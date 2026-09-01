"""Key every deterministic artifact on its derivation identity

The pipeline is a chain of deterministic derivations:

    Source -> Canonical PDF -> Canonical Text -> Evidence -> Entities
           -> Facts -> Semantics

Each stage persisted its result and, on a re-run, reused it when a
natural key matched. That key was the source checksum plus a manually
copied list of the policy versions above it - and the copy drifted, six
times, each drift a silent stale reuse.

This replaces it. Every artifact now carries the identity of the
computation that produced it:

    identity = H(identity contract, kind, upstream identity, local
                 derivation identity)

so a change anywhere upstream changes every identity below it, by
construction rather than by anyone remembering to copy a column. Reuse
is one identity comparison, and the uniqueness constraint encodes the
same rule.

**No provenance is removed.** Every explicit version column stays
readable beside the digest: identity compresses, it does not replace
explanation.

**No identity is fabricated.** Both columns are nullable, and existing
rows keep NULL. The identity of a historical artifact depends on the
identity of the artifact above it, which was never recorded, so it
cannot be reconstructed from anything durable. A NULL never satisfies an
identity lookup, so a legacy artifact is recomputed rather than trusted
- and the stage below one refuses rather than deriving from provenance
nobody can establish.

Revision ID: e5a2f7b91c60
Revises: c1f80d54ea27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5a2f7b91c60"
down_revision = "c1f80d54ea27"
branch_labels = None
depends_on = None

_IDENTITY = "artifact_identity"
_UPSTREAM = "upstream_identity"

# table -> (old constraint name, old columns, new constraint name)
_TABLES: dict[str, tuple[str, tuple[str, ...], str]] = {
    "canonical_pdf_representations": (
        "uq_canonical_pdf_document_checksum_version",
        ("document_id", "content_checksum", "representation_version"),
        "uq_canonical_pdf_artifact_identity",
    ),
    "canonical_text_documents": (
        "uq_canonical_text_document_checksum_version",
        ("document_id", "content_checksum", "segmentation_version"),
        "uq_canonical_text_artifact_identity",
    ),
    "engineering_evidence_sets": (
        "uq_engineering_evidence_set_source_policy",
        ("document_id", "content_checksum", "extraction_policy_version"),
        "uq_engineering_evidence_set_artifact_identity",
    ),
    "engineering_entity_sets": (
        "uq_engineering_entity_set_source_policy",
        ("document_id", "content_checksum", "resolution_policy_version"),
        "uq_engineering_entity_set_artifact_identity",
    ),
    "engineering_fact_sets": (
        "uq_engineering_fact_set_source_policy",
        (
            "document_id",
            "content_checksum",
            "resolution_policy_version",
            "fact_policy_version",
        ),
        "uq_engineering_fact_set_artifact_identity",
    ),
    "engineering_semantic_sets": (
        "uq_engineering_semantic_set_source_policy",
        (
            "document_id",
            "content_checksum",
            "resolution_policy_version",
            "fact_policy_version",
            "semantic_policy_version",
        ),
        "uq_engineering_semantic_set_artifact_identity",
    ),
}


def upgrade() -> None:
    for table, (old_name, _, new_name) in _TABLES.items():
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(_IDENTITY, sa.String(length=64), nullable=True)
            )
            batch.add_column(
                sa.Column(_UPSTREAM, sa.String(length=64), nullable=True)
            )
            batch.drop_constraint(old_name, type_="unique")
            batch.create_unique_constraint(
                new_name, ["document_id", _IDENTITY]
            )

        op.create_index(
            f"ix_{table}_artifact_identity", table, [_IDENTITY]
        )


def downgrade() -> None:
    """
    Restore the natural-key constraints and drop the identity columns.

    Refused when the data no longer fits: once a source has been derived
    under two different contracts, the rows that records are exactly the
    rows the older, weaker constraints forbid. Choosing which honest
    derivation to destroy is not a decision a migration may make.

    Checked **before** anything is altered. Discovering the conflict half
    way through a batch rebuild would abort with a constraint error and
    leave the rebuild's temporary table behind, so the next attempt would
    fail on that instead of reporting the real cause.
    """

    bind = op.get_bind()

    for table, (_, columns, new_name) in _TABLES.items():
        grouped = ", ".join(columns)
        conflicts = bind.execute(
            sa.text(
                # The derived table is aliased so this parses on every
                # backend the repository supports, not only SQLite.
                f"SELECT COUNT(*) FROM ("  # noqa: S608 - fixed identifiers
                f"SELECT 1 FROM {table} "
                f"GROUP BY {grouped} "
                f"HAVING COUNT(*) > 1) AS conflicting"
            )
        ).scalar()

        if conflicts:
            raise RuntimeError(
                f"Cannot restore the natural key on {table}: "
                f"{conflicts} group(s) hold more than one artifact "
                "because the same source was derived under more than "
                "one contract. Narrowing would require deleting one of "
                "them."
            )

    for table, (old_name, columns, new_name) in _TABLES.items():
        op.drop_index(f"ix_{table}_artifact_identity", table_name=table)

        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(new_name, type_="unique")
            batch.create_unique_constraint(old_name, list(columns))
            batch.drop_column(_UPSTREAM)
            batch.drop_column(_IDENTITY)
