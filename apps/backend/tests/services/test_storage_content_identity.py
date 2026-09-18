"""
The write that hashes what it writes (ADR-0036 §8).

Before this milestone ``save_file`` copied a stream and returned a path,
and the upload then re-opened the file and hashed it a second time. The
digest that reached the format classifier therefore described the bytes
that were there *at read time*, not the bytes this write had put there:
a same-length substitution between close and re-open passed the size
cross-check unnoticed. Hashing the chunks on their way to disk closes
that window instead of narrowing it, and these tests hold it closed.

``BASE_STORAGE`` is a module constant pointing at the deployment storage
root, so every test here redirects it to a temporary directory. Writing
into the repository's ``storage/`` tree would leave real files behind
and make one test's output visible to another.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from app.domain.document_identity.content_identity import (
    CHECKSUM_ALGORITHM,
    ContentIdentityFailureReason,
)
from app.services import storage
from app.services.storage import discard_file, save_file

PDF = b"%PDF-1.7 Schema unifilare - sezione MT"
DXF = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"


@pytest.fixture()
def storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A storage root that belongs to this test and nobody else.

    Redirected rather than shared: ``BASE_STORAGE`` is a relative path
    resolved against the process working directory, so a test that used
    it as-is would write into the deployment tree and never clean up.
    """

    monkeypatch.setattr(storage, "BASE_STORAGE", tmp_path)

    return tmp_path


def _stored(content: bytes, filename: str):
    return save_file(io.BytesIO(content), filename)


def _files(storage_root: Path) -> list[Path]:
    return sorted(
        path for path in storage_root.rglob("*") if path.is_file()
    )


# --- The digest covers the bytes that were persisted --------------------


def test_the_stored_file_is_identified_by_a_digest_of_its_own_bytes(
    storage_root: Path,
) -> None:
    """
    ADR-0036 §28 row 13, at the layer where the guarantee is created.

    ``save_file`` now has two responsibilities, and the second one is
    the one a future refactor could quietly drop. Recomputing the digest
    from the file on disk is the only assertion that notices if it does.
    """

    stored = _stored(PDF, "schema.pdf")

    written = stored.path.read_bytes()

    assert stored.content.resolved
    assert stored.content.identity.checksum == hashlib.sha256(
        written
    ).hexdigest()
    assert stored.content.identity.checksum_algorithm == CHECKSUM_ALGORITHM
    assert stored.content.identity.size_bytes == len(written)


def test_the_bytes_reach_disk_exactly_as_they_arrived(
    storage_root: Path,
) -> None:
    """
    ADR-0036 §9: the source bytes are authoritative and are never
    normalized. A transformation between the stream and the file would
    make the recorded digest describe something the engineer never
    uploaded.
    """

    stored = _stored(PDF, "schema.pdf")

    assert stored.path.read_bytes() == PDF


def test_a_large_stream_is_hashed_in_chunks_without_changing_the_digest(
    storage_root: Path,
) -> None:
    """The hash is accumulated chunk by chunk so an arbitrarily large
    drawing is never held in memory; chunking must not be able to change
    the answer."""

    content = b"x" * (2 * 1024 * 1024 + 37)

    stored = _stored(content, "big.dwg")

    assert stored.content.identity.checksum == hashlib.sha256(
        content
    ).hexdigest()
    assert stored.content.identity.size_bytes == len(content)


# --- What is excluded from the identity (§10, §11) ----------------------


def test_the_uploaded_filename_does_not_affect_the_identity(
    storage_root: Path,
) -> None:
    """
    ADR-0036 §28 row 3.

    The filename is registry metadata and is editable. If it reached the
    digest, correcting a typo in a document's name would re-identify it
    and orphan every artifact keyed to the old value.
    """

    first = _stored(PDF, "schema.pdf")
    second = _stored(PDF, "schema-rev-corretta.pdf")

    assert first.content.identity.checksum == (
        second.content.identity.checksum
    )


def test_the_storage_path_does_not_affect_the_identity(
    storage_root: Path,
) -> None:
    """
    ADR-0036 §28 row 4.

    The stored name carries a random suffix so no upload overwrites
    another, which means the same file never lands at the same path
    twice. A digest that covered the path would make every upload of one
    file a different document version.
    """

    first = _stored(PDF, "schema.pdf")
    second = _stored(PDF, "schema.pdf")

    assert first.path != second.path
    assert first.content.identity.storage_reference != (
        second.content.identity.storage_reference
    )
    assert first.content.identity.checksum == (
        second.content.identity.checksum
    )


def test_different_bytes_are_stored_under_different_identities(
    storage_root: Path,
) -> None:
    """ADR-0036 §28 row 2: without it a changed drawing reuses the old
    artifacts and an engineer is answered from superseded content."""

    first = _stored(PDF, "schema.pdf")
    second = _stored(DXF, "schema.dxf")

    assert first.content.identity.checksum != (
        second.content.identity.checksum
    )


# --- The empty-file refusal at the write (§8) ---------------------------


def test_a_zero_byte_upload_is_stored_but_records_no_identity(
    storage_root: Path,
) -> None:
    """
    ADR-0036 §28 row 14.

    The file is written - refusing the identity is not refusing the
    upload - but nothing is identified, because there is nothing to
    identify.
    """

    stored = _stored(b"", "empty.pdf")

    assert stored.path.exists()
    assert not stored.content.resolved
    assert stored.content.identity is None
    assert (
        stored.content.failure_reason
        is ContentIdentityFailureReason.EMPTY_CONTENT
    )


def test_a_zero_byte_upload_never_produces_the_empty_digest(
    storage_root: Path,
) -> None:
    """
    SHA-256 of nothing is a real value, and recording it would make
    every empty document in the system look like the same document.

    Asserted against the literal, because a refusal that was replaced by
    "record it anyway" would still satisfy a check that only looked for
    a resolved result.
    """

    empty_digest = (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )

    stored = _stored(b"", "empty.pdf")

    assert empty_digest not in repr(stored.content)


# --- Compensation (§20) -------------------------------------------------


def test_a_discarded_file_is_gone_from_storage(
    storage_root: Path,
) -> None:
    """The write the upload has to undo when its commit fails. Without
    it the bytes stay on disk under a name nothing references, in a tree
    excluded from version control, and nothing ever reconciles them."""

    stored = _stored(PDF, "schema.pdf")

    discard_file(stored.path)

    assert _files(storage_root) == []


def test_discarding_a_file_that_is_already_gone_is_not_a_failure(
    storage_root: Path,
) -> None:
    """
    Compensation runs while an exception is already on its way out of
    the handler. A missing file is the end state it wants, and raising
    here would replace the reason the upload failed with a filesystem
    error about the cleanup.
    """

    stored = _stored(PDF, "schema.pdf")
    stored.path.unlink()

    discard_file(stored.path)


def test_discarding_one_file_leaves_every_other_alone(
    storage_root: Path,
) -> None:
    """Compensation undoes the write this request made and nothing else.
    A cleanup that swept the directory would delete documents belonging
    to requests that succeeded."""

    kept = _stored(PDF, "kept.pdf")
    discarded = _stored(DXF, "discarded.dxf")

    discard_file(discarded.path)

    assert _files(storage_root) == [kept.path]


# --- Compensation refuses to leave the storage root ---------------------
#
# ``discard_file`` is a delete. Until this round its only safety was that
# its single caller passed it a path ``save_file`` had already validated
# - which is a property of that call site, not of this function, and one
# refactor away from not being true. The root is now re-checked here, and
# these hold that check in place.


def test_discarding_a_path_outside_the_storage_root_is_refused(
    storage_root: Path, tmp_path: Path
) -> None:
    """
    A delete whose only safety is a careful caller is one caller away
    from deleting something else. Without this the compensation would
    unlink whatever path it was handed, anywhere on the machine.
    """

    outside = tmp_path.parent / "not_in_storage.pdf"
    outside.write_bytes(PDF)

    with pytest.raises(storage.UnsafeStoragePathError):
        discard_file(outside)

    outside.unlink()


def test_a_refused_discard_leaves_the_file_where_it_is(
    storage_root: Path, tmp_path: Path
) -> None:
    """
    Refusing has to mean *not deleting*, not "raising afterwards". The
    file named here is by definition one this request never wrote, so
    removing it would be destroying somebody else's data while reporting
    that it had been protected.
    """

    outside = tmp_path.parent / "not_in_storage_either.pdf"
    outside.write_bytes(PDF)

    with pytest.raises(storage.UnsafeStoragePathError):
        discard_file(outside)

    assert outside.read_bytes() == PDF

    outside.unlink()


def test_a_traversal_path_that_escapes_the_root_is_refused(
    storage_root: Path, tmp_path: Path
) -> None:
    """
    The check resolves before it compares, so a path that *starts*
    inside the root and climbs out of it is refused like any other
    outsider. A prefix comparison on the unresolved string would let
    this one through.
    """

    escaping = tmp_path.parent / "escaped.pdf"
    escaping.write_bytes(PDF)

    traversal = storage_root / "documents" / ".." / ".." / escaping.name

    with pytest.raises(storage.UnsafeStoragePathError):
        discard_file(traversal)

    assert escaping.exists()

    escaping.unlink()
