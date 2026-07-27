"""
Builds an immutable ``EngineeringResponseBuildRequest`` from a
caller-supplied ``ContextPackage``/``PromptPackage``/
``EngineeringResponseSourceEnvelope`` (CLAUDE.md SS4.2 - a factory
enforces invariants at construction time).
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseBuildRequest,
    EngineeringResponseConfiguration,
    EngineeringResponsePolicy,
    EngineeringResponseSourceEnvelope,
)
from app.domain.engineering_response.engineering_response_policy import (
    ENGINEERING_RESPONSE_VERSION,
    RESPONSE_POLICY_VERSION,
)
from app.domain.engineering_response.engineering_response_validator import (
    EngineeringResponseInputValidator,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


class EngineeringResponseBuildRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        context_package: ContextPackage,
        prompt_package: PromptPackage,
        source: EngineeringResponseSourceEnvelope,
    ) -> EngineeringResponseBuildRequest:
        EngineeringResponseInputValidator.validate_project_id(project_id)
        EngineeringResponseInputValidator.validate_project_id_matches_context_package(
            project_id, context_package
        )
        EngineeringResponseInputValidator.validate_project_id_matches_prompt_package(
            project_id, prompt_package
        )

        configuration = EngineeringResponseConfiguration(
            response_policy=EngineeringResponsePolicy(
                version=RESPONSE_POLICY_VERSION
            ),
            engineering_response_version=ENGINEERING_RESPONSE_VERSION,
        )

        return EngineeringResponseBuildRequest(
            project_id=project_id,
            context_package=context_package,
            prompt_package=prompt_package,
            source=source,
            configuration=configuration,
        )
