from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.graph_builder.graph_builder_models import (
    GraphOperationBatchScope,
)


class GraphOperationBatchRecord(Base):
    """
    Persistence model for one Graph Operation Batch (Milestone 11.1 -
    Graph Builder). This is Graph Builder's own output artifact - it is
    not graph persistence: no graph node, edge, or graph database is
    referenced anywhere in this table. Graph Persistence (Milestone
    11.2) is a separate, not-yet-built consumer of what this table
    records, not this table itself.

    ``project_id`` is nullable only for a document-scoped batch built
    from a document with no Canonical Facts yet (see
    ``GraphOperationBatch``'s docstring).
    """

    __tablename__ = "graph_operation_batches"

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

    scope: Mapped[GraphOperationBatchScope] = mapped_column(
        SqlEnum(GraphOperationBatchScope),
        nullable=False,
    )

    scope_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class GraphOperationRecord(Base):
    """
    Persistence model for one operation belonging to a
    ``GraphOperationBatchRecord``. Sparse by operation shape, mirroring
    ``app.models.canonicalization.CanonicalFactRecord``'s own
    sparse-by-``claim_type`` convention:

    - ``CREATE_NODE``/``UPDATE_NODE`` (a ``GraphNodeOperation``)
      populate ``entity_*``, and ``attribute``/``value`` for
      ``UPDATE_NODE`` only.
    - Every other ``kind`` (a ``GraphRelationshipOperation``) populates
      ``subject_*``, ``relationship_type``, and ``object_*``.

    ``kind`` alone discriminates which shape a row is: the
    ``GraphNodeOperationKind`` and ``GraphRelationshipOperationKind``
    value sets never overlap, so no separate category column is needed.

    ``sequence`` records this operation's position in its batch's
    deterministic ordering - row insertion order is not itself a
    queryable guarantee, so ordering is an explicit column, not
    implicit.
    """

    __tablename__ = "graph_operations"

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

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_fact_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_facts.id"),
        nullable=False,
        index=True,
    )

    entity_project_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    entity_canonical_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    attribute: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    value: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    subject_project_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    subject_entity_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    subject_canonical_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    relationship_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    object_project_id: Mapped[int | None] = mapped_column(
        Integer,
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
