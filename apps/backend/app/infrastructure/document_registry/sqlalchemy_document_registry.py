"""
SQLAlchemy adapter for the document registry.

This is the **only** module that knows a document is a row in a table
called ``documents`` with a column called ``file_path``. It maps that row
onto the public value objects, and the mapping is where the storage
column stops: no value object it constructs has a field for it.
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.domain.document_registry.document_failures import (
    DocumentPersistenceError,
)
from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentDetail,
    DocumentFormat,
    DocumentSummary,
)
from app.domain.document_registry.document_query import (
    DocumentQuery,
    DocumentSortField,
)
from app.domain.document_registry.document_repository import (
    DocumentRegistryRepository,
)
from app.domain.shared_kernel.pagination import Page, SortDirection
from app.models.document import Document as DocumentRecord
from app.models.document_ingestion import DocumentIngestionJob

#: The one place a governed sort field becomes a column.
_SORT_COLUMNS = {
    DocumentSortField.UPLOADED_AT: DocumentRecord.uploaded_at,
    DocumentSortField.FILENAME: DocumentRecord.filename,
    DocumentSortField.REVISION: DocumentRecord.revision,
    DocumentSortField.DOCUMENT_FORMAT: DocumentRecord.file_format,
}

#: The fields ``DocumentSearchTerm`` documents itself as searching.
_SEARCHED_COLUMNS = (
    DocumentRecord.filename,
    DocumentRecord.project_name,
)


def _escape_like(value: str) -> str:
    r"""Escape ``LIKE`` wildcards so a literal ``%`` or ``_`` matches
    itself. ``\`` first, or it double-escapes what follows."""

    return (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


class SqlAlchemyDocumentRegistryRepository(DocumentRegistryRepository):
    """Reads the existing ``app.models.document.Document`` mapping."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_page(self, query: DocumentQuery) -> Page[DocumentSummary]:
        try:
            filtered = self._apply_filters(
                self._session.query(DocumentRecord), query
            )

            total = filtered.with_entities(
                func.count(DocumentRecord.id)
            ).scalar()

            records = (
                self._apply_order(filtered, query)
                .offset(query.page.offset)
                .limit(query.page.limit)
                .all()
            )
        except Exception as error:  # noqa: BLE001 - re-raised as typed
            raise DocumentPersistenceError(type(error).__name__) from error

        return Page.of(
            tuple(self._to_summary(record) for record in records),
            total=total or 0,
            request=query.page,
        )

    def find_detail(self, document_id: int) -> DocumentDetail | None:
        try:
            record = self._session.get(DocumentRecord, document_id)
        except Exception as error:  # noqa: BLE001 - re-raised as typed
            raise DocumentPersistenceError(type(error).__name__) from error

        if record is None:
            return None

        return self._to_detail(record, self._latest_job(document_id))

    def _latest_job(self, document_id: int) -> DocumentIngestionJob | None:
        """
        The document's most recent ingestion attempt, which is where the
        content identity lives. Reading it here rather than recomputing a
        checksum keeps a detail view a read, not a full file hash.
        """

        return (
            self._session.query(DocumentIngestionJob)
            .filter(DocumentIngestionJob.document_id == document_id)
            .order_by(DocumentIngestionJob.id.desc())
            .first()
        )

    @staticmethod
    def _apply_filters(
        statement: "Query[DocumentRecord]", query: DocumentQuery
    ) -> "Query[DocumentRecord]":
        if query.project_id is not None:
            statement = statement.filter(
                DocumentRecord.project_id == query.project_id
            )

        if query.scope is not None:
            statement = statement.filter(
                DocumentRecord.scope == query.scope
            )

        if query.document_format is not None:
            statement = statement.filter(
                DocumentRecord.file_format
                == query.document_format.value
            )

        if query.category is not None:
            statement = statement.filter(
                DocumentRecord.category == query.category.value
            )

        if query.search is not None:
            pattern = f"%{_escape_like(query.search.value)}%"

            statement = statement.filter(
                or_(
                    *(
                        column.ilike(pattern, escape="\\")
                        for column in _SEARCHED_COLUMNS
                    )
                )
            )

        return statement

    @staticmethod
    def _apply_order(
        statement: "Query[DocumentRecord]", query: DocumentQuery
    ) -> "Query[DocumentRecord]":
        column = _SORT_COLUMNS[query.sort_by]

        ordered = (
            column.asc()
            if query.direction is SortDirection.ASCENDING
            else column.desc()
        )

        # `id` breaks ties so paging is stable across reads.
        return statement.order_by(ordered, DocumentRecord.id.asc())

    @staticmethod
    def _to_summary(record: DocumentRecord) -> DocumentSummary:
        return DocumentSummary(
            document_id=record.id,
            project_id=record.project_id,
            project_name=record.project_name,
            filename=record.filename,
            document_format=DocumentFormat(record.file_format.value),
            category=DocumentCategory(record.category.value),
            revision=record.revision,
            scope=record.scope,
            uploaded_at=record.uploaded_at,
        )

    @staticmethod
    def _to_detail(
        record: DocumentRecord,
        job: DocumentIngestionJob | None,
    ) -> DocumentDetail:
        return DocumentDetail(
            document_id=record.id,
            project_id=record.project_id,
            project_name=record.project_name,
            filename=record.filename,
            document_format=DocumentFormat(record.file_format.value),
            category=DocumentCategory(record.category.value),
            revision=record.revision,
            scope=record.scope,
            uploaded_at=record.uploaded_at,
            content_checksum=None if job is None else job.content_checksum,
            checksum_algorithm=(
                None if job is None else job.content_checksum_algorithm
            ),
            size_bytes=None if job is None else job.content_size_bytes,
            # Resolved by the service through the content port; the
            # registry cannot see storage and does not guess.
            content_available=False,
            ingestion_state=(
                None if job is None else job.state.value
            ),
            ingestion_outcome=(
                None
                if job is None or job.outcome is None
                else job.outcome.value
            ),
        )
