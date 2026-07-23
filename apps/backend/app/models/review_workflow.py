from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.review_workflow.review_status import ReviewStatus


class ReviewCandidateRecord(Base):
    """
    Persistence model for one Review Candidate (Milestone 10.1 - Review
    Workflow). Lives in its own table, separate from ``proposed_claims``
    and ``engineering_index_entries``: Review Workflow references a
    Proposed Claim by id, it never writes into Proposed Claims or the
    Engineering Index, and neither stays free of any review-state column
    (ADR-0002, extended to the Proposed Claims layer by Milestone 10.1).
    """

    __tablename__ = "review_candidates"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    proposed_claim_id: Mapped[int] = mapped_column(
        ForeignKey("proposed_claims.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(ReviewStatus),
        nullable=False,
        default=ReviewStatus.PENDING,
        index=True,
    )

    review_comment: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ReviewHistoryEventRecord(Base):
    """
    Persistence model for one immutable Review History ledger entry.
    Append-only by convention: nothing in this bounded context ever
    issues an ``UPDATE`` or ``DELETE`` against this table.
    """

    __tablename__ = "review_history_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    review_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("review_candidates.id"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(ReviewStatus),
        nullable=False,
    )

    to_status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(ReviewStatus),
        nullable=False,
    )

    reviewed_by: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
