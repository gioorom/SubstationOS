from __future__ import annotations

from datetime import datetime

import pytest

from app.application.models.llm_capabilities import LLMCapability
from app.application.models.llm_exceptions import ProviderRequestMappingError
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
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.anthropic.anthropic_mapper import (
    map_llm_request_to_anthropic_prepared_request,
)

NOW = datetime(2026, 1, 1, 6, 0, 0)


def _metadata() -> LLMRequestMetadata:
    return LLMRequestMetadata(
        project_id=3,
        context_builder_version="1.0",
        prompt_builder_version="1.0",
        composition_policy_version="1.0",
        prompt_package_version="1.0",
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        provider_id=ANTHROPIC_PROVIDER_ID,
        model_identifier="model-x",
        request_correlation_id="corr-1",
        excluded_section_types=(),
        prepared_at=NOW,
    )


def _request(
    *,
    messages: tuple[LLMMessage, ...],
    generation_parameters: LLMGenerationParameters | None = None,
) -> LLMRequest:
    return LLMRequest(
        project_id=3,
        provider_selection=LLMProviderSelection(provider_id=ANTHROPIC_PROVIDER_ID),
        model_selection=LLMModelSelection(model_identifier="model-x"),
        messages=messages,
        references=(),
        generation_parameters=generation_parameters or LLMGenerationParameters(),
        capability_requirements=LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        ),
        metadata=_metadata(),
        version=LLMRequestVersion(
            provider_abstraction_version="1.0",
            request_preparation_policy_version="1.0",
        ),
    )


def _text_message(role: LLMMessageRole, *lines: str) -> LLMMessage:
    return LLMMessage(
        role=role,
        section_type="system_context" if role is LLMMessageRole.INSTRUCTION else "engineering_context",
        content_blocks=tuple(
            LLMContentBlock(content_type=LLMContentType.TEXT, text=line)
            for line in lines
        ),
    )


def test_system_instruction_mapping():
    request = _request(
        messages=(
            _text_message(LLMMessageRole.INSTRUCTION, "Be precise."),
            _text_message(LLMMessageRole.CONTEXT, "Project id: 3"),
        )
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert prepared.system == "Be precise."


def test_conversational_message_mapping():
    request = _request(
        messages=(
            _text_message(LLMMessageRole.INSTRUCTION, "Be precise."),
            _text_message(LLMMessageRole.CONTEXT, "Project id: 3", "Selected: C-001"),
        )
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert len(prepared.messages) == 1
    assert prepared.messages[0].role == "user"
    assert [b.text for b in prepared.messages[0].content] == [
        "Project id: 3",
        "Selected: C-001",
    ]


def test_model_identifier_propagation():
    request = _request(messages=(_text_message(LLMMessageRole.CONTEXT, "x"),))
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert prepared.model == "model-x"


def test_max_output_tokens_falls_back_to_adapter_default_when_unset():
    request = _request(messages=(_text_message(LLMMessageRole.CONTEXT, "x"),))
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=2048
    )
    assert prepared.max_tokens == 2048


def test_max_output_tokens_uses_requested_value_when_set():
    request = _request(
        messages=(_text_message(LLMMessageRole.CONTEXT, "x"),),
        generation_parameters=LLMGenerationParameters(max_output_tokens=777),
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=2048
    )
    assert prepared.max_tokens == 777


def test_temperature_mapping():
    request = _request(
        messages=(_text_message(LLMMessageRole.CONTEXT, "x"),),
        generation_parameters=LLMGenerationParameters(temperature=0.3),
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert prepared.temperature == 0.3


def test_stop_sequence_mapping():
    request = _request(
        messages=(_text_message(LLMMessageRole.CONTEXT, "x"),),
        generation_parameters=LLMGenerationParameters(stop_sequences=("STOP", "END")),
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert prepared.stop_sequences == ("STOP", "END")


def test_mapping_fails_explicitly_when_no_conversational_content_exists():
    request = _request(
        messages=(_text_message(LLMMessageRole.INSTRUCTION, "Only instructions."),)
    )
    with pytest.raises(ProviderRequestMappingError):
        map_llm_request_to_anthropic_prepared_request(
            request, default_max_output_tokens=4096
        )


def test_prepared_request_is_deterministic():
    request = _request(
        messages=(
            _text_message(LLMMessageRole.INSTRUCTION, "Be precise."),
            _text_message(LLMMessageRole.CONTEXT, "Project id: 3"),
        )
    )
    first = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    second = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    assert first == second


def test_capability_validation_declares_only_implemented_capabilities():
    adapter = AnthropicAdapter(model_identifier="model-x", default_max_output_tokens=4096)
    capabilities = adapter.provider_capabilities()

    assert LLMCapability.TEXT_INPUT in capabilities.supported
    assert LLMCapability.TEMPERATURE in capabilities.supported
    assert LLMCapability.STREAMING not in capabilities.supported
    assert LLMCapability.TOOL_USE not in capabilities.supported
    assert LLMCapability.MULTIMODAL_INPUT not in capabilities.supported


def test_validate_configuration_reports_a_blank_model_identifier():
    adapter = AnthropicAdapter(model_identifier="   ", default_max_output_tokens=4096)
    problems = adapter.validate_configuration()
    assert problems


def test_validate_configuration_is_clean_for_sane_configuration():
    adapter = AnthropicAdapter(model_identifier="model-x", default_max_output_tokens=4096)
    assert adapter.validate_configuration() == ()


def test_adapter_end_to_end_prepare_request_via_the_port():
    adapter = AnthropicAdapter(model_identifier="model-x", default_max_output_tokens=4096)
    request = _request(
        messages=(
            _text_message(LLMMessageRole.INSTRUCTION, "Be precise."),
            _text_message(LLMMessageRole.CONTEXT, "Project id: 3"),
        )
    )
    prepared = adapter.prepare_request(request)
    assert prepared.provider_id == ANTHROPIC_PROVIDER_ID
    assert prepared.model == "model-x"


def test_adapter_module_imports_no_network_or_provider_sdk_dependency():
    # A structural, not merely behavioral, proof: importing the module
    # succeeds with no network configuration or credential present -
    # this only works because the module never imports the anthropic
    # package or constructs a client. See the architecture tests for
    # the exhaustive import-boundary check.
    import app.infrastructure.llm.anthropic.anthropic_adapter as module

    assert not hasattr(module, "Anthropic")
