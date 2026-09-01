from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)


class EngineeringEvidenceSetRecord(Base):
    """
    One extraction over one canonical source (Milestone 28.1).

    Stored **independently of canonical text and of the Knowledge
    Graph**, and modifying neither. The four provenance columns -
    document, checksum, segmentation version, policy version - are what
    keep a historical set explainable years later.
    """

    __tablename__ = "engineering_evidence_sets"

    __table_args__ = (
        # The idempotency backstop, and the whole reuse rule in one
        # line: one artifact per deterministic identity per document.
        # Re-deriving the same computation cannot produce a second row,
        # while any change upstream or in this stage's own contract is a
        # different identity and therefore a new row alongside - never
        # over - the old one.
        UniqueConstraint(
            "document_id",
            "artifact_identity",
            name="uq_engineering_evidence_set_artifact_identity",
        ),
        Index(
            "ix_engineering_evidence_sets_document_created",
            "document_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )

    content_checksum: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    segmentation_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    extraction_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


    # The deterministic identity of this artifact, and of the artifact it
    # was derived from. Together they are what makes reuse a provable
    # claim rather than a guess: a change anywhere upstream changes the
    # upstream identity, which changes this one.
    #
    # Nullable for one reason only: rows stored before the identity chain
    # existed. Their identity cannot be reconstructed from anything
    # durable, so it stays unknown rather than guessed, and an unknown
    # row can never satisfy a reuse lookup.
    artifact_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    upstream_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    evidence: Mapped[list["EngineeringEvidenceRecord"]] = relationship(
        "EngineeringEvidenceRecord",
        back_populates="evidence_set",
        cascade="all, delete-orphan",
        order_by="EngineeringEvidenceRecord.id",
    )


class EngineeringEvidenceRecord(Base):
    """
    One observation.

    ## The value columns

    ``quantity_value`` is `Numeric`, **never** `Float`: a rated voltage
    that reads back as 20.000000000000004 kV would be a defect nobody
    could explain to an engineer, and binary floating point makes that
    inevitable. SQLAlchemy returns `Decimal` from this column, which is
    what the domain holds.

    ``quantity_*`` and ``designation_normalized`` are separate typed
    columns rather than one ``value`` string, because a voltage and a
    designation are different kinds of thing and a single text column
    would force every consumer to re-parse what the extractor already
    knew. Exactly one group is populated, decided by ``evidence_type``.

    ## What has no column here, deliberately

    No ``entity_id``, no ``equipment_type``, no ``belongs_to``, no
    ``related_evidence_id``. Evidence is an observation about a document;
    attaching it to an entity or to another observation is a judgement,
    and this milestone makes none. An architecture test asserts these
    columns stay absent.
    """

    __tablename__ = "engineering_evidence"

    __table_args__ = (
        # The deterministic evidence key makes a duplicate observation
        # impossible to insert within one set, whatever the caller does.
        UniqueConstraint(
            "evidence_set_id",
            "evidence_key",
            name="uq_engineering_evidence_key",
        ),
        # "Where has this designation been observed?" - the read a future
        # entity-resolution milestone performs.
        Index(
            "ix_engineering_evidence_designation",
            "designation_normalized",
        ),
        Index(
            "ix_engineering_evidence_type_status",
            "evidence_type",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    evidence_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_evidence_sets.id"),
        nullable=False,
        index=True,
    )

    evidence_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    evidence_type: Mapped[EvidenceType] = mapped_column(
        SqlEnum(EvidenceType),
        nullable=False,
    )

    status: Mapped[EvidenceStatus] = mapped_column(
        SqlEnum(EvidenceStatus),
        nullable=False,
    )

    observed_text: Mapped[str] = mapped_column(Text, nullable=False)

    rule_id: Mapped[str] = mapped_column(String(60), nullable=False)

    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Typed values -------------------------------------------------

    quantity_value: Mapped[object | None] = mapped_column(
        Numeric(28, 6),
        nullable=True,
    )

    quantity_unit: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    quantity_base_value: Mapped[object | None] = mapped_column(
        Numeric(28, 6),
        nullable=True,
    )

    quantity_base_unit: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    designation_normalized: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    # --- Provenance ----------------------------------------------------

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    section_index: Mapped[int] = mapped_column(Integer, nullable=False)

    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)

    block_reading_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    token_start: Mapped[int] = mapped_column(Integer, nullable=False)

    token_end: Mapped[int] = mapped_column(Integer, nullable=False)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    evidence_set: Mapped["EngineeringEvidenceSetRecord"] = relationship(
        "EngineeringEvidenceSetRecord",
        back_populates="evidence",
    )

    spans: Mapped[list["EngineeringEvidenceSpanRecord"]] = relationship(
        "EngineeringEvidenceSpanRecord",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="EngineeringEvidenceSpanRecord.id",
    )


class EngineeringEvidenceSpanRecord(Base):
    """
    One canonical span an observation drew characters from.

    A child table rather than three columns on the evidence row, because
    an observation may legitimately draw on **more than one span** - "20"
    and "kV" in different styles. Flattening that into a single range
    would describe characters that exist in neither span.
    """

    __tablename__ = "engineering_evidence_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_evidence.id"),
        nullable=False,
        index=True,
    )

    span_reading_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    character_start: Mapped[int] = mapped_column(Integer, nullable=False)

    character_end: Mapped[int] = mapped_column(Integer, nullable=False)

    evidence: Mapped["EngineeringEvidenceRecord"] = relationship(
        "EngineeringEvidenceRecord",
        back_populates="spans",
    )
