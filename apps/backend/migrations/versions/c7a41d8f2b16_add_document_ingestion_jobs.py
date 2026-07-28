"""add document_ingestion_jobs

Introduces the Document Ingestion lifecycle table (Milestone 25.1): one
row per ingestion of one document, carrying its lifecycle state, its
outcome, the pipeline version that produced it, and a snapshot of the
document's metadata as it stood at ingestion time.

Additive only - no existing table, column or constraint is altered, so a
database at the baseline revision upgrades without touching any governed
data.

Revision ID: c7a41d8f2b16
Revises: b3e2e0f30024
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a41d8f2b16"
down_revision: Union[str, Sequence[str], None] = "b3e2e0f30024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "document_ingestion_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "UPLOADED",
                "QUEUED",
                "PROCESSING",
                "PROCESSED",
                "FAILED",
                name="ingestionstate",
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.Enum(
                "READY_FOR_EXTRACTION",
                "FAILED",
                name="ingestionoutcome",
            ),
            nullable=True,
        ),
        sa.Column("pipeline_version", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "failure_code",
            sa.Enum(
                "DOCUMENT_NOT_FOUND",
                "UNSUPPORTED_FORMAT",
                "INVALID_LIFECYCLE_TRANSITION",
                "DUPLICATE_INGESTION_REQUEST",
                "PIPELINE_EXECUTION_FAILURE",
                name="ingestionfailurecode",
            ),
            nullable=True,
        ),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("failure_detail", sa.String(length=1000), nullable=True),
        sa.Column("document_title", sa.String(length=255), nullable=True),
        sa.Column("document_format", sa.String(length=50), nullable=True),
        sa.Column("document_category", sa.String(length=50), nullable=True),
        sa.Column("document_revision", sa.String(length=50), nullable=True),
        sa.Column(
            "document_scope",
            sa.Enum(
                "PROJECT",
                "CANONICAL_LIBRARY",
                name="documentscope",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_ingestion_jobs_id"),
        "document_ingestion_jobs",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_ingestion_jobs_document_id"),
        "document_ingestion_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_ingestion_jobs_project_id"),
        "document_ingestion_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_ingestion_jobs_document_state",
        "document_ingestion_jobs",
        ["document_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_document_ingestion_jobs_project_state",
        "document_ingestion_jobs",
        ["project_id", "state"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_document_ingestion_jobs_project_state",
        table_name="document_ingestion_jobs",
    )
    op.drop_index(
        "ix_document_ingestion_jobs_document_state",
        table_name="document_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_document_ingestion_jobs_project_id"),
        table_name="document_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_document_ingestion_jobs_document_id"),
        table_name="document_ingestion_jobs",
    )
    op.drop_index(
        op.f("ix_document_ingestion_jobs_id"),
        table_name="document_ingestion_jobs",
    )
    op.drop_table("document_ingestion_jobs")
