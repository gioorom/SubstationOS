"""
Tests for the filesystem adapter behind ``DocumentContentPort``
(Milestone 25.2), against real files in pytest's ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.document_identity.content_identity import (
    resolve_content_identity,
)
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)


def _write(tmp_path: Path, name: str, content: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(content)

    return str(path)


def test_describing_a_stored_file_reports_its_size_and_readability(
    tmp_path: Path,
) -> None:
    reference = _write(tmp_path, "diagram.pdf", b"%PDF-1.7 content")

    descriptor = FilesystemDocumentContentAdapter().describe(reference)

    assert descriptor is not None
    assert descriptor.size_bytes == len(b"%PDF-1.7 content")
    assert descriptor.readable is True


def test_describing_a_missing_reference_returns_none(tmp_path: Path) -> None:
    """``None`` means "no such content", which is deliberately different
    from a descriptor reporting ``readable=False``."""

    descriptor = FilesystemDocumentContentAdapter().describe(
        str(tmp_path / "never_written.pdf")
    )

    assert descriptor is None


def test_describing_a_directory_returns_none(tmp_path: Path) -> None:
    descriptor = FilesystemDocumentContentAdapter().describe(str(tmp_path))

    assert descriptor is None


def test_reading_a_prefix_returns_only_the_leading_bytes(
    tmp_path: Path,
) -> None:
    reference = _write(tmp_path, "diagram.pdf", b"%PDF-1.7" + b"x" * 5000)

    prefix = FilesystemDocumentContentAdapter().read_prefix(reference, 8)

    assert prefix == b"%PDF-1.7"


def test_reading_a_prefix_of_zero_length_reads_nothing(
    tmp_path: Path,
) -> None:
    reference = _write(tmp_path, "diagram.pdf", b"%PDF-1.7")

    assert FilesystemDocumentContentAdapter().read_prefix(reference, 0) == b""


def test_iterating_chunks_yields_the_whole_file_in_order(
    tmp_path: Path,
) -> None:
    content = bytes(range(256)) * 40
    reference = _write(tmp_path, "model.dwg", content)

    chunks = list(
        FilesystemDocumentContentAdapter().iter_chunks(reference, 1024)
    )

    assert b"".join(chunks) == content
    assert len(chunks) > 1


def test_content_identity_resolves_through_the_adapter(
    tmp_path: Path,
) -> None:
    """The port and its adapter agree end to end: a real file on disk
    yields a resolved identity with the file's own size."""

    content = b"%PDF-1.7 single line diagram"
    reference = _write(tmp_path, "diagram.pdf", content)

    result = resolve_content_identity(
        FilesystemDocumentContentAdapter(), reference
    )

    assert result.resolved
    assert result.identity.size_bytes == len(content)
    assert result.identity.storage_reference == reference


def test_an_empty_file_on_disk_fails_rather_than_resolving(
    tmp_path: Path,
) -> None:
    reference = _write(tmp_path, "empty.pdf", b"")

    result = resolve_content_identity(
        FilesystemDocumentContentAdapter(), reference
    )

    assert not result.resolved


def test_the_adapter_offers_no_way_to_write(tmp_path: Path) -> None:
    """The port declares three read operations and the adapter implements
    exactly those. A ``save``, ``delete`` or ``move`` here would hand
    every caller of the port a capability nobody asked for."""

    adapter = FilesystemDocumentContentAdapter()
    public = {
        name for name in dir(adapter) if not name.startswith("_")
    }

    assert public == {"describe", "read_prefix", "iter_chunks"}
