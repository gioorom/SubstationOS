"""
Persistence for the Governed Knowledge Graph.

Three tables, and they hold a **projection**. Everything in them is
reproducible from `engineering_semantic_statements` and
`engineering_reviews`; dropping them and rebuilding produces identical
content, which is why `clear()` exists here and nowhere else in this
system.

Deliberately absent:

- **No foreign key to the semantic tables.** A re-run replaces a semantic
  set, and a constraint would either block the pipeline or cascade a
  historical projection into nothing. The graph references governed
  artefacts by their deterministic keys, exactly as reviews do.
- **No foreign key to `engineering_reviews` or `users`.** Same reason: the
  projection records the identity of the review that authorised it and
  must stay readable regardless of what happens to either.
- **No free-form property bag.** A node has the fields its kind needs.
  A JSON blob would be the generic property graph this context exists not
  to be, and it would let a quantity acquire a designation.

### Why these table names

`project_graph_nodes` and `project_entities` are already taken, by two
earlier and differently-sourced graph efforts (Milestones 11.1/11.2 and
the legacy path ADR-0009 isolates). `governed_graph_*` names what this
one is: the projection of *governed* knowledge - approved semantics
only. `knowledge_graph.md` states the relationship between the three and
recommends how the older two retire.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class GovernedGraphNodeRecord(Base):
    """One governed engineering concept."""

    __tablename__ = "governed_graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    node_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    """
    SHA-256 over the namespace, the kind and the **entity key**.

    Unique at the database, which is what makes duplicate prevention a
    constraint rather than a convention: promoting the same entity twice
    cannot produce two nodes, whatever the application does.
    """

    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)

    entity_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    """
    Readable, and **never identity**. See `graph_identity` on why using
    this instead would merge two transformers that share a name.
    """

    normalized_value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    """Present on a quantity, `NULL` on an asset."""

    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    retirement_reason: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- Provenance: where this knowledge came from ----------------------

    statement_key: Mapped[str] = mapped_column(String(128), nullable=False)
    document_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    semantic_rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    semantic_rule_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    semantic_contract_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    resolution_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    fact_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    semantic_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    support_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )


class GovernedGraphEdgeRecord(Base):
    """One governed engineering relationship. Never anonymous."""

    __tablename__ = "governed_graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    edge_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    """SHA-256 over the namespace, the kind and the **statement key**."""

    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)

    subject_node_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    object_node_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    retirement_reason: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- Provenance ------------------------------------------------------

    statement_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    """
    Unique: one statement produces at most one edge.

    The constraint that makes re-promotion idempotent at the database
    level rather than only in application code.
    """

    document_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    semantic_rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    semantic_rule_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    semantic_contract_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    resolution_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    fact_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    semantic_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    support_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )


class GovernedGraphGenerationRecord(Base):
    """
    One recomputation of the whole projection. Append-only.

    Incremental promotions do **not** create a generation: a generation
    says "this is the projection as recomputed from scratch, under these
    promotion rules", and promoting one statement recomputes nothing.
    """

    __tablename__ = "governed_graph_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    generation_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )

    trigger: Mapped[str] = mapped_column(String(30), nullable=False)

    promotion_contract_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    node_count: Mapped[int] = mapped_column(Integer, nullable=False)

    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)

    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


#: The query the Workspace and the asset lookups run: current knowledge
#: for one project, by kind.
Index(
    "ix_governed_graph_nodes_project_state",
    GovernedGraphNodeRecord.project_id,
    GovernedGraphNodeRecord.state,
    GovernedGraphNodeRecord.kind,
)

Index(
    "ix_governed_graph_edges_project_state",
    GovernedGraphEdgeRecord.project_id,
    GovernedGraphEdgeRecord.state,
    GovernedGraphEdgeRecord.kind,
)
