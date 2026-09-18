"""
Where uploaded bytes are written.

**A caller-supplied filename never becomes a path.** Before Milestone
30.1.3 the uploaded name was joined to the storage directory directly, so
a file called ``../../app/main.py`` was written wherever that resolved,
and two uploads with the same name silently overwrote each other. Both
are fixed here:

- the stored name is derived from the original by an allow-list, so no
  separator, ``..`` or control character can survive;
- a short random suffix makes it unique, so an upload never destroys an
  earlier one;
- the result is resolved and checked to be **inside** the storage root
  before anything is written, which closes the hole rather than trusting
  the sanitiser to be perfect.

The original filename is still recorded on the document row and is what
an engineer sees. Only the *storage* name is sanitised - the two are
different things, and conflating them would rename people's documents.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.domain.document_identity.content_identity import (
    CHECKSUM_ALGORITHM,
    CHECKSUM_CHUNK_SIZE,
    ContentIdentityResult,
    identity_of_written_bytes,
)

_LOGGER = logging.getLogger(__name__)

BASE_STORAGE = Path("../../storage")

#: Allow-list, not a block-list: enumerating what is safe cannot be
#: defeated by a character nobody thought of.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

_FALLBACK_STEM = "document"

#: Long enough for a real engineering filename, short enough to stay well
#: inside every filesystem's path limit once root and suffix are added.
_MAX_STEM_LENGTH = 80


class UnsafeStoragePathError(RuntimeError):
    """
    The computed path escaped the storage root.

    Unreachable through the sanitiser above; raised anyway, because a
    security control enforced only by an earlier step is one refactor
    away from not being enforced at all.
    """


def _safe_stem(filename: str) -> str:
    ascii_only = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    cleaned = _UNSAFE.sub("_", ascii_only).strip("._")

    return (cleaned or _FALLBACK_STEM)[:_MAX_STEM_LENGTH]


def safe_storage_name(filename: str) -> str:
    """
    The name an uploaded file is stored under: a sanitised form of the
    original, plus a random suffix so no upload overwrites another.
    """

    stem = _safe_stem(filename)
    suffix = secrets.token_hex(4)

    if "." in stem:
        base, _, extension = stem.rpartition(".")
        return f"{base}_{suffix}.{extension}"

    return f"{stem}_{suffix}"


@dataclass(frozen=True, slots=True)
class StoredFile:
    """
    Where the bytes went, and which bytes they were.

    The two are established together on purpose. Hashing afterwards
    would describe whatever the file held at the moment of the second
    read, which is not necessarily what this write put there.
    """

    path: Path
    content: ContentIdentityResult


def save_file(
    uploaded_file,
    filename: str,
    folder: str = "documents",
) -> StoredFile:
    """
    Write an uploaded stream into the storage root and return the path it
    was written to, together with the identity of the bytes written.

    That path is the ``storage_reference`` the registry records. It is
    private backend state and never leaves the backend - see
    ``app.schemas.document``.

    **The digest is taken from the same chunks that go to disk**, in one
    pass. Reading the file back to hash it would cost a second full read
    and would leave a window in which the bytes hashed need not be the
    bytes stored; both disappear by hashing here. The rule that turns a
    digest and a length into an identity - including the refusal to
    identify an empty file - stays in the domain, which is why this
    function computes and does not decide.

    :raises UnsafeStoragePathError: the computed path is outside the root
    """

    storage_path = BASE_STORAGE / folder

    storage_path.mkdir(parents=True, exist_ok=True)

    file_path = storage_path / safe_storage_name(filename)

    root = storage_path.resolve()

    if not file_path.resolve().is_relative_to(root):
        raise UnsafeStoragePathError(
            "The computed storage path is outside the storage root."
        )

    digest = hashlib.new(CHECKSUM_ALGORITHM)
    written_bytes = 0

    with file_path.open("wb") as buffer:
        while True:
            chunk = uploaded_file.read(CHECKSUM_CHUNK_SIZE)

            if not chunk:
                break

            buffer.write(chunk)
            digest.update(chunk)
            written_bytes += len(chunk)

    try:
        content = identity_of_written_bytes(
            storage_reference=str(file_path),
            checksum=digest.hexdigest(),
            size_bytes=written_bytes,
        )
    except Exception:
        # Identifying the bytes is the last thing this function does,
        # and it happens with the file already on disk. If it raises,
        # the caller never learns the path and so can never compensate
        # for it - so the write is undone here, where the path is still
        # known. Unreachable while the only digest is `hexdigest()`;
        # present for the same reason `UnsafeStoragePathError` is.
        discard_file(file_path)
        raise

    return StoredFile(path=file_path, content=content)


def discard_file(file_path: Path) -> None:
    """
    Remove a stored file whose document row was never committed.

    Compensation, not cleanup: it undoes a write this request made and
    nothing else. Best effort by nature - if the process dies before it
    runs, the file stays - so it never reports success and never masks
    the failure that brought it here. A missing file is the desired
    end state, so it is not an error.

    **The storage root is re-checked here, not assumed.** Today the only
    path that reaches this function is one ``save_file`` already
    validated, so the check rejects nothing - which is the same reason
    ``save_file`` raises ``UnsafeStoragePathError`` on a branch its own
    sanitiser makes unreachable. This is a delete, and a delete whose
    only safety is that its single caller happens to be careful is one
    caller away from deleting something else.
    """

    root = BASE_STORAGE.resolve()

    try:
        if not file_path.resolve().is_relative_to(root):
            raise UnsafeStoragePathError(
                "Refusing to discard a path outside the storage root."
            )
    except OSError as error:
        _LOGGER.warning(
            "Could not resolve %s while discarding it after a failed "
            "upload; the file may remain: %s",
            file_path,
            error,
        )
        return

    try:
        file_path.unlink(missing_ok=True)
    except OSError as error:
        # The upload is already failing and the caller is about to
        # re-raise that failure. Replacing it with a filesystem error
        # from the cleanup would hide the reason the upload failed - so
        # this is recorded rather than raised. Silence would leave an
        # orphan nothing knows about.
        _LOGGER.warning(
            "Could not discard %s after a failed upload commit; it is "
            "now an orphaned file: %s",
            file_path,
            error,
        )
