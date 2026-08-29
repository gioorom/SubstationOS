from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from app.application.models.llm_capabilities import LLMCapability
from app.application.models.llm_exceptions import (
    InvalidPromptPackageError,
    ProjectIdMismatchError,
    ProviderMismatchError,
    UnknownProviderError,
    UnsupportedCapabilityError,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
)
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.application.services.llm_request_service import prepare_llm_request
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeLLMProviderAdapter,
)
from app.services import context_builder_service, prompt_builder_service

from tests._governed_context import designation_result

PROJECT_ID = 8
NOW = datetime(2026, 1, 1, 11, 0, 0)


def _prompt_package(project_id: int = PROJECT_ID):
    context_result = context_builder_service.build_context_package(
        project_id=project_id, results=(designation_result("TR1", ()),), now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    return prompt_result.package


def _registry() -> LLMProviderRegistry:
    registry = LLMProviderRegistry()
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(model_identifier="model-x", default_max_output_tokens=4096),
    )
    registry.register("fake", FakeLLMProviderAdapter())
    return registry


def _prepare(**overrides):
    defaults = dict(
        registry=_registry(),
        prompt_package=_prompt_package(),
        project_id=PROJECT_ID,
        provider_selection=LLMProviderSelection(provider_id=ANTHROPIC_PROVIDER_ID),
        model_selection=LLMModelSelection(model_identifier="model-x"),
        request_correlation_id="corr-1",
        request_preparation_policy_version="1.0",
        now=NOW,
    )
    defaults.update(overrides)
    return prepare_llm_request(**defaults)


def test_successful_anthropic_preparation():
    result = _prepare()
    assert result.request.project_id == PROJECT_ID
    assert result.prepared_request.provider_id == ANTHROPIC_PROVIDER_ID
    assert result.capability_validation.valid is True


def test_successful_fake_provider_preparation():
    result = _prepare(
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="fake-model"),
    )
    assert result.prepared_request.provider_id == "fake"


def test_unknown_provider_raises():
    with pytest.raises(UnknownProviderError):
        _prepare(provider_selection=LLMProviderSelection(provider_id="does-not-exist"))


def test_missing_model_selection_raises():
    from app.application.models.llm_exceptions import MissingModelSelectionError

    with pytest.raises(MissingModelSelectionError):
        _prepare(model_selection=LLMModelSelection(model_identifier=""))


def test_unsupported_required_capability_raises():
    with pytest.raises(UnsupportedCapabilityError):
        _prepare(
            provider_selection=LLMProviderSelection(provider_id="fake"),
            model_selection=LLMModelSelection(model_identifier="fake-model"),
            capability_requirements=LLMCapabilityRequirements(
                required_capabilities=(LLMCapability.STREAMING,)
            ),
        )


def test_invalid_prompt_package_project_mismatch_raises():
    package = _prompt_package(project_id=PROJECT_ID)
    with pytest.raises(ProjectIdMismatchError):
        _prepare(prompt_package=package, project_id=PROJECT_ID + 1)


def test_service_never_falls_back_to_a_different_provider():
    # A provider that cannot satisfy a required capability must fail,
    # never silently substitute a different registered adapter.
    with pytest.raises(UnsupportedCapabilityError):
        _prepare(
            provider_selection=LLMProviderSelection(provider_id="fake"),
            model_selection=LLMModelSelection(model_identifier="fake-model"),
            capability_requirements=LLMCapabilityRequirements(
                required_capabilities=(LLMCapability.TOOL_USE,)
            ),
        )


def test_metadata_propagates_provider_and_model_and_versions():
    result = _prepare()
    metadata = result.request.metadata
    assert metadata.provider_id == ANTHROPIC_PROVIDER_ID
    assert metadata.model_identifier == "model-x"
    assert metadata.project_id == PROJECT_ID
    assert metadata.request_correlation_id == "corr-1"
    assert metadata.provider_abstraction_version == "1.0"
    assert metadata.request_preparation_policy_version == "1.0"


def test_result_never_carries_a_secret_or_credential_field():
    result = _prepare()
    for field in dataclasses.fields(result.request.metadata):
        text = str(getattr(result.request.metadata, field.name))
        assert "ANTHROPIC_API_KEY" not in text
        assert "sk-" not in text


def test_unsupported_optional_generation_parameter_is_a_warning_not_an_error():
    result = _prepare(
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="fake-model"),
        generation_parameters=LLMGenerationParameters(temperature=0.5),
    )
    assert any("temperature" in warning for warning in result.warnings)


def test_provider_mismatch_is_detected_defensively():
    registry = LLMProviderRegistry()
    # Register the adapter under a DIFFERENT key than its own declared
    # provider_id() - an intentionally misconfigured registry.
    registry.register("mislabeled", FakeLLMProviderAdapter(provider_id="fake"))

    with pytest.raises(ProviderMismatchError):
        _prepare(
            registry=registry,
            provider_selection=LLMProviderSelection(provider_id="mislabeled"),
            model_selection=LLMModelSelection(model_identifier="fake-model"),
        )


def test_preparation_is_deterministic_given_identical_inputs():
    first = _prepare()
    second = _prepare()
    assert first.request == second.request
    assert first.prepared_request == second.prepared_request
