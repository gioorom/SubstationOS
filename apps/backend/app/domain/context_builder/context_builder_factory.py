"""
Builds an immutable ``ContextBuildRequest`` from the raw, optional
fields an API caller supplies (CLAUDE.md SS4.2 - a factory enforces
invariants at construction time).
"""

from __future__ import annotations

from app.domain.context_builder.budget_policy import (
    BUDGET_POLICY_VERSION,
    CONTEXT_BUILDER_VERSION,
    DEFAULT_MAX_ATTRIBUTES,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_ENTITIES,
    DEFAULT_MAX_METADATA_ENTRIES,
    DEFAULT_MAX_RELATIONSHIPS,
    DEFAULT_MAX_WARNINGS,
    SELECTION_POLICY_VERSION,
)
from app.domain.context_builder.context_builder_models import (
    BudgetPolicy,
    ContextBuildRequest,
    ContextBuilderConfiguration,
    ContextMetadataEntry,
    ContextSelectionPolicy,
)
from app.domain.context_builder.context_builder_validator import (
    ContextBuilderValidator,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)


class ContextBuildRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        candidates: KnowledgeCandidateCollection,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        max_entities: int = DEFAULT_MAX_ENTITIES,
        max_relationships: int = DEFAULT_MAX_RELATIONSHIPS,
        max_attributes: int = DEFAULT_MAX_ATTRIBUTES,
        max_metadata_entries: int = DEFAULT_MAX_METADATA_ENTRIES,
        max_warnings: int = DEFAULT_MAX_WARNINGS,
        metadata_entries: tuple[tuple[str, str], ...] = (),
        retrieval_policy_version: str | None = None,
    ) -> ContextBuildRequest:
        ContextBuilderValidator.validate_project_id(project_id)
        ContextBuilderValidator.validate_budget_policy(
            max_candidates=max_candidates,
            max_entities=max_entities,
            max_relationships=max_relationships,
            max_attributes=max_attributes,
            max_metadata_entries=max_metadata_entries,
            max_warnings=max_warnings,
        )
        ContextBuilderValidator.validate_metadata_entries(metadata_entries)

        budget_policy = BudgetPolicy(
            version=BUDGET_POLICY_VERSION,
            max_candidates=max_candidates,
            max_entities=max_entities,
            max_relationships=max_relationships,
            max_attributes=max_attributes,
            max_metadata_entries=max_metadata_entries,
            max_warnings=max_warnings,
        )
        configuration = ContextBuilderConfiguration(
            budget_policy=budget_policy,
            selection_policy=ContextSelectionPolicy(
                version=SELECTION_POLICY_VERSION
            ),
            context_builder_version=CONTEXT_BUILDER_VERSION,
        )

        entries = tuple(
            ContextMetadataEntry(key=key, value=value)
            for key, value in metadata_entries
        )

        return ContextBuildRequest(
            project_id=project_id,
            candidates=candidates,
            configuration=configuration,
            metadata_entries=entries,
            retrieval_policy_version=retrieval_policy_version,
        )
