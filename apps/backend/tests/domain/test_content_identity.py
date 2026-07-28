"""
Tests for deterministic content identity (Milestone 25.2).

The port is faked in memory here, so these stay pure domain tests: no
filesystem, no temporary directories, no I/O. The filesystem adapter has
its own tests under ``tests/infrastructure``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator

from app.domain.document_identity.content_identity import (
    CHECKSUM_ALGORITHM,
    ContentIdentityFailureReason,
    resolve_content_identity,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentDescriptor,
    DocumentContentPort,
)


class InMemoryContent(DocumentContentPort):
    """A byte store that behaves exactly as the port describes, with
    deliberate switches for the three ways content goes wrong."""

    def __init__(
        self,
        contents: dict[str, bytes],
        *,
        unreadable: frozenset[str] = frozenset(),
        reported_size: dict[str, int] | None = None,
        raise_on_read: bool = False,
    ) -> None:
        self._contents = contents
        self._unreadable = unreadable
        self._reported_size = reported_size or {}
        self._raise_on_read = raise_on_read

    def describe(
        self, storage_reference: str
    ) -> DocumentContentDescriptor | None:
        if storage_reference not in self._contents:
            return None

        return DocumentContentDescriptor(
            storage_reference=storage_reference,
            size_bytes=self._reported_size.get(
                storage_reference, len(self._contents[storage_reference])
            ),
            readable=storage_reference not in self._unreadable,
        )

    def read_prefix(self, storage_reference: str, length: int) -> bytes:
        return self._contents[storage_reference][:length]

    def iter_chunks(
        self, storage_reference: str, chunk_size: int
    ) -> Iterator[bytes]:
        if self._raise_on_read:
            raise OSError("the stream broke")

        content = self._contents[storage_reference]

        for start in range(0, len(content), chunk_size):
            yield content[start : start + chunk_size]


# --- The happy path ----------------------------------------------------


def test_content_identity_is_the_sha256_of_the_bytes() -> None:
    content = b"%PDF-1.7 single line diagram"
    port = InMemoryContent({"docs/one.pdf": content})

    result = resolve_content_identity(port, "docs/one.pdf")

    assert result.resolved
    assert result.identity.checksum == hashlib.sha256(content).hexdigest()
    assert result.identity.checksum_algorithm == CHECKSUM_ALGORITHM
    assert result.identity.size_bytes == len(content)


def test_the_same_bytes_always_produce_the_same_checksum() -> None:
    port = InMemoryContent({"a": b"identical bytes"})

    first = resolve_content_identity(port, "a")
    second = resolve_content_identity(port, "a")

    assert first.identity.checksum == second.identity.checksum


def test_the_same_bytes_under_different_names_share_a_checksum() -> None:
    """The checksum describes the bytes, not the filing. A checksum that
    depended on the name would answer a question nobody asked."""

    port = InMemoryContent(
        {"docs/original.pdf": b"same bytes", "docs/copy.pdf": b"same bytes"}
    )

    first = resolve_content_identity(port, "docs/original.pdf")
    second = resolve_content_identity(port, "docs/copy.pdf")

    assert first.identity.checksum == second.identity.checksum
    assert first.identity.storage_reference != second.identity.storage_reference


def test_different_bytes_produce_different_checksums() -> None:
    port = InMemoryContent({"a": b"revision 00", "b": b"revision 01"})

    first = resolve_content_identity(port, "a")
    second = resolve_content_identity(port, "b")

    assert first.identity.checksum != second.identity.checksum


def test_a_large_document_is_hashed_in_chunks_without_changing_the_result(
) -> None:
    content = b"x" * (3 * 1024 * 1024 + 17)
    port = InMemoryContent({"big.dwg": content})

    result = resolve_content_identity(port, "big.dwg")

    assert result.identity.checksum == hashlib.sha256(content).hexdigest()
    assert result.identity.size_bytes == len(content)


# --- The four ways it fails --------------------------------------------


def test_missing_content_fails_as_content_not_found() -> None:
    result = resolve_content_identity(InMemoryContent({}), "docs/gone.pdf")

    assert not result.resolved
    assert (
        result.failure_reason
        is ContentIdentityFailureReason.CONTENT_NOT_FOUND
    )
    assert result.identity is None


def test_a_blank_storage_reference_fails_as_content_not_found() -> None:
    result = resolve_content_identity(InMemoryContent({}), "   ")

    assert (
        result.failure_reason
        is ContentIdentityFailureReason.CONTENT_NOT_FOUND
    )


def test_unreadable_content_is_distinguished_from_missing_content() -> None:
    """Two different problems for an engineer: one file is not there, the
    other is there and the process cannot open it."""

    port = InMemoryContent(
        {"docs/locked.pdf": b"content"},
        unreadable=frozenset({"docs/locked.pdf"}),
    )

    result = resolve_content_identity(port, "docs/locked.pdf")

    assert (
        result.failure_reason
        is ContentIdentityFailureReason.CONTENT_INACCESSIBLE
    )


def test_empty_content_fails_rather_than_hashing_to_the_empty_digest(
) -> None:
    """SHA-256 of nothing is a real value, which is exactly the problem:
    recorded as an identity it would make every empty document in the
    system look like the same document."""

    port = InMemoryContent({"docs/empty.pdf": b""})

    result = resolve_content_identity(port, "docs/empty.pdf")

    assert result.failure_reason is ContentIdentityFailureReason.EMPTY_CONTENT
    assert result.identity is None


def test_a_stream_that_breaks_partway_fails_as_a_checksum_failure() -> None:
    port = InMemoryContent({"docs/one.pdf": b"content"}, raise_on_read=True)

    result = resolve_content_identity(port, "docs/one.pdf")

    assert (
        result.failure_reason
        is ContentIdentityFailureReason.CHECKSUM_FAILURE
    )


def test_content_that_changed_while_being_read_is_not_recorded() -> None:
    """The digest would describe bytes other than the ones reported, so
    recording it would be a lie."""

    port = InMemoryContent(
        {"docs/one.pdf": b"twelve bytes"},
        reported_size={"docs/one.pdf": 999},
    )

    result = resolve_content_identity(port, "docs/one.pdf")

    assert (
        result.failure_reason
        is ContentIdentityFailureReason.CHECKSUM_FAILURE
    )
    assert result.identity is None


def test_every_failure_carries_an_explanation() -> None:
    result = resolve_content_identity(InMemoryContent({}), "docs/gone.pdf")

    assert result.detail
    assert "docs/gone.pdf" in result.detail


# --- Identity is not deduplication -------------------------------------


def test_identical_checksums_are_recorded_and_nothing_is_concluded(
) -> None:
    """Whether a repeated upload is a duplicate, a re-issue under a new
    revision, or the same drawing filed twice is a question about the
    documents. This milestone answers none of it - it reports the fact and
    stops."""

    port = InMemoryContent({"a": b"same", "b": b"same"})

    first = resolve_content_identity(port, "a")
    second = resolve_content_identity(port, "b")

    assert first.resolved and second.resolved
    assert not hasattr(first, "duplicate_of")
    assert not hasattr(first.identity, "duplicate_of")
