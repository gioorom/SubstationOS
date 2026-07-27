"""
Application service for the LLM Provider Abstraction Layer (EPIC 4,
Milestone 16). Orchestrates: validate the request, construct the
provider-neutral ``LLMRequest``, resolve the matching provider adapter,
validate required capabilities, and prepare the provider-native local
request. No network I/O, no response generation, no persistence, and
no provider fallback of any kind - a provider mismatch or missing
capability always raises rather than silently substituting a different
provider.
"""

from __future__ import annotations

from datetime import datetime

from app.application.config.llm_configuration import PROVIDER_ABSTRACTION_VERSION
from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMCapabilityValidationResult,
)
from app.application.models.llm_exceptions import (
    ProviderMismatchError,
    UnsupportedCapabilityError,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequestPreparationResult,
)
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.application.services.llm_request_validator import LLMRequestValidator
from app.application.services.prompt_package_to_llm_request_mapper import (
    map_prompt_package_to_llm_request,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage

# The minimum a provider must support to prepare any request at all -
# every other requested capability is optional (unsupported ones are
# reported as a warning, never silently downgraded or a hard failure).
DEFAULT_REQUIRED_CAPABILITIES: tuple[LLMCapability, ...] = (
    LLMCapability.TEXT_INPUT,
)


def _generation_parameter_warnings(
    generation_parameters: LLMGenerationParameters,
    supported: frozenset[LLMCapability],
) -> list[str]:
    warnings: list[str] = []

    if (
        generation_parameters.max_output_tokens is not None
        and LLMCapability.CONFIGURABLE_MAX_OUTPUT not in supported
    ):
        warnings.append(
            "Provider does not support configuring 'max_output_tokens'; "
            "the adapter's own default was used instead."
        )

    if (
        generation_parameters.temperature is not None
        and LLMCapability.TEMPERATURE not in supported
    ):
        warnings.append(
            "Provider does not support 'temperature'; the parameter was "
            "not applied."
        )

    if generation_parameters.stop_sequences and (
        LLMCapability.STOP_SEQUENCES not in supported
    ):
        warnings.append(
            "Provider does not support 'stop_sequences'; the parameter "
            "was not applied."
        )

    return warnings


def prepare_llm_request(
    *,
    registry: LLMProviderRegistry,
    prompt_package: PromptPackage,
    project_id: int,
    provider_selection: LLMProviderSelection,
    model_selection: LLMModelSelection,
    generation_parameters: LLMGenerationParameters | None = None,
    capability_requirements: LLMCapabilityRequirements | None = None,
    request_correlation_id: str,
    request_preparation_policy_version: str,
    now: datetime,
) -> LLMRequestPreparationResult:
    LLMRequestValidator.validate_project_id(project_id)
    LLMRequestValidator.validate_project_id_matches_prompt_package(
        project_id, prompt_package
    )
    LLMRequestValidator.validate_prompt_package(prompt_package)
    LLMRequestValidator.validate_provider_selection(provider_selection)
    LLMRequestValidator.validate_model_selection(model_selection)

    generation_parameters = generation_parameters or LLMGenerationParameters()
    LLMRequestValidator.validate_generation_parameters(generation_parameters)

    capability_requirements = capability_requirements or LLMCapabilityRequirements(
        required_capabilities=DEFAULT_REQUIRED_CAPABILITIES
    )

    adapter = registry.resolve(provider_selection.provider_id)

    if adapter.provider_id() != provider_selection.provider_id:
        raise ProviderMismatchError(
            provider_selection.provider_id, adapter.provider_id()
        )

    provider_capabilities = adapter.provider_capabilities()

    missing_required = tuple(
        capability
        for capability in capability_requirements.required_capabilities
        if capability not in provider_capabilities.supported
    )
    if missing_required:
        raise UnsupportedCapabilityError(
            provider_selection.provider_id, missing_required
        )

    llm_request = map_prompt_package_to_llm_request(
        prompt_package,
        provider_selection=provider_selection,
        model_selection=model_selection,
        generation_parameters=generation_parameters,
        capability_requirements=capability_requirements,
        provider_abstraction_version=PROVIDER_ABSTRACTION_VERSION,
        request_preparation_policy_version=request_preparation_policy_version,
        request_correlation_id=request_correlation_id,
        now=now,
    )

    prepared_request = adapter.prepare_request(llm_request)

    warnings = tuple(
        adapter.validate_configuration()
    ) + tuple(
        _generation_parameter_warnings(
            generation_parameters, provider_capabilities.supported
        )
    )

    capability_validation = LLMCapabilityValidationResult(
        valid=True,
        missing_required_capabilities=(),
        unsupported_requested_capabilities=(),
    )

    return LLMRequestPreparationResult(
        request=llm_request,
        provider_capabilities=provider_capabilities,
        capability_validation=capability_validation,
        prepared_request=prepared_request,
        warnings=warnings,
    )
