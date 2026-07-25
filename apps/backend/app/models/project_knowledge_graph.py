from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecutionStatus,
)

# Named app.models.project_knowledge_graph, not app.models.knowledge_graph,
# to avoid colliding with the pre-existing, unrelated legacy module of
# that name (app/models/knowledge_graph.py - the ungoverned
# ProjectEntity/EntityRelation tables this milestone does not touch,
# per its explicit "do not modify" scope).


class ProjectGraphNodeRecord(Base):
    """
    Persistence model for one Project Knowledge Graph node. Natural key
    is ``(project_id, entity_type, canonical_id)`` - the same triple a
    ``GraphEntityId`` decomposes into. ``id`` is a storage detail only,
    never referenced by ``ProjectGraphRelationshipRecord``, which
    stores the same triple directly instead (see that record's
    docstring for why).
    """

    __tablename__ = "project_graph_nodes"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "entity_type",
            "canonical_id",
            name="uq_project_graph_node_natural_key",
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

    entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    canonical_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    properties: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_by_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=True,
    )

    updated_by_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class ProjectGraphRelationshipRecord(Base):
    """
    Persistence model for one Project Knowledge Graph relationship.
    Natural key is
    ``(project_id, source_entity_type, source_canonical_id,
    relationship_type, target_entity_type, target_canonical_id)``.

    Endpoints are stored as their own ``entity_type``/``canonical_id``
    pairs rather than a foreign key to ``ProjectGraphNodeRecord.id``:
    this keeps the natural-key uniqueness constraint self-contained
    (no join needed to enforce or query it) and matches
    ``GraphOperationRecord``'s own established convention of storing
    entity identity as flattened columns, not a surrogate-key
    reference.
    """

    __tablename__ = "project_graph_relationships"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "source_entity_type",
            "source_canonical_id",
            "relationship_type",
            "target_entity_type",
            "target_canonical_id",
            name="uq_project_graph_relationship_natural_key",
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

    source_entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    source_canonical_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    relationship_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    target_entity_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    target_canonical_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    properties: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_by_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=True,
    )

    updated_by_execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class GraphExecutionRecord(Base):
    """
    Persistence model for one ``GraphExecution`` audit record. Carries
    no copy of any ``CanonicalFact``/``ProposedClaim`` content -
    ``batch_id`` is the only reference needed to trace an execution
    back to what it executed.
    """

    __tablename__ = "graph_executions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("graph_operation_batches.id"),
        nullable=False,
        index=True,
    )

    batch_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[GraphExecutionStatus] = mapped_column(
        SqlEnum(GraphExecutionStatus),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    operation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    failure_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    failure_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class GraphExecutionOperationResultRecord(Base):
    """Persistence model for one per-operation outcome belonging to a
    ``GraphExecutionRecord``."""

    __tablename__ = "graph_execution_operation_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    succeeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class GraphExecutionFingerprintRecord(Base):
    """
    Maps a batch content fingerprint to the ``GraphExecution`` that
    first succeeded with that content. Only ever contains fingerprints
    of ``SUCCEEDED`` executions - a failed attempt never inserts a row
    here, which is what allows a later retry of the same (or a
    different, identically-shaped) batch to still succeed. The plain,
    unconditional uniqueness constraint on ``fingerprint`` is therefore
    correct without needing a partial/filtered index: enforced by the
    database, not only by the service's own existence check.
    """

    __tablename__ = "graph_execution_fingerprints"

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("graph_executions.id"),
        nullable=False,
        unique=True,
    )
