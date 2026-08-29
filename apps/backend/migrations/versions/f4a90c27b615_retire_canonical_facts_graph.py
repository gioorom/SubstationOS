"""retire the Canonical Facts graph-shaped projection

EPIC 31.4: drops the seven tables of the Canonical Facts graph lineage -
``graph_operation_batches``, ``graph_operations``, ``graph_executions``,
``graph_execution_operation_results``, ``graph_execution_fingerprints``,
``project_graph_nodes`` and ``project_graph_relationships``.

---

## What these tables held

A **graph-shaped projection of Canonical Facts**. An operator built a
`GraphOperationBatch` from a project's approved canonical facts, executed
it, and the execution wrote nodes and relationships into
`project_graph_nodes` / `project_graph_relationships`, each carrying a
free-form JSON `properties` bag.

That projection was the substrate legacy Structured Retrieval matched on,
and therefore the Engineering Engine's knowledge source until EPIC 31.2.

## Why they go now

Three milestones removed every consumer:

- **EPIC 31.2** moved the Engineering Engine onto Governed Structured
  Retrieval over the Governed Knowledge Graph.
- **EPIC 31.3** removed the last compatibility adapter, so no governed
  module speaks the legacy vocabulary.
- **EPIC 31.4** (this one) withdrew the twenty HTTP routes that were the
  only remaining readers and writers.

`ADR-0028` records the decision and the evidence.

## The data: derived, and reconstructable

**Every row in these seven tables is derived.** Nodes and relationships
are a projection of `canonical_facts`; operations and batches are the
instructions that produced them; executions and fingerprints are the
record of running them.

`canonical_facts`, `proposed_claims`, `review_candidates` and
`review_history_events` are **not** dropped. Those hold the
human-authored claims and the review history the projection was computed
*from*, and they keep their own API. Nothing unique to an engineer is
lost here - what is dropped is the computed shape, not the input.

## Before upgrading: keeping the rows

The projection cannot be rebuilt after this migration, because the code
that built it is deleted too. An operator who wants the rows as a
historical artefact exports them first:

```sql
-- Run against the database before `alembic upgrade head`.
.mode csv
.once legacy_project_graph_nodes.csv
SELECT * FROM project_graph_nodes;
.once legacy_project_graph_relationships.csv
SELECT * FROM project_graph_relationships;
.once legacy_graph_executions.csv
SELECT * FROM graph_executions;
.once legacy_graph_operations.csv
SELECT * FROM graph_operations;
.once legacy_graph_operation_batches.csv
SELECT * FROM graph_operation_batches;
.once legacy_graph_execution_operation_results.csv
SELECT * FROM graph_execution_operation_results;
.once legacy_graph_execution_fingerprints.csv
SELECT * FROM graph_execution_fingerprints;
```

They are exported as a historical artefact, **not** as something to load
back into governed knowledge. The Governed Knowledge Graph admits only
statements a named engineer approved through Human Review; loading a
legacy projection into it would fabricate the governance that makes it
trustworthy, which ADR-0004 exists to forbid. `canonical_facts` survives
untouched, so the engineering claims themselves remain readable.

## Rollback

`downgrade()` recreates all seven tables, **empty**, with their original
columns, indexes, constraints and foreign keys - so a downgraded schema
matches what the previous revision expected and any code restored
alongside it will run.

It does **not** restore rows, and cannot. Stated here rather than
discovered: rolling back returns the *shape*, never the contents. A
deployment that may want the rows takes the export above first.

## Fresh installations

A database created from scratch at this revision never has these tables:
the baseline creates them and this migration drops them, which is the
cost of not editing an applied migration.

Revision ID: f4a90c27b615
Revises: e28b91f4c073
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a90c27b615"
down_revision: Union[str, None] = "e28b91f4c073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drops the projection, dependants first.

    The order is dictated by the foreign keys, not by preference:
    fingerprints and operation results point at executions; nodes and
    relationships point at executions; operations point at batches;
    executions point at batches. Dropping a parent first would fail on
    any engine that enforces the constraint.
    """

    op.drop_table("graph_execution_fingerprints")
    op.drop_table("graph_execution_operation_results")
    op.drop_table("project_graph_relationships")
    op.drop_table("project_graph_nodes")
    op.drop_table("graph_operations")
    op.drop_table("graph_executions")
    op.drop_table("graph_operation_batches")


def downgrade() -> None:
    """
    Recreates all seven tables, empty.

    The schema returns; the rows do not, and cannot - see the module
    docstring. This exists so a downgraded database still matches what
    the previous revision's code expects, not so a rollback restores the
    projection's contents.
    """

    op.create_table(
        "graph_operation_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column(
            "scope",
            sa.Enum("PROJECT", "DOCUMENT", name="graphoperationbatchscope"),
            nullable=False,
        ),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_operation_batches_id"),
        "graph_operation_batches",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_operation_batches_project_id"),
        "graph_operation_batches",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_operation_batches_scope_id"),
        "graph_operation_batches",
        ["scope_id"],
        unique=False,
    )

    op.create_table(
        "graph_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("source_fact_id", sa.Integer(), nullable=False),
        sa.Column("entity_project_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_canonical_id", sa.String(length=255), nullable=True),
        sa.Column("attribute", sa.String(length=255), nullable=True),
        sa.Column("value", sa.String(length=500), nullable=True),
        sa.Column("subject_project_id", sa.Integer(), nullable=True),
        sa.Column("subject_entity_type", sa.String(length=80), nullable=True),
        sa.Column(
            "subject_canonical_id", sa.String(length=255), nullable=True
        ),
        sa.Column("relationship_type", sa.String(length=255), nullable=True),
        sa.Column("object_project_id", sa.Integer(), nullable=True),
        sa.Column("object_entity_type", sa.String(length=80), nullable=True),
        sa.Column("object_canonical_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["graph_operation_batches.id"]
        ),
        sa.ForeignKeyConstraint(["source_fact_id"], ["canonical_facts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_operations_batch_id"),
        "graph_operations",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_operations_id"),
        "graph_operations",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_operations_source_fact_id"),
        "graph_operations",
        ["source_fact_id"],
        unique=False,
    )

    op.create_table(
        "graph_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("batch_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SUCCEEDED",
                "FAILED",
                name="graphexecutionstatus",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("failure_type", sa.String(length=255), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["graph_operation_batches.id"]
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_executions_batch_fingerprint"),
        "graph_executions",
        ["batch_fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_executions_batch_id"),
        "graph_executions",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_executions_id"),
        "graph_executions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_executions_project_id"),
        "graph_executions",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "graph_execution_operation_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["graph_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_execution_operation_results_execution_id"),
        "graph_execution_operation_results",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_execution_operation_results_id"),
        "graph_execution_operation_results",
        ["id"],
        unique=False,
    )

    op.create_table(
        "graph_execution_fingerprints",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["graph_executions.id"]),
        sa.PrimaryKeyConstraint("fingerprint"),
        sa.UniqueConstraint("execution_id"),
    )

    op.create_table(
        "project_graph_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("canonical_id", sa.String(length=255), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_by_execution_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_execution_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_execution_id"], ["graph_executions.id"]
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["updated_by_execution_id"], ["graph_executions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "entity_type",
            "canonical_id",
            name="uq_project_graph_node_natural_key",
        ),
    )
    op.create_index(
        op.f("ix_project_graph_nodes_id"),
        "project_graph_nodes",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_graph_nodes_project_id"),
        "project_graph_nodes",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "project_graph_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_entity_type", sa.String(length=80), nullable=False),
        sa.Column(
            "source_canonical_id", sa.String(length=255), nullable=False
        ),
        sa.Column("relationship_type", sa.String(length=255), nullable=False),
        sa.Column("target_entity_type", sa.String(length=80), nullable=False),
        sa.Column(
            "target_canonical_id", sa.String(length=255), nullable=False
        ),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_by_execution_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_execution_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_execution_id"], ["graph_executions.id"]
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["updated_by_execution_id"], ["graph_executions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "source_entity_type",
            "source_canonical_id",
            "relationship_type",
            "target_entity_type",
            "target_canonical_id",
            name="uq_project_graph_relationship_natural_key",
        ),
    )
    op.create_index(
        op.f("ix_project_graph_relationships_id"),
        "project_graph_relationships",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_graph_relationships_project_id"),
        "project_graph_relationships",
        ["project_id"],
        unique=False,
    )
