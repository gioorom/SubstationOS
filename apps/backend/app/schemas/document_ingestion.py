from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.document_ingestion.ingestion_lifecycle import IngestionState
from app.domain.document_ingestion.ingestion_models import (
    IngestionFailureCode,
    IngestionOutcome,
)
from app.domain.project.project_document_scope import DocumentScope

# --- Request -----------------------------------------------------------


class IngestDocumentRequestBody(BaseModel):
    """
    A request to ingest one already-uploaded document.

    Carries **only** the document id. There is deliberately no field for a
    lifecycle state, an outcome, a pipeline version or a format override:
    the lifecycle decides the first, the pipeline the second and third,
    and the document repository the fourth. A caller cannot assert what
    ingestion concluded.
    """

    document_id: int


# --- Response ------------------------------------------------------------


class IngestionFailureRead(BaseModel):
    code: IngestionFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class DocumentContentIdentityRead(BaseModel):
    """The bytes' identity at ingestion time (Milestone 25.2).

    Identical checksums across two documents are reported and nothing is
    concluded from them - this is identity, not deduplication."""

    storage_reference: str
    checksum_algorithm: str
    checksum: str
    size_bytes: int

    model_config = ConfigDict(from_attributes=True)


class DocumentFormatRead(BaseModel):
    """What the classifier decided and on what evidence (Milestone 25.2).

    ``stored_format`` is what the document record said, kept beside
    ``detected_format`` so a divergence is visible rather than silently
    resolved in favour of either."""

    detected_format: str
    decided_by: str
    stored_format: str
    disagreeing_evidence: tuple[str, ...]
    matches_stored_format: bool

    model_config = ConfigDict(from_attributes=True)


class IngestedDocumentSnapshotRead(BaseModel):
    """The document's facts **as they stood at ingestion time** - a
    snapshot, not a live read, so a job stays explainable after the
    document changes."""

    document_id: int
    project_id: int | None
    title: str
    document_format: str
    document_category: str
    revision: str
    scope: DocumentScope | None
    # ``null`` on a job that failed before the step ran, and on every job
    # recorded before Milestone 25.2 existed.
    content: DocumentContentIdentityRead | None = None
    format: DocumentFormatRead | None = None

    model_config = ConfigDict(from_attributes=True)


class IngestionJobRead(BaseModel):
    """
    One ingestion job's full, auditable record.

    ``outcome`` is ``null`` until the job reaches a terminal state, and
    ``ready_for_extraction`` is the one question a future extraction
    milestone asks of it.
    """

    id: int | None
    project_id: int | None
    document_id: int
    state: IngestionState
    outcome: IngestionOutcome | None
    pipeline_version: str
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    failure: IngestionFailureRead | None
    document: IngestedDocumentSnapshotRead | None
    ready_for_extraction: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, job) -> "IngestionJobRead":
        return cls(
            id=job.id,
            project_id=job.project_id,
            document_id=job.document_id,
            state=job.state,
            outcome=job.outcome,
            pipeline_version=job.pipeline_version,
            attempt_count=job.attempt_count,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            failure=(
                None
                if job.failure is None
                else IngestionFailureRead.model_validate(job.failure)
            ),
            document=(
                None
                if job.document is None
                else IngestedDocumentSnapshotRead.model_validate(job.document)
            ),
            ready_for_extraction=job.is_ready_for_extraction,
        )
