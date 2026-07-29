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

import re
import secrets
import shutil
import unicodedata
from pathlib import Path

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


def save_file(
    uploaded_file,
    filename: str,
    folder: str = "documents",
) -> Path:
    """
    Write an uploaded stream into the storage root and return the path it
    was written to.

    That path is the ``storage_reference`` the registry records. It is
    private backend state and never leaves the backend - see
    ``app.schemas.document``.

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

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(uploaded_file, buffer)

    return file_path
