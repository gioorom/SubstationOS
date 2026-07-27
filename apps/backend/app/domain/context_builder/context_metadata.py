"""
Builds ``ContextMetadata`` and truncates caller-supplied metadata
entries to the configured ``max_metadata_entries`` budget. ``now`` is
always supplied by the caller (the service layer) rather than read from
the wall clock here, keeping assembly deterministic and reproducible
(CLAUDE.md SS16) given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    ContextBuilderConfiguration,
    ContextMetadata,
    ContextMetadataEntry,
)


def build_metadata(
    *,
    configuration: ContextBuilderConfiguration,
    retrieval_policy_version: str | None,
    metadata_entries: tuple[ContextMetadataEntry, ...],
    now: datetime,
) -> tuple[ContextMetadata, BudgetConsumption]:
    limit = configuration.budget_policy.max_metadata_entries
    accepted_entries = metadata_entries[:limit]

    consumption = BudgetConsumption(
        category=BudgetCategory.METADATA_ENTRIES,
        requested=len(metadata_entries),
        accepted=len(accepted_entries),
        discarded=len(metadata_entries) - len(accepted_entries),
        limit=limit,
        utilization=0.0 if limit == 0 else len(accepted_entries) / limit,
    )

    metadata = ContextMetadata(
        context_builder_version=configuration.context_builder_version,
        assembled_at=now,
        selection_policy_version=configuration.selection_policy.version,
        budget_policy_version=configuration.budget_policy.version,
        retrieval_policy_version=retrieval_policy_version,
        entries=accepted_entries,
    )

    return metadata, consumption
