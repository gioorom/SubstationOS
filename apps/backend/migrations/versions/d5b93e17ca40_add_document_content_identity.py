"""add document content identity to ingestion jobs

Milestone 25.2: records the content checksum, size, storage reference and
classified format on each ingestion job.

**Additive and fully nullable.** Every column added here is optional, so
each ingestion job recorded before this revision remains readable and
keeps meaning exactly what it meant when it was written - a historical
job simply carries no content identity, which is the truth about it. No
existing row is rewritten and no existing column is altered.

Note on ``documents.file_format``: Milestone 25.2 adds ``DXF`` and
``IMAGE`` to ``DocumentFormat``. No DDL is needed on SQLite, where
SQLAlchemy renders an enum as VARCHAR with no CHECK constraint
(``Enum.create_constraint`` defaults to ``False``). A database with native
enum types would need an ``ALTER TYPE``; that is recorded here rather than
attempted, because this project runs SQLite and writing untested
Postgres DDL would be a promise this migration cannot keep.

Revision ID: d5b93e17ca40
Revises: c7a41d8f2b16
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5b93e17ca40"
down_revision: Union[str, Sequence[str], None] = "c7a41d8f2b16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "document_ingestion_jobs",
        sa.Column(
            "content_storage_reference", sa.String(length=500), nullable=True
        ),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column(
            "content_checksum_algorithm", sa.String(length=20), nullable=True
        ),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column("content_checksum", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column("content_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column("detected_format", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column("format_decided_by", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "document_ingestion_jobs",
        sa.Column(
            "format_disagreeing_evidence",
            sa.String(length=1000),
            nullable=True,
        ),
    )
    # "Which jobs saw these exact bytes?" - the one read this column is
    # for. Deliberately not unique: identical checksums are recorded and
    # nothing is concluded from them (identity is not deduplication).
    op.create_index(
        op.f("ix_document_ingestion_jobs_content_checksum"),
        "document_ingestion_jobs",
        ["content_checksum"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_document_ingestion_jobs_content_checksum"),
        table_name="document_ingestion_jobs",
    )
    op.drop_column("document_ingestion_jobs", "format_disagreeing_evidence")
    op.drop_column("document_ingestion_jobs", "format_decided_by")
    op.drop_column("document_ingestion_jobs", "detected_format")
    op.drop_column("document_ingestion_jobs", "content_size_bytes")
    op.drop_column("document_ingestion_jobs", "content_checksum")
    op.drop_column("document_ingestion_jobs", "content_checksum_algorithm")
    op.drop_column("document_ingestion_jobs", "content_storage_reference")
