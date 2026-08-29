"""
Builds ``ContextMetadata`` and truncates caller-supplied metadata
entries to the configured ``max_metadata_entries`` budget.

``now`` is always supplied by the caller (the service layer) rather than
read from the wall clock here, keeping assembly deterministic and
reproducible given the same inputs (CLAUDE.md SS16).

The retrieval versions recorded here are **echoed from the governed
results**, never re-derived: which normalization folded a designation
and which matching policy ordered the answers are facts about the
retrieval that ran, and a context that restated them from its own
constants could disagree with the results it contains.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    ContextAssemblyConfiguration,
    ContextMetadata,
    ContextMetadataEntry,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalResult,
)


def _retrieval_versions(
    results: tuple[GovernedRetrievalResult, ...],
) -> tuple[str | None, str | None, int | None]:
    """
    The versions the governed results agree on.

    ``None`` when there is nothing to report, and - deliberately - also
    ``None`` when the results **disagree**: one value standing for two
    different ones is how a version field becomes a lie. Disagreement is
    only reachable across a redeploy mid-request, so reporting nothing is
    both honest and rare.
    """

    if not results:
        return (None, None, None)

    normalization = {
        result.diagnostics.normalization_version for result in results
    }
    matching = {
        result.diagnostics.matching_policy_version for result in results
    }
    generation = {
        result.diagnostics.graph_version.generation_number
        for result in results
    }

    return (
        normalization.pop() if len(normalization) == 1 else None,
        matching.pop() if len(matching) == 1 else None,
        generation.pop() if len(generation) == 1 else None,
    )


def build_metadata(
    *,
    configuration: ContextAssemblyConfiguration,
    results: tuple[GovernedRetrievalResult, ...],
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

    normalization, matching, generation = _retrieval_versions(results)

    metadata = ContextMetadata(
        context_assembly_version=configuration.context_assembly_version,
        assembled_at=now,
        selection_policy_version=configuration.selection_policy.version,
        budget_policy_version=configuration.budget_policy.version,
        retrieval_normalization_version=normalization,
        retrieval_matching_policy_version=matching,
        graph_generation_number=generation,
        entries=accepted_entries,
    )

    return metadata, consumption
