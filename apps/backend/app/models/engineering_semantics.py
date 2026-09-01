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
from app.domain.engineering_semantics.semantic_models import (
    SemanticAmbiguityReason,
    SemanticStatementStatus,
)
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)


class EngineeringSemanticSetRecord(Base):
    """
    One interpretation over one fact source (Milestone 30.1).

    Stored **independently of facts, entities, evidence and the
    Knowledge Graph**, and modifying none of them.

    The five provenance columns identify the whole upstream chain: which
    document, which bytes, which resolution policy produced the entities,
    which construction policy produced the facts, and which semantic
    policy interpreted them.
    """

    __tablename__ = "engineering_semantic_sets"

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
            name="uq_engineering_semantic_set_artifact_identity",
        ),
        Index(
            "ix_engineering_semantic_sets_document_created",
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

    # Nullable for one reason only: rows stored before this provenance
    # was recorded. Their true extraction policy cannot be reconstructed
    # from anything durable, so it stays unknown rather than guessed -
    # and an unknown row can never satisfy a reuse lookup.
    #
    # A newly interpreted set always has one: interpretation over a
    # fact set of unknown provenance is refused rather than stored.
    extraction_policy_version: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    resolution_policy_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    fact_policy_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    semantic_policy_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    statement_count: Mapped[int] = mapped_column(Integer, nullable=False)

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

    statements: Mapped[list["EngineeringSemanticStatementRecord"]] = (
        relationship(
            "EngineeringSemanticStatementRecord",
            back_populates="semantic_set",
            cascade="all, delete-orphan",
            order_by="EngineeringSemanticStatementRecord.id",
        )
    )

    diagnostics: Mapped[
        list["SemanticInterpretationDiagnosticRecord"]
    ] = relationship(
        "SemanticInterpretationDiagnosticRecord",
        back_populates="semantic_set",
        cascade="all, delete-orphan",
        order_by="SemanticInterpretationDiagnosticRecord.id",
    )


class EngineeringSemanticStatementRecord(Base):
    """
    One interpreted engineering meaning.

    ## What has no column here, deliberately

    No ``value``, no ``unit``, no ``equipment_type``, no ``confidence``.
    A statement says *what the association means*; the figure itself
    lives on the quantity entity, and copying it here would create a
    second source of truth for a rated value - the worst possible thing
    to have two of.

    Entities and facts are referenced by their **deterministic keys**,
    not by foreign key, for the same reason facts reference entities that
    way: a re-resolution or re-construction upstream produces new sets,
    and a foreign key would either block that or cascade a historical
    interpretation into nothing.
    """

    __tablename__ = "engineering_semantic_statements"

    __table_args__ = (
        UniqueConstraint(
            "semantic_set_id",
            "statement_key",
            name="uq_engineering_semantic_statement_key",
        ),
        # "What is known about this entity?" - the read the milestone
        # that populates the graph performs.
        Index(
            "ix_engineering_semantic_statements_subject",
            "subject_entity_key",
        ),
        Index(
            "ix_engineering_semantic_statements_type_status",
            "statement_type",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    semantic_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_semantic_sets.id"),
        nullable=False,
        index=True,
    )

    statement_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    statement_type: Mapped[SemanticStatementType] = mapped_column(
        SqlEnum(SemanticStatementType),
        nullable=False,
    )

    subject_entity_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    object_entity_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    status: Mapped[SemanticStatementStatus] = mapped_column(
        SqlEnum(SemanticStatementStatus),
        nullable=False,
    )

    semantic_contract_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    semantic_rule_id: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    semantic_rule_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    semantic_set: Mapped["EngineeringSemanticSetRecord"] = relationship(
        "EngineeringSemanticSetRecord",
        back_populates="statements",
    )

    support: Mapped[list["SemanticStatementSupportRecord"]] = relationship(
        "SemanticStatementSupportRecord",
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="SemanticStatementSupportRecord.id",
    )


class SemanticStatementSupportRecord(Base):
    """
    One fact supporting a statement.

    Only the fact **key** is stored. The association, its own support and
    the whole provenance chain beneath it live on the fact; duplicating
    any of that here would create a third copy of where a thing was seen.

    A statement with no row here cannot exist: validation refuses it
    before storage, because meaning resting on nothing traceable is an
    assertion.
    """

    __tablename__ = "engineering_semantic_statement_support"

    __table_args__ = (
        UniqueConstraint(
            "statement_id",
            "fact_key",
            name="uq_engineering_semantic_support",
        ),
        Index(
            "ix_engineering_semantic_support_fact",
            "fact_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    statement_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_semantic_statements.id"),
        nullable=False,
        index=True,
    )

    fact_key: Mapped[str] = mapped_column(String(64), nullable=False)

    statement: Mapped["EngineeringSemanticStatementRecord"] = relationship(
        "EngineeringSemanticStatementRecord",
        back_populates="support",
    )


class SemanticInterpretationDiagnosticRecord(Base):
    """
    A subject that had candidates and received no statement.

    **In its own table on purpose.** An undecided meaning must not be
    readable as interpreted knowledge, and the surest way to guarantee
    that is to make it structurally invisible to anyone querying
    statements. It has no object and no statement-type column, because
    which quantity carries the meaning is exactly what could not be
    decided.
    """

    __tablename__ = "engineering_semantic_diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    semantic_set_id: Mapped[int] = mapped_column(
        ForeignKey("engineering_semantic_sets.id"),
        nullable=False,
        index=True,
    )

    reason: Mapped[SemanticAmbiguityReason] = mapped_column(
        SqlEnum(SemanticAmbiguityReason),
        nullable=False,
    )

    subject_entity_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    # The competing facts, as a readable list - for a human deciding what
    # the document meant, not for a query to join on.
    candidate_fact_keys: Mapped[str] = mapped_column(Text, nullable=False)

    semantic_set: Mapped["EngineeringSemanticSetRecord"] = relationship(
        "EngineeringSemanticSetRecord",
        back_populates="diagnostics",
    )
