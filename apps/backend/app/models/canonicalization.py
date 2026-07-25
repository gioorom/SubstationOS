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


class CanonicalFactRecord(Base):
    """
    Persistence model for one Canonical Fact (Milestone 11 -
    Canonicalization Pipeline). Lives in its own table, separate from
    ``proposed_claims`` and ``review_candidates``: a fact references
    both by id but owns neither's data, and carries no graph identifier
    or graph edge column - the Project Knowledge Graph (Milestone 11.1)
    is a separate consumer, not this table (ADR-0002's layer
    separation, extended here).

    ``review_candidate_id`` is unique: canonicalizing the same approved
    Review Candidate twice never produces two rows - the chosen
    idempotency strategy is a natural-key uniqueness constraint, backed
    up at the service layer by an explicit existence check
    (``CanonicalFactRepository.get_by_review_candidate``).

    ``predicate_value``/``object_entity_type``/``object_canonical_id``/
    ``object_value`` are sparse by ``claim_type``: a RELATIONSHIP fact
    populates ``predicate_value`` and the ``object_entity_type``/
    ``object_canonical_id`` pair; an ATTRIBUTE fact populates
    ``predicate_value`` and ``object_value``; an EXISTENCE fact
    populates neither.
    """

    __tablename__ = "canonical_facts"

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

    subject_entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    subject_canonical_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    predicate_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    object_entity_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    object_canonical_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    object_value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    proposed_claim_id: Mapped[int] = mapped_column(
        ForeignKey("proposed_claims.id"),
        nullable=False,
        index=True,
    )

    review_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("review_candidates.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    reviewed_by: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class CanonicalFactEvidenceRecord(Base):
    """
    Persistence model for one evidence citation belonging to a
    ``CanonicalFactRecord``. A copy, not a reference, of the source
    ``ProposedClaim``'s own evidence at canonicalization time - mirrors
    ``app.models.proposed_claims.EvidenceReferenceRecord`` exactly,
    against ``canonical_facts`` instead of ``proposed_claims``.
    """

    __tablename__ = "canonical_fact_evidence"

    __table_args__ = (
        UniqueConstraint(
            "canonical_fact_id",
            "engineering_index_entry_id",
            name="uq_canonical_fact_evidence_fact_and_entry",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    canonical_fact_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_facts.id"),
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
