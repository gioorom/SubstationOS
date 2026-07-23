from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)
from app.domain.proposed_claims.claim_type import ClaimType


class ProposedClaimRecord(Base):
    """
    Persistence model for one Proposed Claim (Milestone 10.1). Lives in
    its own table, separate from ``engineering_index_entries`` and from
    ``review_candidates``: a claim references Engineering Index entries
    (via ``EvidenceReferenceRecord``) and is referenced *by* a Review
    Candidate, but owns neither's data - no review field lives here
    (ADR-0002-style layer separation, extended to this bounded context).
    """

    __tablename__ = "proposed_claims"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "claim_type",
            "subject",
            "predicate",
            "object",
            name="uq_proposed_claim_natural_key",
        ),
    )

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

    claim_type: Mapped[ClaimType] = mapped_column(
        SqlEnum(ClaimType),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    predicate: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    object: Mapped[str | None] = mapped_column(
        String(255),
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


class EvidenceReferenceRecord(Base):
    """
    Persistence model for one evidence citation belonging to a
    ``ProposedClaimRecord``. ``document_id``/``locator_kind``/
    ``locator_value`` are a snapshot taken from the cited Engineering
    Index entry at claim-creation (or evidence-replacement) time - they
    are not kept in sync if the entry is later rebuilt; replacing the
    claim's evidence is how a stale snapshot gets refreshed.
    """

    __tablename__ = "proposed_claim_evidence"

    __table_args__ = (
        UniqueConstraint(
            "proposed_claim_id",
            "engineering_index_entry_id",
            name="uq_evidence_reference_claim_and_entry",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    proposed_claim_id: Mapped[int] = mapped_column(
        ForeignKey("proposed_claims.id"),
        nullable=False,
        index=True,
    )

    engineering_index_entry_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_index_entries.id"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    locator_kind: Mapped[IndexEntryLocatorKind] = mapped_column(
        SqlEnum(IndexEntryLocatorKind),
        nullable=False,
        default=IndexEntryLocatorKind.PAGE,
    )

    locator_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
