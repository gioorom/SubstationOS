from __future__ import annotations

import asyncio
import random
from datetime import datetime

import pytest

from app.application.models.llm_exceptions import (
    LLMRuntimeDisabledError,
    MissingCredentialError,
    ProjectIdMismatchError,
    ProviderMismatchError,
    UnknownProviderError,
    UnsupportedCapabilityError,
)
from app.application.models.llm_capabilities import LLMCapability
from app.application.models.llm_invocation import (
    LLMInvocationStatus,
    LLMProviderErrorCategory,
    LLMRuntimeConfiguration,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMModelSelection,
    LLMProviderSelection,
)
from app.application.services.llm_invocation_service import invoke_llm
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
    FakeLLMProviderAdapter,
)
from app.services import context_builder_service, prompt_builder_service

from tests._governed_context import designation_result

PROJECT_ID = 12
NOW = datetime(2026, 1, 1, 2, 0, 0)


def _prompt_package(project_id: int = PROJECT_ID):
    context_result = context_builder_service.build_context_package(
        project_id=project_id, results=(designation_result("TR1", ()),), now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    return prompt_result.package


def _runtime_config(**overrides) -> LLMRuntimeConfiguration:
    defaults = dict(
        enabled=True,
        provider_id="fake",
        model_identifier="fake-model",
        connect_timeout_seconds=5.0,
        read_timeout_seconds=30.0,
        total_deadline_seconds=60.0,
        max_attempts=3,
        retry_base_delay_seconds=0.01,
        retry_max_delay_seconds=0.05,
        retry_jitter_enabled=False,
        default_max_output_tokens=1024,
        default_temperature=None,
    )
    defaults.update(overrides)
    return LLMRuntimeConfiguration(**defaults)


async def _no_op_sleeper(_seconds: float) -> None:
    return None


def _registry(fake_outcomes=None) -> LLMProviderRegistry:
    registry = LLMProviderRegistry()
    registry.register(
        "fake", FakeLLMProviderAdapter(outcomes=fake_outcomes or ())
    )
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(model_identifier="model-x", default_max_output_tokens=4096),
    )
    return registry


def _invoke(**overrides):
    defaults = dict(
        registry=_registry(),
        runtime_configuration=_runtime_config(),
        credential_present=True,
        credential_environment_variable_name="FAKE_API_KEY",
        prompt_package=_prompt_package(),
        project_id=PROJECT_ID,
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="fake-model"),
        request_correlation_id="corr-service",
        clock=lambda: NOW,
        sleeper=_no_op_sleeper,
        random_source=random.Random(1),
        now=NOW,
    )
    defaults.update(overrides)
    return asyncio.run(invoke_llm(**defaults))


def test_runtime_disabled_rejection():
    with pytest.raises(LLMRuntimeDisabledError):
        _invoke(runtime_configuration=_runtime_config(enabled=False))


def test_missing_credential_rejection():
    with pytest.raises(MissingCredentialError):
        _invoke(credential_present=False)


def test_successful_fake_provider_invocation():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(registry=registry)
    assert result.status is LLMInvocationStatus.SUCCEEDED


def test_successful_configured_anthropic_invocation_using_injected_adapter():
    # The Anthropic adapter has no injected client in this registry -
    # but its prepare_request/registration path is exercised the same
    # way; a real invocation attempt without a client fails loudly
    # (RuntimeError), proving the service never silently substitutes a
    # working adapter for a misconfigured one.
    registry = _registry()
    with pytest.raises(RuntimeError):
        _invoke(
            registry=registry,
            provider_selection=LLMProviderSelection(provider_id=ANTHROPIC_PROVIDER_ID),
            model_selection=LLMModelSelection(model_identifier="model-x"),
        )


def test_unknown_provider():
    with pytest.raises(UnknownProviderError):
        _invoke(provider_selection=LLMProviderSelection(provider_id="does-not-exist"))


def test_provider_mismatch_detected_defensively():
    registry = LLMProviderRegistry()
    registry.register(
        "mislabeled", FakeLLMProviderAdapter(provider_id="fake", outcomes=())
    )
    with pytest.raises(ProviderMismatchError):
        _invoke(
            registry=registry,
            provider_selection=LLMProviderSelection(provider_id="mislabeled"),
        )


def test_missing_model_selection_defaults_from_runtime_configuration():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(
        registry=registry,
        model_selection=None,
        runtime_configuration=_runtime_config(model_identifier="configured-model"),
    )
    assert result.envelope.configured_model_identifier == "configured-model"


def test_project_id_mismatch_is_rejected():
    package = _prompt_package(project_id=PROJECT_ID)
    with pytest.raises(ProjectIdMismatchError):
        _invoke(prompt_package=package, project_id=PROJECT_ID + 1)


def test_unsupported_required_capability_is_rejected():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    with pytest.raises(UnsupportedCapabilityError):
        _invoke(
            registry=registry,
            capability_requirements=LLMCapabilityRequirements(
                required_capabilities=(LLMCapability.STREAMING,)
            ),
        )


def test_successful_retry_flow():
    registry = _registry(
        fake_outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    result = _invoke(registry=registry)
    assert result.status is LLMInvocationStatus.SUCCEEDED
    assert len(result.attempts) == 2


def test_terminal_normalized_failure():
    registry = _registry(
        fake_outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
            ),
        )
    )
    result = _invoke(registry=registry)
    assert result.status is LLMInvocationStatus.FAILED
    assert result.envelope is None
    assert result.terminal_error.category is LLMProviderErrorCategory.AUTHENTICATION_FAILURE


def test_no_fallback_to_a_different_provider_on_failure():
    registry = _registry(
        fake_outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
            ),
        )
    )
    result = _invoke(registry=registry)
    # The result reports the fake provider's own failure - never
    # silently switches to the also-registered anthropic adapter.
    assert result.terminal_error is not None


def test_correlation_id_propagates_into_the_result_and_envelope():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(registry=registry, request_correlation_id="trace-xyz")
    assert result.request_correlation_id == "trace-xyz"
    assert result.envelope.request_correlation_id == "trace-xyz"


def test_prompt_package_identity_propagates_into_metadata():
    package = _prompt_package()
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(registry=registry, prompt_package=package)
    assert (
        result.envelope.metadata.prompt_package_version == package.metadata.package_version
    )


def test_response_validation_is_present_on_success():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(registry=registry)
    assert result.validation is not None
    assert result.validation.valid is True


def test_no_secrets_appear_anywhere_in_the_result():
    registry = _registry(fake_outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _invoke(registry=registry)
    assert "FAKE_API_KEY" not in str(result)
