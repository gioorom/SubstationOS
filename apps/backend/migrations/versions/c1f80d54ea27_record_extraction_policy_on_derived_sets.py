"""Record the extraction policy on fact and semantic sets

A fact set is derived from one entity set, and a semantic set from one
fact set. Each recorded the policy versions of the stages above it, but
never the extraction policy that read the evidence beneath them - so a
set could not say which reading of the document it ultimately rests on.

This adds that provenance and nothing else. It is kept as an explicit,
readable column rather than folded away, because an artifact must be
able to explain its derivation without anyone reversing a digest.

Unlike the entity table, these two have never carried the column, so the
true extraction policy of an existing row cannot be reconstructed from
anything durable. It is therefore left **NULL** rather than guessed:
unknown provenance stays unknown, and never becomes assumed-compatible
provenance.

Revision ID: c1f80d54ea27
Revises: f4a90c27b615
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1f80d54ea27"
down_revision = "f4a90c27b615"
branch_labels = None
depends_on = None

_COLUMN = "extraction_policy_version"
_TABLES = ("engineering_fact_sets", "engineering_semantic_sets")


def upgrade() -> None:
    for table in _TABLES:
        # Nullable, with no server default and no backfill: every
        # existing row keeps an unknown extraction policy, which is the
        # only honest thing to record about it.
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(_COLUMN, sa.String(length=20), nullable=True)
            )


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column(_COLUMN)
