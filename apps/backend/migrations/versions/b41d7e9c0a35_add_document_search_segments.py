"""add the searchable projection of a document

One table holding the smallest pieces of a document worth showing an
engineer on their own: a line of a drawing's text, a cell of a workbook.

**A projection, and disposable.** Every row is derived from a canonical
representation that stays authoritative. Dropping the table loses
nothing but the work to rebuild it, which is why it carries no identity
of its own and no lifecycle - it copies ``document_id`` and
``content_checksum`` from the document it was read from so a hit can
say which version it came from, and if the two ever disagree the
document row wins.

``project_id`` is copied rather than joined, and is the column every
search filters on first. A search that had to join to find the project
would be one refactor away from a search that forgot to.

``normalized_text`` is stored beside the verbatim text because matching
compares the normalized form and a reader recognises the original. It
is space-wrapped so a term matches whole: ``% tr1 %`` finds ``TR1`` and
never the ``TR1`` inside ``TR15``.

Revision ID: b41d7e9c0a35
Revises: 8f21c04ab7de
Create Date: 2026-09-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b41d7e9c0a35"
down_revision: Union[str, Sequence[str], None] = "8f21c04ab7de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "document_search_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content_checksum", sa.String(length=128), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("line_index", sa.Integer(), nullable=True),
        sa.Column("worksheet_index", sa.Integer(), nullable=True),
        sa.Column("worksheet_name", sa.String(length=255), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("column_number", sa.Integer(), nullable=True),
        sa.Column("cell_offsets", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_document_search_segments_id",
        "document_search_segments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_document_search_segments_project",
        "document_search_segments",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_search_segments_document",
        "document_search_segments",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_document_search_segments_document",
        table_name="document_search_segments",
    )
    op.drop_index(
        "ix_document_search_segments_project",
        table_name="document_search_segments",
    )
    op.drop_index(
        "ix_document_search_segments_id",
        table_name="document_search_segments",
    )
    op.drop_table("document_search_segments")
