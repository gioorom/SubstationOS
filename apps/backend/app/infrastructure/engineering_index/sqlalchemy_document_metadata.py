from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.engineering_index.document_metadata import (
    DocumentMetadata,
    DocumentMetadataPort,
)
from app.models.document import Document as DocumentRecord


class SqlAlchemyDocumentMetadataRepository(DocumentMetadataPort):
    """
    SQLAlchemy adapter for the ``DocumentMetadataPort``, reading the
    existing ``Document`` persistence model. Like
    ``SqlAlchemyDocumentLookup``, it introduces no Document domain
    bounded context - it reads exactly the already-persisted fields a
    document reference exposes and maps the persistence enums to their
    stored string values.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_many(
        self, document_ids: tuple[int, ...]
    ) -> tuple[DocumentMetadata, ...]:
        if not document_ids:
            return ()

        records = (
            self._session.query(DocumentRecord)
            .filter(DocumentRecord.id.in_(set(document_ids)))
            .order_by(DocumentRecord.id.asc())
            .all()
        )

        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_domain(record: DocumentRecord) -> DocumentMetadata:
        return DocumentMetadata(
            document_id=record.id,
            project_id=record.project_id,
            title=record.filename,
            document_format=record.file_format.value,
            document_category=record.category.value,
            revision=record.revision,
            scope=record.scope,
        )
