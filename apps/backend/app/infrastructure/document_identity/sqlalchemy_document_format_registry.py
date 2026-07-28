from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.document_identity.document_format_registry import (
    DocumentFormatRegistryPort,
    RegisteredDocumentFormat,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentFormat


class SqlAlchemyDocumentFormatRegistry(DocumentFormatRegistryPort):
    """
    SQLAlchemy adapter over ``app.models.document.Document``.

    ``record_format`` writes ``file_format`` and nothing else - not the
    filename, not the category, not ``uploaded_at``. A backfill that
    touched a second column would be editing history it was not asked to
    edit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_stored_format(
        self, stored_format: str
    ) -> tuple[RegisteredDocumentFormat, ...]:
        records = (
            self._session.query(DocumentRecord)
            .filter(DocumentRecord.file_format == stored_format)
            .order_by(DocumentRecord.id.asc())
            .all()
        )

        return tuple(
            RegisteredDocumentFormat(
                document_id=record.id,
                filename=record.filename,
                storage_reference=record.file_path or None,
                stored_format=record.file_format.value,
            )
            for record in records
        )

    def record_format(self, document_id: int, classified_format: str) -> None:
        record = self._session.get(DocumentRecord, document_id)

        if record is None:
            return

        record.file_format = DocumentFormat(classified_format)
        self._session.commit()
