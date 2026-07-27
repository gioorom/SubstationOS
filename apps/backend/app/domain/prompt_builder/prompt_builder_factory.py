"""
Builds an immutable ``PromptBuildRequest`` from a caller-supplied
``ContextPackage`` (CLAUDE.md SS4.2 - a factory enforces invariants at
construction time).
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.composition_policy import (
    COMPOSITION_POLICY_VERSION,
    PROMPT_BUILDER_VERSION,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptBuildRequest,
    PromptBuilderConfiguration,
    PromptCompositionPolicy,
)
from app.domain.prompt_builder.prompt_builder_validator import (
    PromptBuilderValidator,
)


class PromptBuildRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        context_package: ContextPackage,
    ) -> PromptBuildRequest:
        PromptBuilderValidator.validate_project_id(project_id)
        PromptBuilderValidator.validate_project_id_matches_context_package(
            project_id, context_package
        )

        configuration = PromptBuilderConfiguration(
            composition_policy=PromptCompositionPolicy(
                version=COMPOSITION_POLICY_VERSION
            ),
            prompt_builder_version=PROMPT_BUILDER_VERSION,
        )

        return PromptBuildRequest(
            project_id=project_id,
            context_package=context_package,
            configuration=configuration,
        )
