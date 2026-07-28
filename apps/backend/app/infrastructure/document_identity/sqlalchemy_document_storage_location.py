from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.models.document import Document as DocumentRecord


class SqlAlchemyDocumentStorageLocation(DocumentStorageLocationPort):
    """
    Reads ``Document.file_path`` - the reference the upload endpoint
    recorded when it stored the bytes.

    Reads one column of one row and returns it unchanged. It does not
    touch storage, does not check that anything exists at the reference,
    and does not repair a stale one: whether the bytes are actually there
    is ``DocumentContentPort``'s question, and answering it here would
    make a registry read depend on a filesystem.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_storage_reference(self, document_id: int) -> str | None:
        record = self._session.get(DocumentRecord, document_id)

        if record is None:
            return None

        return record.file_path or None
