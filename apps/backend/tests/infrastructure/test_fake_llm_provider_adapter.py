from __future__ import annotations

from datetime import datetime

from app.application.models.llm_capabilities import LLMCapability
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMContentBlock,
    LLMContentType,
    LLMGenerationParameters,
    LLMMessage,
    LLMMessageRole,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
    LLMRequestMetadata,
    LLMRequestVersion,
)
from app.application.ports.llm_provider_port import LLMProviderPort
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeLLMProviderAdapter,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


def _request(*, generation_parameters: LLMGenerationParameters | None = None) -> LLMRequest:
    metadata = LLMRequestMetadata(
        project_id=2,
        context_builder_version="1.0",
        prompt_builder_version="1.0",
        composition_policy_version="1.0",
        prompt_package_version="1.0",
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        provider_id="fake",
        model_identifier="fake-model",
        request_correlation_id="corr-1",
        excluded_section_types=(),
        prepared_at=NOW,
    )
    return LLMRequest(
        project_id=2,
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="fake-model"),
        messages=(
            LLMMessage(
                role=LLMMessageRole.INSTRUCTION,
                section_type="system_context",
                content_blocks=(
                    LLMContentBlock(content_type=LLMContentType.TEXT, text="Be precise."),
                ),
            ),
            LLMMessage(
                role=LLMMessageRole.CONTEXT,
                section_type="engineering_context",
                content_blocks=(
                    LLMContentBlock(content_type=LLMContentType.TEXT, text="Project id: 2"),
                ),
            ),
        ),
        references=(),
        generation_parameters=generation_parameters or LLMGenerationParameters(),
        capability_requirements=LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        ),
        metadata=metadata,
        version=LLMRequestVersion(
            provider_abstraction_version="1.0",
            request_preparation_policy_version="1.0",
        ),
    )


def test_fake_adapter_satisfies_the_port_contract():
    adapter = FakeLLMProviderAdapter()
    assert isinstance(adapter, LLMProviderPort)


def test_fake_adapter_declares_configurable_capabilities():
    adapter = FakeLLMProviderAdapter(
        supported_capabilities=frozenset(
            {LLMCapability.TEXT_INPUT, LLMCapability.STREAMING}
        )
    )
    capabilities = adapter.provider_capabilities()
    assert LLMCapability.STREAMING in capabilities.supported


def test_fake_adapter_prepares_a_deterministic_request():
    adapter = FakeLLMProviderAdapter()
    request = _request()

    first = adapter.prepare_request(request)
    second = adapter.prepare_request(request)
    assert first == second
    assert first.instruction_text == "Be precise."
    assert first.conversational_text == "Project id: 2"


def test_fake_adapter_reports_configured_validation_problems():
    adapter = FakeLLMProviderAdapter(configuration_problems=("misconfigured",))
    assert adapter.validate_configuration() == ("misconfigured",)


def test_fake_adapter_proves_provider_independence_from_anthropic():
    # The same neutral LLMRequest, prepared by a wholly different
    # adapter with no Anthropic-shaped output at all - proof the
    # application layer's contract is genuinely provider-neutral, not
    # secretly coupled to one provider's request shape.
    adapter = FakeLLMProviderAdapter()
    prepared = adapter.prepare_request(_request())
    assert not hasattr(prepared, "system")
    assert not hasattr(prepared, "messages")
    assert prepared.provider_id == "fake"


def test_fake_adapter_uses_default_max_output_tokens_when_unset():
    adapter = FakeLLMProviderAdapter(default_max_output_tokens=333)
    prepared = adapter.prepare_request(_request())
    assert prepared.max_tokens == 333
