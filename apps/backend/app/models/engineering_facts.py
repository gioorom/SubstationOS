from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    FactStatus,
    SupportRole,
)
from app.domain.engineering_facts.fact_predicates import FactPredicate


class EngineeringFactSetRecord(Base):
    """
    One construction over one entity source (Milestone 29.2).

    Stored **independently of evidence, entities and the Knowledge
    Graph**, and modifying none of them.

    ## Why entities are referenced by key rather than by foreign key

    ``engineering_facts.subject_entity_key`` is a plain string, not a
    foreign key into ``engineering_entities``. That is deliberate: a
    later re-resolution produces a *new* entity set, and a foreign key
    would either block it or cascade a historical fact set into
    nothing. Fact history must survive newer entities, so the reference
    is by the deterministic key - which stays resolvable against the
    entity set the fact records as its source.
    """

    __tablename__ = "engineering_fact_sets"

    __table_args__ = (
        # The idempotency backstop. One set per document per entity
        # source per fact policy: re-running cannot produce a second row,
        # while new entities (a new checksum or resolution policy) or new
        # rules (a new fact policy) is a new row alongside - never over -
        # the old one.
        UniqueConstraint(
            "document_id",
            "content_checksum",
            "resolution_policy_version",
            "fact_policy_version",
            name="uq_engineering_fact_set_source_policy",
        ),
        Index(
            "ix_engineering_fact_sets_document_created",
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

    resolution_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    fact_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    fact_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    facts: Mapped[list["EngineeringFactRecord"]] = relationship(
        "EngineeringFactRecord",
        back_populates="fact_set",
        cascade="all, delete-orphan",
        order_by="EngineeringFactRecord.id",
    )

    diagnostics: Mapped[list["FactConstructionDiagnosticRecord"]] = (
        relationship(
            "FactConstructionDiagnosticRecord",
            back_populates="fact_set",
            cascade="all, delete-orphan",
            order_by="FactConstructionDiagnosticRecord.id",
        )
    )


class EngineeringFactRecord(Base):
    """
    One deterministic association.

    ## What has no column here, deliberately

    No ``role``, no ``property_name``, no ``rated_value``, no
    ``connected_to``, no ``equipment_type``. The predicate column holds a
    closed vocabulary of exactly one member, and
    ``HAS_ASSOCIATED_QUANTITY`` says only that two entities appeared
    together under a declared rule - not that the quantity is a rated
    power, a voltage or a current. Promoting the quantity's evidence type
    into a role is a later milestone with its own rule and its own
    evaluation.

    No entity payload is copied in either: the subject's designation and
    the object's value live on the entity, which stays the single account
    of what each is.
    """

    __tablename__ = "engineering_facts"

    __table_args__ = (
        UniqueConstraint(
            "fact_set_id",
            "fact_key",
            name="uq_engineering_fact_key",
        ),
        # "What is associated with this entity?" - the read a future
        # graph-population milestone performs.
        Index(
            "ix_engineering_facts_subject",
            "subject_entity_key",
        ),
        Index(
            "ix_engineering_facts_object",
            "object_entity_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    fact_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_fact_sets.id"),
        nullable=False,
        index=True,
    )

    fact_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Deliberately not a foreign key - see the set record's docstring.
    subject_entity_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    predicate: Mapped[FactPredicate] = mapped_column(
        SqlEnum(FactPredicate),
        nullable=False,
    )

    object_entity_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    status: Mapped[FactStatus] = mapped_column(
        SqlEnum(FactStatus),
        nullable=False,
    )

    fact_version: Mapped[str] = mapped_column(String(20), nullable=False)

    construction_rule_id: Mapped[str] = mapped_column(
        String(60), nullable=False
    )

    construction_rule_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    fact_set: Mapped["EngineeringFactSetRecord"] = relationship(
        "EngineeringFactSetRecord",
        back_populates="facts",
    )

    support: Mapped[list["EngineeringFactSupportRecord"]] = relationship(
        "EngineeringFactSupportRecord",
        back_populates="fact",
        cascade="all, delete-orphan",
        order_by="EngineeringFactSupportRecord.id",
    )


class EngineeringFactSupportRecord(Base):
    """
    One observation supporting a fact.

    ``evidence_key`` points at the authoritative evidence record, which
    carries the full character-level provenance. The location is stored
    so a fact can be audited without a second lookup - and so the
    same-line rule can be re-checked, which is the only way to tell a
    correct association from a claimed one.

    A fact with no row here cannot exist: validation refuses it before
    storage, because a fact resting on nothing traceable is an assertion.
    """

    __tablename__ = "engineering_fact_support"

    __table_args__ = (
        UniqueConstraint(
            "fact_id",
            "evidence_key",
            "role",
            name="uq_engineering_fact_support",
        ),
        Index(
            "ix_engineering_fact_support_evidence",
            "evidence_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    fact_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_facts.id"),
        nullable=False,
        index=True,
    )

    evidence_key: Mapped[str] = mapped_column(String(64), nullable=False)

    role: Mapped[SupportRole] = mapped_column(
        SqlEnum(SupportRole),
        nullable=False,
    )

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

    fact: Mapped["EngineeringFactRecord"] = relationship(
        "EngineeringFactRecord",
        back_populates="support",
    )


class FactConstructionDiagnosticRecord(Base):
    """
    A line that held candidates and produced no fact.

    **In its own table on purpose.** An ambiguous pairing must not be
    readable as a confirmed association, and the surest way to guarantee
    that is to make it structurally invisible to anyone querying
    ``engineering_facts``. It is not a fact with a softer status; it has
    no subject and no object columns, because which is which is exactly
    what could not be determined.
    """

    __tablename__ = "engineering_fact_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    fact_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_fact_sets.id"),
        nullable=False,
        index=True,
    )

    reason: Mapped[AmbiguityReason] = mapped_column(
        SqlEnum(AmbiguityReason),
        nullable=False,
    )

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # The candidates involved, as a readable list - they are for a human
    # deciding what the line meant, not for a query to join on.
    subject_entity_keys: Mapped[str] = mapped_column(Text, nullable=False)

    object_entity_keys: Mapped[str] = mapped_column(Text, nullable=False)

    fact_set: Mapped["EngineeringFactSetRecord"] = relationship(
        "EngineeringFactSetRecord",
        back_populates="diagnostics",
    )
