"""add governed knowledge graph

EPIC 31: the projection of governed engineering knowledge - approved,
applicable semantic statements and the entities they relate.

**Purely additive.** Three new tables. No existing table, column or
constraint is touched, and in particular nothing in the engineering
pipeline or in Human Review is modified: the graph reads both and owns
neither.

These tables hold a **derived projection**, and that is what makes them
different from every other table in this schema. Everything in them is
reproducible from `engineering_semantic_statements` and
`engineering_reviews`; dropping them loses nothing that cannot be
rebuilt. It is also why the repository has a `clear()` and nothing else
in this system does.

Deliberately absent:

- **No foreign key anywhere.** Not to the semantic tables (a re-run
  replaces a semantic set, and a constraint would either block the
  pipeline or cascade a historical projection into nothing), not to
  `engineering_reviews`, and not to `users`. The projection references
  governed artefacts by their deterministic keys, exactly as reviews do.
- **No free-form property bag.** A node has the fields its kind needs. A
  JSON blob would make this the generic property graph the context exists
  not to be, and would let a quantity acquire a designation.
- **No confidence, score or weight.** Knowledge is here because an
  engineer approved it. A number expressing how much to trust it would
  reintroduce exactly the ungoverned trust signal ADR-0004 rejected.

### Why `governed_graph_*` and not `project_graph_*`

Those names are taken, by two earlier graph efforts fed from a different
lineage: `graph_builder`/`project_knowledge_graph` (Milestones 11.1/11.2,
sourced from Canonical Facts) and the legacy path ADR-0009 isolates.
Neither is touched here. `docs/architecture/knowledge_graph.md` states
the relationship between the three and recommends how the older two
retire.

Revision ID: d15a7c3e8b42
Revises: c92f4d1a7b60
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d15a7c3e8b42"
down_revision: Union[str, None] = "c92f4d1a7b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Every provenance column, on both nodes and edges. Identical by design:
#: the question "where did this come from?" has the same answer shape
#: whichever kind of object is asked.
def _provenance_columns() -> list[sa.Column]:
    return [
        sa.Column("statement_key", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("content_checksum", sa.String(length=128), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "reviewer_display_name", sa.String(length=120), nullable=False
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("semantic_rule_id", sa.String(length=120), nullable=False),
        sa.Column(
            "semantic_rule_version", sa.String(length=40), nullable=False
        ),
        sa.Column(
            "semantic_contract_version",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "resolution_policy_version",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "fact_policy_version", sa.String(length=40), nullable=False
        ),
        sa.Column(
            "semantic_policy_version", sa.String(length=40), nullable=False
        ),
        sa.Column(
            "support_fingerprint", sa.String(length=64), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "governed_graph_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("entity_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "normalized_value", sa.String(length=255), nullable=False
        ),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("retirement_reason", sa.String(length=60), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *_provenance_columns(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_governed_graph_nodes_id"), "governed_graph_nodes", ["id"]
    )

    # Unique: promoting the same governed entity twice cannot produce two
    # nodes, whatever the application does. Duplicate prevention as a
    # constraint rather than a convention.
    op.create_index(
        op.f("ix_governed_graph_nodes_node_id"),
        "governed_graph_nodes",
        ["node_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_governed_graph_nodes_entity_key"),
        "governed_graph_nodes",
        ["entity_key"],
    )
    op.create_index(
        op.f("ix_governed_graph_nodes_kind"),
        "governed_graph_nodes",
        ["kind"],
    )
    op.create_index(
        op.f("ix_governed_graph_nodes_state"),
        "governed_graph_nodes",
        ["state"],
    )
    op.create_index(
        op.f("ix_governed_graph_nodes_document_id"),
        "governed_graph_nodes",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_governed_graph_nodes_project_id"),
        "governed_graph_nodes",
        ["project_id"],
    )
    op.create_index(
        "ix_governed_graph_nodes_project_state",
        "governed_graph_nodes",
        ["project_id", "state", "kind"],
    )

    op.create_table(
        "governed_graph_edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("edge_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("subject_node_id", sa.String(length=64), nullable=False),
        sa.Column("object_node_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("retirement_reason", sa.String(length=60), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *_provenance_columns(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_governed_graph_edges_id"), "governed_graph_edges", ["id"]
    )
    op.create_index(
        op.f("ix_governed_graph_edges_edge_id"),
        "governed_graph_edges",
        ["edge_id"],
        unique=True,
    )

    # Unique: one semantic statement produces at most one edge, which is
    # what makes re-promotion idempotent at the database level.
    op.create_index(
        op.f("ix_governed_graph_edges_statement_key"),
        "governed_graph_edges",
        ["statement_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_governed_graph_edges_kind"),
        "governed_graph_edges",
        ["kind"],
    )
    op.create_index(
        op.f("ix_governed_graph_edges_state"),
        "governed_graph_edges",
        ["state"],
    )
    op.create_index(
        op.f("ix_governed_graph_edges_subject_node_id"),
        "governed_graph_edges",
        ["subject_node_id"],
    )
    op.create_index(
        op.f("ix_governed_graph_edges_object_node_id"),
        "governed_graph_edges",
        ["object_node_id"],
    )
    op.create_index(
        op.f("ix_governed_graph_edges_document_id"),
        "governed_graph_edges",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_governed_graph_edges_project_id"),
        "governed_graph_edges",
        ["project_id"],
    )
    op.create_index(
        "ix_governed_graph_edges_project_state",
        "governed_graph_edges",
        ["project_id", "state", "kind"],
    )

    op.create_table(
        "governed_graph_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_number", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column(
            "promotion_contract_version",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_governed_graph_generations_id"),
        "governed_graph_generations",
        ["id"],
    )
    op.create_index(
        op.f("ix_governed_graph_generations_generation_number"),
        "governed_graph_generations",
        ["generation_number"],
        unique=True,
    )


def downgrade() -> None:
    """
    Reverses the schema change.

    Unlike every other downgrade in this repository, this one loses
    **nothing that matters**: the graph is a projection, and re-running
    the upgrade plus a rebuild reproduces its content exactly from the
    pipeline and the reviews. That is the practical consequence of the
    decision recorded in ADR-0024.
    """

    op.drop_index(
        op.f("ix_governed_graph_generations_generation_number"),
        "governed_graph_generations",
    )
    op.drop_index(
        op.f("ix_governed_graph_generations_id"),
        "governed_graph_generations",
    )
    op.drop_table("governed_graph_generations")

    for index in (
        "ix_governed_graph_edges_project_state",
        op.f("ix_governed_graph_edges_project_id"),
        op.f("ix_governed_graph_edges_document_id"),
        op.f("ix_governed_graph_edges_object_node_id"),
        op.f("ix_governed_graph_edges_subject_node_id"),
        op.f("ix_governed_graph_edges_state"),
        op.f("ix_governed_graph_edges_kind"),
        op.f("ix_governed_graph_edges_statement_key"),
        op.f("ix_governed_graph_edges_edge_id"),
        op.f("ix_governed_graph_edges_id"),
    ):
        op.drop_index(index, "governed_graph_edges")

    op.drop_table("governed_graph_edges")

    for index in (
        "ix_governed_graph_nodes_project_state",
        op.f("ix_governed_graph_nodes_project_id"),
        op.f("ix_governed_graph_nodes_document_id"),
        op.f("ix_governed_graph_nodes_state"),
        op.f("ix_governed_graph_nodes_kind"),
        op.f("ix_governed_graph_nodes_entity_key"),
        op.f("ix_governed_graph_nodes_node_id"),
        op.f("ix_governed_graph_nodes_id"),
    ):
        op.drop_index(index, "governed_graph_nodes")

    op.drop_table("governed_graph_nodes")
