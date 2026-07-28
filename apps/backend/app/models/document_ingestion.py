from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.document_ingestion.ingestion_lifecycle import IngestionState
from app.domain.document_ingestion.ingestion_models import (
    IngestionFailureCode,
    IngestionOutcome,
)
from app.domain.project.project_document_scope import DocumentScope


class DocumentIngestionJob(Base):
    """
    Persistence model for one document ingestion (Milestone 25.1).

    The ``document_*`` columns are a **snapshot** taken at ingestion time,
    not a join onto the live document. A document's revision or category
    can change afterwards, and a job that silently started describing the
    current document would make its own recorded outcome unexplainable.

    Deliberately no uniqueness constraint on ``document_id``: a document
    is legitimately ingested more than once over its life, and the
    accumulated jobs are its audit trail. What must never happen - two
    jobs *in flight* at once - is enforced by the active-job check in the
    service, which is a rule about state rather than about rows and could
    not be expressed as a column constraint without encoding the lifecycle
    into the schema.
    """

    __tablename__ = "document_ingestion_jobs"

    __table_args__ = (
        # The two reads this table exists to serve: "is anything in flight
        # for this document?" and "what has this project ingested?".
        Index(
            "ix_document_ingestion_jobs_document_state",
            "document_id",
            "state",
        ),
        Index(
            "ix_document_ingestion_jobs_project_state",
            "project_id",
            "state",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    state: Mapped[IngestionState] = mapped_column(
        SqlEnum(IngestionState),
        nullable=False,
        default=IngestionState.UPLOADED,
    )

    outcome: Mapped[IngestionOutcome | None] = mapped_column(
        SqlEnum(IngestionOutcome),
        nullable=True,
    )

    pipeline_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    failure_code: Mapped[IngestionFailureCode | None] = mapped_column(
        SqlEnum(IngestionFailureCode),
        nullable=True,
    )

    failure_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    failure_detail: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # --- Document snapshot -------------------------------------------

    document_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    document_format: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    document_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    document_revision: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    document_scope: Mapped[DocumentScope | None] = mapped_column(
        SqlEnum(DocumentScope),
        nullable=True,
    )

    # --- Content identity and format classification (Milestone 25.2) ---
    #
    # All nullable: a job that failed before the relevant step ran carries
    # none of them, and so does every job recorded before 25.2 existed. A
    # historical job stays readable and keeps meaning exactly what it
    # meant when it was written.

    content_storage_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    content_checksum_algorithm: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    content_checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    content_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    detected_format: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    format_decided_by: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    format_disagreeing_evidence: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # --- Timestamps ---------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
