"""add content identity to documents

ADR-0036: records a document's own content identity on the ``documents``
row - the digest of the bytes that were stored, the algorithm that
produced it, and their length.

Until now the checksum lived only on ``document_ingestion_jobs``, one per
attempt, and "the checksum of document 17" had as many answers as that
document had ingestion jobs. The registry resolved it by taking the most
recent job by row id, with no filter on whether that job succeeded. This
revision gives the question one answer by putting it where the question
is asked.

**Additive and fully nullable.** Three columns and one index. No existing
table, column or constraint is altered, and no row is rewritten.

``content_checksum`` is nullable and is **not** backfilled, here or
anywhere. A migration cannot hash bytes it never saw, and a
``server_default`` would manufacture a value whose only property is that
it looks like one. A row created before this revision therefore carries
no content identity, which is the truth about it: ``NULL`` means
*honestly unknown*, never "empty" and never "zero". Because ``NULL``
never equals ``NULL`` in SQL, two such rows are never treated as sharing
an unknown identity.

The index is deliberately **not** unique. Identical checksums are
recorded and nothing is concluded from them - whether a repeated upload
is a duplicate, a re-issue under a new revision, or the same drawing
filed against two projects is a question about the documents, not their
bytes. Uniqueness here would answer it by accident.

Revision ID: 3ca7e14b90d2
Revises: 2fb50687af2e
Create Date: 2026-09-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3ca7e14b90d2"
down_revision: Union[str, Sequence[str], None] = "2fb50687af2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "documents",
        sa.Column("content_checksum", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "content_checksum_algorithm", sa.String(length=20), nullable=True
        ),
    )
    op.add_column(
        "documents",
        sa.Column("content_size_bytes", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_documents_content_checksum",
        "documents",
        ["content_checksum"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index("ix_documents_content_checksum", table_name="documents")

    op.drop_column("documents", "content_size_bytes")
    op.drop_column("documents", "content_checksum_algorithm")
    op.drop_column("documents", "content_checksum")
