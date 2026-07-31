"""retire the legacy knowledge graph

EPIC 31.1: drops ``project_entities`` and ``entity_relations``, the two
tables of the ungoverned Knowledge Graph.

---

## What these tables held, and why they go

They held **LLM-extracted entities and relationships, written straight
from document upload with no review gate**: no reviewer, no review date,
no provenance beyond a source filename, and a bare `confidence` float as
the only trust signal.

[ADR-0004](../../../docs/architecture/adr/0004-reviewed-facts-only-in-queryable-graph.md)
recorded at Architecture Freeze v1.0 that only reviewed, approved facts
may enter a queryable graph, and recorded in the same breath that this
path violated it and was not remediated.
[ADR-0009](../../../docs/architecture/adr/0009-legacy-knowledge-graph-isolation.md)
isolated it and tracked the debt. EPIC 31 built the governed replacement.
This migration is where the violation ends.

**Nothing is lost that this platform considers engineering knowledge.**
By its own definition - `CANONICAL_KNOWLEDGE_PROTOCOL.md` §8, "reviewed,
approved, traceable, versioned" - the rows here were never engineering
knowledge. They were unreviewed extraction output that a query endpoint
had been presenting as though it were.

## Before upgrading: keeping the rows

An operator who wants them keeps them **before** running this, because
this migration cannot: the data is not derivable from anything.

```sql
-- Run against the database before `alembic upgrade head`.
.mode csv
.once legacy_project_entities.csv
SELECT * FROM project_entities;
.once legacy_entity_relations.csv
SELECT * FROM entity_relations;
```

They are exported as a historical artefact, not as something to load
back: there is no governed table to load them into, because the governed
graph accepts only statements an engineer approved.

## Rollback

`downgrade()` recreates both tables, **empty**, with their original
columns, indexes and foreign keys - so a downgraded schema matches what
the previous revision expected and any code restored alongside it will
run.

It does **not** restore rows, and cannot. That is stated here rather
than discovered: rolling back returns the *shape*, never the contents.
A deployment that may need the rows takes the export above first.

## What this migration does not touch

`project_graph_nodes`, `project_graph_relationships`, `graph_executions`,
`graph_operations` and `graph_operation_batches` - the Canonical Facts
lineage from Milestones 11.1/11.2. Those are **still read at runtime** by
Graph Query, Structured Retrieval and the Engineering Engine, so they are
retained and documented rather than retired. See `knowledge_graph.md` §2
and ADR-0025 on why, and on what closing that would require.

Revision ID: e28b91f4c073
Revises: d15a7c3e8b42
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e28b91f4c073"
down_revision: Union[str, None] = "d15a7c3e8b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: The two enums the legacy tables used, recreated verbatim on downgrade.
#: Copied from the removed `app/models/knowledge_graph.py` rather than
#: imported, because that module no longer exists - which is the point of
#: a migration owning its own schema description.
_ENTITY_TYPES = (
    "substation",
    "bay",
    "panel",
    "circuit_breaker",
    "disconnector",
    "transformer",
    "current_transformer",
    "voltage_transformer",
    "protection_relay",
    "cable",
    "signal",
    "document",
    "test",
    "other",
    "busbar",
    "line",
)

_RELATION_TYPES = (
    "contains",
    "connected_to",
    "protects",
    "measures",
    "controls",
    "feeds",
    "documented_in",
    "tested_by",
    "related_to",
)


def upgrade() -> None:
    # Relations first: they carry foreign keys into `project_entities`.
    op.drop_table("entity_relations")
    op.drop_table("project_entities")


def downgrade() -> None:
    """
    Recreates both tables, empty.

    The schema returns; the rows do not, and cannot - see the module
    docstring. This exists so a downgraded database still matches what
    the previous revision's code expects, not so a rollback restores an
    ungoverned graph's contents.
    """

    op.create_table(
        "project_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(*_ENTITY_TYPES, name="entitytype"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_entities_id"), "project_entities", ["id"]
    )
    op.create_index(
        op.f("ix_project_entities_project_id"),
        "project_entities",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_project_entities_name"), "project_entities", ["name"]
    )

    op.create_table(
        "entity_relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_entity_id", sa.Integer(), nullable=False),
        sa.Column("target_entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "relation_type",
            sa.Enum(*_RELATION_TYPES, name="relationtype"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["project_entities.id"]
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["project_entities.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_entity_relations_id"), "entity_relations", ["id"]
    )
