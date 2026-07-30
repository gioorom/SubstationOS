"""add engineering reviews

EPIC 30.4: the Human Review bounded context - one append-only table
holding governed engineering judgements over deterministic pipeline
artefacts.

**Purely additive.** One new table and its indexes. No existing table,
column or constraint is touched, and in particular **nothing in the
engineering pipeline is modified**: reviews reference semantic statements
by their deterministic key and never write to them. Engineering truth and
engineering judgement stay separate at the schema level, not only in
prose.

Four things this table deliberately does **not** have:

- **No status, `is_current` or `superseded_at` column.** Every one would
  be a mutable field on a record that must never be modified, and every
  one would be a second account of something the ordered history already
  says. The current decision is the newest row, computed on read.
- **No engineering payload.** No statement type, subject, object,
  quantity or support. A column holding what a statement *said* would be
  a copy of engineering knowledge living outside the pipeline that
  produced it, and the first time the two disagreed nobody could say
  which was authoritative.
- **No foreign key to the semantic tables.** A re-run replaces a semantic
  set; a constraint would either block the pipeline or cascade a
  historical judgement into nothing. The snapshot columns exist precisely
  so a review outlives the artefact it reviewed.
- **No foreign key to ``users``.** The reviewer is denormalised for the
  same reason the audit trail denormalises its actor: the record must
  stay readable after the account is renamed, re-roled or disabled.

The snapshot columns record the identity the reviewed statement had -
which bytes, which rules, which policies, and a fingerprint over the
support chain. That is what makes "does this review still apply after the
pipeline re-ran?" a comparison rather than a guess; see
`docs/architecture/human_review.md`.

Revision ID: c92f4d1a7b60
Revises: a4c81f2b90de
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c92f4d1a7b60"
down_revision: Union[str, None] = "a4c81f2b90de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        # What was reviewed, by identity alone.
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_key", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        # The judgement.
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        # Who, and when.
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "reviewer_display_name", sa.String(length=120), nullable=False
        ),
        sa.Column("reviewer_email", sa.String(length=254), nullable=False),
        sa.Column("reviewer_role", sa.String(length=40), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("record_version", sa.String(length=20), nullable=False),
        # The snapshot: the artefact's identity at review time.
        sa.Column(
            "content_checksum", sa.String(length=128), nullable=False
        ),
        sa.Column(
            "semantic_rule_id", sa.String(length=120), nullable=False
        ),
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
            "semantic_policy_version",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "support_fingerprint", sa.String(length=64), nullable=False
        ),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_engineering_reviews_id"), "engineering_reviews", ["id"]
    )
    op.create_index(
        op.f("ix_engineering_reviews_target_key"),
        "engineering_reviews",
        ["target_key"],
    )
    op.create_index(
        op.f("ix_engineering_reviews_document_id"),
        "engineering_reviews",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_engineering_reviews_recorded_at"),
        "engineering_reviews",
        ["recorded_at"],
    )

    # The history read: every judgement about one statement, newest first.
    op.create_index(
        "ix_engineering_reviews_target_history",
        "engineering_reviews",
        ["document_id", "target_key", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    """
    Reverses the schema change.

    Note what this cannot reverse: dropping ``engineering_reviews``
    destroys every recorded engineering judgement. That is inherent to
    removing the table and is stated here so nobody discovers it by
    running this.
    """

    op.drop_index(
        "ix_engineering_reviews_target_history", "engineering_reviews"
    )
    op.drop_index(
        op.f("ix_engineering_reviews_recorded_at"), "engineering_reviews"
    )
    op.drop_index(
        op.f("ix_engineering_reviews_document_id"), "engineering_reviews"
    )
    op.drop_index(
        op.f("ix_engineering_reviews_target_key"), "engineering_reviews"
    )
    op.drop_index(op.f("ix_engineering_reviews_id"), "engineering_reviews")
    op.drop_table("engineering_reviews")
