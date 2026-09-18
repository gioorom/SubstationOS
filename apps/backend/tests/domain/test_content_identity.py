"""
Tests for deterministic content identity (Milestone 25.2).

The port is faked in memory here, so these stay pure domain tests: no
filesystem, no temporary directories, no I/O. The filesystem adapter has
its own tests under ``tests/infrastructure``.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator

import pytest

from app.domain.document_identity.content_identity import (
    CHECKSUM_ALGORITHM,
    ContentIdentity,
    ContentIdentityFailureReason,
    MalformedChecksumError,
    identity_of_written_bytes,
    resolve_content_identity,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentDescriptor,
    DocumentContentPort,
)
from app.domain.document_identity.document_identity_exceptions import (
    DocumentIdentityError,
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


# --- Identity taken during the write (ADR-0036) ------------------------
#
# ``identity_of_written_bytes`` answers "what did I just store", where
# ``resolve_content_identity`` above answers "what is at this reference
# now". The second is still the one ingestion and canonicalisation use;
# the upload path uses the first, because a digest accumulated over the
# bytes going to disk provably covers the bytes that were persisted.


def test_written_bytes_are_identified_by_the_digest_taken_while_writing(
) -> None:
    content = b"%PDF-1.7 sezione montante"
    digest = hashlib.sha256(content).hexdigest()

    result = identity_of_written_bytes(
        storage_reference="documents/schema_ab12cd34.pdf",
        checksum=digest,
        size_bytes=len(content),
    )

    assert result.resolved
    assert result.identity.checksum == digest
    assert result.identity.checksum_algorithm == CHECKSUM_ALGORITHM
    assert result.identity.size_bytes == len(content)


def test_a_write_that_stored_nothing_records_no_identity() -> None:
    """
    ADR-0036 §8: the empty-file refusal had to survive the move from
    hashing on read to hashing on write.

    Without this, a zero-byte upload acquires an identity the moment the
    refusal is only enforced on the read path - and the refusal was
    written on the read path.
    """

    result = identity_of_written_bytes(
        storage_reference="documents/empty_ab12cd34.pdf",
        checksum=hashlib.sha256(b"").hexdigest(),
        size_bytes=0,
    )

    assert not result.resolved
    assert result.failure_reason is ContentIdentityFailureReason.EMPTY_CONTENT
    assert result.identity is None


def test_an_empty_write_never_yields_the_sha256_empty_digest() -> None:
    """
    The digest of nothing is a real, well-defined value, which is
    exactly the problem: recorded as an identity it would make every
    empty document in the system look like the same document.

    Asserted against the literal so that a refusal replaced by "record
    it anyway" is caught by name rather than by a nullability check that
    a future default could satisfy.
    """

    empty_digest = (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )

    result = identity_of_written_bytes(
        storage_reference="documents/empty_ab12cd34.pdf",
        checksum=empty_digest,
        size_bytes=0,
    )

    assert result.identity is None
    assert empty_digest not in (result.detail or "")


def test_the_content_identity_records_nothing_but_the_bytes() -> None:
    """
    ADR-0036 §10, the metadata boundary, asserted structurally.

    No clock, no uploader, no ``project_id``, no scope, category or
    revision can influence a digest that has nowhere to keep them. Every
    one of those is editable after upload, so a value object that held
    one would let ordinary registry housekeeping re-identify a document
    and orphan every artifact keyed to it.
    """

    identity = identity_of_written_bytes(
        storage_reference="documents/schema_ab12cd34.pdf",
        checksum="a" * 64,
        size_bytes=12,
    ).identity

    assert set(ContentIdentity.__slots__) == {
        "storage_reference",
        "checksum_algorithm",
        "checksum",
        "size_bytes",
    }
    assert identity.size_bytes == 12


# --- The representation rule (ADR-0036 §7) ------------------------------
#
# A checksum is not "whatever names these bytes". Uppercase hex, a
# ``sha256:`` prefix and base64 all name the same digest, and none of
# them compares equal to the spelling this context records. A column
# that can hold more than one spelling of one value is a column no
# equality test can be built on - and every downstream guarantee of this
# milestone is an equality test.
#
# The guard lives in ``ContentIdentity.__post_init__`` rather than at the
# call site, so the property belongs to the value rather than to the
# only caller that happens to be correct today.


CANONICAL_DIGEST = hashlib.sha256(b"%PDF-1.7 sezione montante").hexdigest()

#: Every spelling that names the right bytes and is still not an
#: identity, plus the two that name nothing at all.
NON_CANONICAL_SPELLINGS = {
    "uppercase_hex": CANONICAL_DIGEST.upper(),
    "algorithm_prefixed": f"sha256:{CANONICAL_DIGEST}",
    "base64": base64.b64encode(
        bytes.fromhex(CANONICAL_DIGEST)
    ).decode("ascii"),
    "one_character_short": CANONICAL_DIGEST[:63],
    "one_character_long": CANONICAL_DIGEST + "0",
    "not_hexadecimal": "z" * 64,
    "empty": "",
}


@pytest.mark.parametrize(
    "spelling",
    list(NON_CANONICAL_SPELLINGS.values()),
    ids=list(NON_CANONICAL_SPELLINGS),
)
def test_a_checksum_in_any_other_spelling_is_refused(
    spelling: str,
) -> None:
    """
    Without this, a digest that sometimes matches itself can be
    persisted: the uppercase and ``sha256:``-prefixed forms name exactly
    the right bytes, compare unequal to the recorded form, and would
    make a document silently fail to match its own artifacts.
    """

    with pytest.raises(MalformedChecksumError):
        ContentIdentity(
            storage_reference="documents/schema_ab12cd34.pdf",
            checksum_algorithm=CHECKSUM_ALGORITHM,
            checksum=spelling,
            size_bytes=12,
        )


@pytest.mark.parametrize("algorithm", ["sha512", "SHA256", "md5"])
def test_an_identity_under_another_algorithm_is_refused(
    algorithm: str,
) -> None:
    """
    The algorithm is recorded alongside the value so a future change
    makes old identities recognisably old. That only works if the field
    is a fact rather than a caller's assertion: a row claiming
    ``sha512`` while holding a 64-character digest would be read as a
    truncated SHA-512 by whoever comes to migrate it.
    """

    with pytest.raises(MalformedChecksumError):
        ContentIdentity(
            storage_reference="documents/schema_ab12cd34.pdf",
            checksum_algorithm=algorithm,
            checksum=CANONICAL_DIGEST,
            size_bytes=12,
        )


@pytest.mark.parametrize("size_bytes", [0, -1])
def test_an_identity_of_no_bytes_is_refused(size_bytes: int) -> None:
    """
    A content identity describes bytes that exist. Zero is the empty
    document that §8 refuses to identify, and a negative length is
    arithmetic nobody intended; neither is a length, and recording
    either would put a value in the column that no comparison can
    trust.
    """

    with pytest.raises(MalformedChecksumError):
        ContentIdentity(
            storage_reference="documents/schema_ab12cd34.pdf",
            checksum_algorithm=CHECKSUM_ALGORITHM,
            checksum=CANONICAL_DIGEST,
            size_bytes=size_bytes,
        )


def test_a_digest_as_hexdigest_writes_it_is_accepted() -> None:
    """
    The guard must reject nothing that exists today. Every digest in
    this system is written by ``hexdigest()``, so a rule that refused
    one would refuse every upload - which is why the accepted case is
    asserted from a real hash rather than from a hand-typed literal.
    """

    identity = ContentIdentity(
        storage_reference="documents/schema_ab12cd34.pdf",
        checksum_algorithm=CHECKSUM_ALGORITHM,
        checksum=CANONICAL_DIGEST,
        size_bytes=25,
    )

    assert identity.checksum == CANONICAL_DIGEST


def test_a_malformed_checksum_is_a_document_identity_error() -> None:
    """
    Callers catch this context's failures by its base class. An
    exception outside that hierarchy would escape every handler written
    against it and surface as an unhandled error somewhere far from the
    caller that caused it.
    """

    assert issubclass(MalformedChecksumError, DocumentIdentityError)


def test_an_empty_write_is_reported_and_a_malformed_digest_is_raised(
) -> None:
    """
    The two refusals are not the same refusal, and collapsing them
    would lose a distinction the registry depends on.

    An empty document is a **fact about a document**: it is stored, it
    is listed, and it simply has no identity - so it travels as a typed
    ``EMPTY_CONTENT`` failure the upload route records as ``NULL``. A
    malformed digest is a **caller error**: no document is at fault, and
    returning it as a failure reason would invite the caller to persist
    it as though one were.

    Asserted together so a later "simplification" that turns either into
    the other has to delete this test to do it.
    """

    empty = identity_of_written_bytes(
        storage_reference="documents/empty_ab12cd34.pdf",
        checksum=hashlib.sha256(b"").hexdigest(),
        size_bytes=0,
    )

    assert empty.failure_reason is ContentIdentityFailureReason.EMPTY_CONTENT
    assert empty.identity is None

    with pytest.raises(MalformedChecksumError):
        identity_of_written_bytes(
            storage_reference="documents/schema_ab12cd34.pdf",
            checksum=CANONICAL_DIGEST.upper(),
            size_bytes=25,
        )
