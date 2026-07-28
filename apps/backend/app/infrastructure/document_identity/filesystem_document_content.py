from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from app.domain.document_identity.document_content_port import (
    DocumentContentDescriptor,
    DocumentContentPort,
)


class FilesystemDocumentContentAdapter(DocumentContentPort):
    """
    Filesystem adapter for the read-only ``DocumentContentPort``, reading
    the paths ``app.services.storage.save_file`` already writes.

    A ``storage_reference`` is the ``Document.file_path`` value as stored -
    the adapter resolves it exactly as written and never rewrites,
    normalises against a different root, or searches for a near match. A
    reference that does not resolve is *not found*, which is a fact worth
    reporting rather than papering over.

    Nothing here writes. The adapter opens files ``"rb"`` and does not
    implement any mutating operation, because the port declares none.
    """

    def describe(
        self, storage_reference: str
    ) -> DocumentContentDescriptor | None:
        path = Path(storage_reference)

        try:
            if not path.is_file():
                return None

            size_bytes = path.stat().st_size
        except OSError:
            # A reference that cannot even be stat'ed exists as far as we
            # can tell but is unusable - reported as unreadable rather
            # than as missing, so the two stay distinguishable.
            return DocumentContentDescriptor(
                storage_reference=storage_reference,
                size_bytes=0,
                readable=False,
            )

        return DocumentContentDescriptor(
            storage_reference=storage_reference,
            size_bytes=size_bytes,
            readable=os.access(path, os.R_OK),
        )

    def read_prefix(self, storage_reference: str, length: int) -> bytes:
        if length <= 0:
            return b""

        with Path(storage_reference).open("rb") as handle:
            return handle.read(length)

    def iter_chunks(
        self, storage_reference: str, chunk_size: int
    ) -> Iterator[bytes]:
        with Path(storage_reference).open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)

                if not chunk:
                    return

                yield chunk
