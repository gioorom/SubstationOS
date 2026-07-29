"""
Serving a document's original bytes, safely.

**The client never names a location.** It names a document id; the
registry says which document that is; the storage-location port says
what opaque reference the registry recorded for it; the content port
turns that reference into bytes. No step accepts a path from the caller,
so path traversal is not defended against here - it is *unreachable*.
There is no parameter through which a caller could express one.

The download name is the other half. A stored filename is user-supplied
text that ends up in an HTTP header, so it is sanitised here rather than
trusted: header injection and traversal both live in that string.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.domain.document_registry.document_models import (
    DocumentFormat,
    media_type_for,
)

#: Everything outside this set is replaced. Deliberately a small
#: allow-list rather than a block-list of the dangerous characters:
#: enumerating what is safe cannot be defeated by a character nobody
#: thought of.
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

#: The name served when nothing usable survives sanitisation. A document
#: called "../../" is still downloadable; it just is not called that.
FALLBACK_FILENAME = "document"

#: Long enough for any real engineering filename, short enough that no
#: header limit is approached.
MAX_FILENAME_LENGTH = 120


def safe_download_filename(filename: str) -> str:
    """
    Reduce a stored filename to something safe to put in a
    ``Content-Disposition`` header.

    - Unicode is normalised to NFKD and non-ASCII dropped, so ``schéma``
      becomes ``schema`` rather than an encoded blob a client may or may
      not decode.
    - Path separators, ``..`` and control characters cannot survive: they
      are not in the allow-list.
    - Quotes and newlines cannot survive either, which is what closes
      header injection.
    - Leading dots are stripped so nothing becomes a hidden file.
    """

    ascii_only = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    collapsed = _SAFE_FILENAME.sub("_", ascii_only).strip("._")

    if not collapsed:
        return FALLBACK_FILENAME

    return collapsed[:MAX_FILENAME_LENGTH]


@dataclass(frozen=True, slots=True)
class DocumentDownload:
    """
    Everything an HTTP layer needs to serve a document, and nothing that
    would tell a client where it came from.

    ``storage_reference`` is present because the transport has to hand it
    back to the content port to stream the bytes - and it is the one
    field that must never be rendered into a response body or header. A
    test asserts it does not appear in any public schema.
    """

    document_id: int
    storage_reference: str
    download_filename: str
    media_type: str
    size_bytes: int

    @classmethod
    def of(
        cls,
        *,
        document_id: int,
        storage_reference: str,
        filename: str,
        document_format: DocumentFormat,
        size_bytes: int,
    ) -> "DocumentDownload":
        return cls(
            document_id=document_id,
            storage_reference=storage_reference,
            download_filename=safe_download_filename(filename),
            media_type=media_type_for(document_format),
            size_bytes=size_bytes,
        )

    @property
    def content_disposition(self) -> str:
        """
        The header value. ``attachment`` rather than ``inline``: a
        document of unverified provenance must not be rendered by the
        browser in this application's origin.
        """

        return f'attachment; filename="{self.download_filename}"'
