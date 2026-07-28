from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.document_ingestion.ingestion_lifecycle import (
    ACTIVE_STATES,
    IngestionState,
)
from app.domain.document_ingestion.ingestion_models import (
    DocumentContentIdentitySnapshot,
    DocumentFormatSnapshot,
    IngestedDocumentSnapshot,
    IngestionFailure,
    IngestionJob,
)
from app.domain.document_ingestion.ingestion_repository import (
    IngestionJobRepository,
)
from app.models.document_ingestion import (
    DocumentIngestionJob as DocumentIngestionJobRecord,
)

_EVIDENCE_SEPARATOR = " | "


class SqlAlchemyIngestionJobRepository(IngestionJobRepository):
    """
    SQLAlchemy adapter for the ``IngestionJobRepository`` port, backed by
    ``app.models.document_ingestion.DocumentIngestionJob``.

    Flattens the job's ``failure`` and ``document`` value objects into
    columns on write and reassembles them on read - the domain keeps its
    nested, typed shape and the table stays a flat, queryable record.

    The content-identity and format columns (Milestone 25.2) are all
    nullable and reassembled only when present, so a job written before
    they existed reads back as a job that carries neither - which is the
    truth about it, not a gap to be filled in.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, job: IngestionJob) -> IngestionJob:
        record = DocumentIngestionJobRecord()
        self._apply(record, job)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def update(self, job: IngestionJob) -> IngestionJob:
        record = self._session.get(DocumentIngestionJobRecord, job.id)

        if record is None:
            raise ValueError(
                f"Ingestion job '{job.id}' cannot be updated: no such row."
            )

        self._apply(record, job)

        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, job_id: int) -> IngestionJob | None:
        record = self._session.get(DocumentIngestionJobRecord, job_id)

        return self._to_domain(record) if record is not None else None

    def list_by_document(self, document_id: int) -> list[IngestionJob]:
        records = (
            self._session.query(DocumentIngestionJobRecord)
            .filter(DocumentIngestionJobRecord.document_id == document_id)
            .order_by(DocumentIngestionJobRecord.id.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def find_active_for_document(
        self, document_id: int
    ) -> IngestionJob | None:
        record = (
            self._session.query(DocumentIngestionJobRecord)
            .filter(
                DocumentIngestionJobRecord.document_id == document_id,
                DocumentIngestionJobRecord.state.in_(tuple(ACTIVE_STATES)),
            )
            .order_by(DocumentIngestionJobRecord.id.asc())
            .first()
        )

        return self._to_domain(record) if record is not None else None

    def list_by_project(self, project_id: int) -> list[IngestionJob]:
        records = (
            self._session.query(DocumentIngestionJobRecord)
            .filter(DocumentIngestionJobRecord.project_id == project_id)
            .order_by(DocumentIngestionJobRecord.id.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    # --- Mapping ------------------------------------------------------

    @staticmethod
    def _apply(
        record: DocumentIngestionJobRecord, job: IngestionJob
    ) -> None:
        record.project_id = job.project_id
        record.document_id = job.document_id
        record.state = job.state
        record.outcome = job.outcome
        record.pipeline_version = job.pipeline_version
        record.attempt_count = job.attempt_count
        record.created_at = job.created_at
        record.updated_at = job.updated_at
        record.completed_at = job.completed_at

        failure = job.failure
        record.failure_code = failure.code if failure is not None else None
        record.failure_message = (
            failure.message if failure is not None else None
        )
        record.failure_detail = failure.detail if failure is not None else None

        document = job.document
        record.document_title = document.title if document is not None else None
        record.document_format = (
            document.document_format if document is not None else None
        )
        record.document_category = (
            document.document_category if document is not None else None
        )
        record.document_revision = (
            document.revision if document is not None else None
        )
        record.document_scope = document.scope if document is not None else None

        content = document.content if document is not None else None
        record.content_storage_reference = (
            content.storage_reference if content is not None else None
        )
        record.content_checksum_algorithm = (
            content.checksum_algorithm if content is not None else None
        )
        record.content_checksum = (
            content.checksum if content is not None else None
        )
        record.content_size_bytes = (
            content.size_bytes if content is not None else None
        )

        document_format = document.format if document is not None else None
        record.detected_format = (
            document_format.detected_format
            if document_format is not None
            else None
        )
        record.format_decided_by = (
            document_format.decided_by if document_format is not None else None
        )
        # Joined on write and split on read. A list column would need a
        # JSON type for something that is only ever displayed, and the
        # separator is one this context's evidence strings never contain.
        record.format_disagreeing_evidence = (
            _EVIDENCE_SEPARATOR.join(document_format.disagreeing_evidence)
            if document_format is not None
            and document_format.disagreeing_evidence
            else None
        )

    @staticmethod
    def _to_domain(record: DocumentIngestionJobRecord) -> IngestionJob:
        failure = (
            IngestionFailure(
                code=record.failure_code,
                message=record.failure_message or "",
                detail=record.failure_detail,
            )
            if record.failure_code is not None
            else None
        )

        document = (
            IngestedDocumentSnapshot(
                document_id=record.document_id,
                project_id=record.project_id,
                title=record.document_title or "",
                document_format=record.document_format or "",
                document_category=record.document_category or "",
                revision=record.document_revision or "",
                scope=record.document_scope,
                content=SqlAlchemyIngestionJobRepository._content_of(record),
                format=SqlAlchemyIngestionJobRepository._format_of(record),
            )
            if record.document_format is not None
            else None
        )

        return IngestionJob(
            id=record.id,
            project_id=record.project_id,
            document_id=record.document_id,
            state=IngestionState(record.state),
            pipeline_version=record.pipeline_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
            attempt_count=record.attempt_count,
            completed_at=record.completed_at,
            outcome=record.outcome,
            failure=failure,
            document=document,
        )

    @staticmethod
    def _content_of(
        record: DocumentIngestionJobRecord,
    ) -> DocumentContentIdentitySnapshot | None:
        if record.content_checksum is None:
            return None

        return DocumentContentIdentitySnapshot(
            storage_reference=record.content_storage_reference or "",
            checksum_algorithm=record.content_checksum_algorithm or "",
            checksum=record.content_checksum,
            size_bytes=record.content_size_bytes or 0,
        )

    @staticmethod
    def _format_of(
        record: DocumentIngestionJobRecord,
    ) -> DocumentFormatSnapshot | None:
        if record.detected_format is None:
            return None

        return DocumentFormatSnapshot(
            detected_format=record.detected_format,
            decided_by=record.format_decided_by or "",
            stored_format=record.document_format or "",
            disagreeing_evidence=tuple(
                record.format_disagreeing_evidence.split(_EVIDENCE_SEPARATOR)
            )
            if record.format_disagreeing_evidence
            else (),
        )
