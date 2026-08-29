"""
Builds an immutable ``ContextBuildRequest`` from the raw, optional
fields a caller supplies (CLAUDE.md SS4.2 - a factory enforces
invariants at construction time).

The input is a tuple of **governed retrieval results**. There is no
constructor that accepts anything else, which is what makes "Context
Assembly reads only governed knowledge" a property of the type rather
than a rule somebody has to remember.
"""

from __future__ import annotations

from app.domain.context_builder.budget_policy import (
    BUDGET_POLICY_VERSION,
    CONTEXT_ASSEMBLY_VERSION,
    DEFAULT_MAX_ASSETS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_METADATA_ENTRIES,
    DEFAULT_MAX_QUANTITIES,
    DEFAULT_MAX_RELATIONSHIPS,
    DEFAULT_MAX_WARNINGS,
    SELECTION_POLICY_VERSION,
)
from app.domain.context_builder.context_builder_models import (
    BudgetPolicy,
    ContextAssemblyConfiguration,
    ContextBuildRequest,
    ContextMetadataEntry,
    ContextSelectionPolicy,
)
from app.domain.context_builder.context_builder_validator import (
    ContextBuilderValidator,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalResult,
)


class ContextBuildRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        results: tuple[GovernedRetrievalResult, ...],
        max_items: int = DEFAULT_MAX_ITEMS,
        max_assets: int = DEFAULT_MAX_ASSETS,
        max_quantities: int = DEFAULT_MAX_QUANTITIES,
        max_relationships: int = DEFAULT_MAX_RELATIONSHIPS,
        max_metadata_entries: int = DEFAULT_MAX_METADATA_ENTRIES,
        max_warnings: int = DEFAULT_MAX_WARNINGS,
        metadata_entries: tuple[tuple[str, str], ...] = (),
    ) -> ContextBuildRequest:
        ContextBuilderValidator.validate_project_id(project_id)
        ContextBuilderValidator.validate_budget_policy(
            max_items=max_items,
            max_assets=max_assets,
            max_quantities=max_quantities,
            max_relationships=max_relationships,
            max_metadata_entries=max_metadata_entries,
            max_warnings=max_warnings,
        )
        ContextBuilderValidator.validate_metadata_entries(metadata_entries)

        budget_policy = BudgetPolicy(
            version=BUDGET_POLICY_VERSION,
            max_items=max_items,
            max_assets=max_assets,
            max_quantities=max_quantities,
            max_relationships=max_relationships,
            max_metadata_entries=max_metadata_entries,
            max_warnings=max_warnings,
        )
        configuration = ContextAssemblyConfiguration(
            budget_policy=budget_policy,
            selection_policy=ContextSelectionPolicy(
                version=SELECTION_POLICY_VERSION
            ),
            context_assembly_version=CONTEXT_ASSEMBLY_VERSION,
        )

        entries = tuple(
            ContextMetadataEntry(key=key, value=value)
            for key, value in metadata_entries
        )

        return ContextBuildRequest(
            project_id=project_id,
            results=results,
            configuration=configuration,
            metadata_entries=entries,
        )
