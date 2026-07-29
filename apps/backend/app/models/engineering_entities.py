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
from app.domain.engineering_entities.entity_models import (
    EntityStatus,
    EntityType,
)
from app.domain.engineering_evidence.evidence_models import EvidenceType


class EngineeringEntitySetRecord(Base):
    """
    One resolution over one evidence source (Milestone 29.1).

    Stored **independently of engineering evidence**, which it never
    modifies, and of the Knowledge Graph, which this milestone does not
    write at all.

    The four provenance columns - document, checksum, extraction policy,
    resolution policy - keep a historical set explainable: which
    document, which bytes, which rules found the observations, and which
    rules grouped them.
    """

    __tablename__ = "engineering_entity_sets"

    __table_args__ = (
        # The idempotency backstop. One set per document per evidence
        # source per resolution policy: re-resolving cannot produce a
        # second row whatever the caller does, while new evidence (a new
        # checksum) or new rules (a new policy version) is a new row
        # alongside - never over - the old one.
        UniqueConstraint(
            "document_id",
            "content_checksum",
            "resolution_policy_version",
            name="uq_engineering_entity_set_source_policy",
        ),
        Index(
            "ix_engineering_entity_sets_document_created",
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

    extraction_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    resolution_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    entity_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    entities: Mapped[list["EngineeringEntityRecord"]] = relationship(
        "EngineeringEntityRecord",
        back_populates="entity_set",
        cascade="all, delete-orphan",
        order_by="EngineeringEntityRecord.id",
    )


class EngineeringEntityRecord(Base):
    """
    One deterministic grouping of observations.

    ## What has no column here, deliberately

    No ``feeds``, no ``protects``, no ``bay_id``, no ``parent_entity_id``,
    no ``rated_voltage``. An entity says "these observations refer to one
    object"; saying what that object *does*, what it *belongs to*, or
    what its *properties* are would be reasoning, and this milestone
    performs none. An architecture test asserts these columns stay
    absent.

    Nor is there an ``equipment_type``: deciding that ``T1`` names a
    transformer is a classification needing a reviewed rule and a
    governed vocabulary.
    """

    __tablename__ = "engineering_entities"

    __table_args__ = (
        UniqueConstraint(
            "entity_set_id",
            "entity_key",
            name="uq_engineering_entity_key",
        ),
        # "Where has this designation been resolved?" - the read the
        # milestone that populates the graph will perform.
        Index(
            "ix_engineering_entities_designation",
            "designation_normalized",
        ),
        Index(
            "ix_engineering_entities_type_status",
            "entity_type",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    entity_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_entity_sets.id"),
        nullable=False,
        index=True,
    )

    entity_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[EntityType] = mapped_column(
        SqlEnum(EntityType),
        nullable=False,
    )

    status: Mapped[EntityStatus] = mapped_column(
        SqlEnum(EntityStatus),
        nullable=False,
    )

    entity_version: Mapped[str] = mapped_column(String(20), nullable=False)

    resolution_rule_id: Mapped[str] = mapped_column(
        String(60), nullable=False
    )

    resolution_rule_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    # --- Typed values -------------------------------------------------

    designation_normalized: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

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

    entity_set: Mapped["EngineeringEntitySetRecord"] = relationship(
        "EngineeringEntitySetRecord",
        back_populates="entities",
    )

    evidence: Mapped[list["EngineeringEntityEvidenceRecord"]] = relationship(
        "EngineeringEntityEvidenceRecord",
        back_populates="entity",
        cascade="all, delete-orphan",
        order_by="EngineeringEntityEvidenceRecord.id",
    )


class EngineeringEntityEvidenceRecord(Base):
    """
    One contributing observation.

    ``evidence_key`` is the pointer to the authoritative evidence record,
    which carries the full character-level provenance. What is stored
    here is the **location** - page, paragraph, line, token range - so an
    entity can be read and audited without a second lookup, while the
    evidence item remains the single account of exactly which characters
    were read.

    An entity with no row here cannot exist: an entity citing no evidence
    is an assertion, not a hypothesis, and validation refuses it before
    storage.
    """

    __tablename__ = "engineering_entity_evidence"

    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "evidence_key",
            name="uq_engineering_entity_evidence_key",
        ),
        Index(
            "ix_engineering_entity_evidence_key",
            "evidence_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_entities.id"),
        nullable=False,
        index=True,
    )

    evidence_key: Mapped[str] = mapped_column(String(64), nullable=False)

    evidence_type: Mapped[EvidenceType] = mapped_column(
        SqlEnum(EvidenceType),
        nullable=False,
    )

    observed_text: Mapped[str] = mapped_column(Text, nullable=False)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    token_start: Mapped[int] = mapped_column(Integer, nullable=False)

    token_end: Mapped[int] = mapped_column(Integer, nullable=False)

    entity: Mapped["EngineeringEntityRecord"] = relationship(
        "EngineeringEntityRecord",
        back_populates="evidence",
    )
