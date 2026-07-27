from __future__ import annotations

import pytest

from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMProviderCapabilities,
)
from app.application.models.llm_request import (
    LLMContentBlock,
    LLMContentType,
    LLMGenerationParameters,
    LLMMessage,
    LLMMessageRole,
    LLMModelSelection,
    LLMProviderSelection,
)


def test_llm_message_role_is_a_closed_semantic_set():
    values = {role.value for role in LLMMessageRole}
    assert values == {"instruction", "context", "user", "assistant", "tool"}


def test_llm_content_type_is_a_closed_set():
    values = {content_type.value for content_type in LLMContentType}
    assert values == {"text", "structured_data", "reference"}


def test_request_objects_are_immutable():
    block = LLMContentBlock(content_type=LLMContentType.TEXT, text="hello")
    with pytest.raises(AttributeError):
        block.text = "changed"  # type: ignore[misc]

    message = LLMMessage(
        role=LLMMessageRole.INSTRUCTION,
        section_type="system_context",
        content_blocks=(block,),
    )
    with pytest.raises(AttributeError):
        message.role = LLMMessageRole.CONTEXT  # type: ignore[misc]


def test_generation_parameters_default_to_no_forced_value():
    parameters = LLMGenerationParameters()
    assert parameters.max_output_tokens is None
    assert parameters.temperature is None
    assert parameters.stop_sequences == ()
    assert parameters.deterministic_preference is False


def test_provider_and_model_selection_are_opaque_strings():
    provider = LLMProviderSelection(provider_id="anthropic")
    model = LLMModelSelection(model_identifier="whatever-string-the-operator-configures")
    assert provider.provider_id == "anthropic"
    assert model.model_identifier == "whatever-string-the-operator-configures"


def test_provider_capabilities_are_a_frozen_declared_set():
    capabilities = LLMProviderCapabilities(
        provider_id="anthropic",
        supported=frozenset({LLMCapability.TEXT_INPUT}),
    )
    assert LLMCapability.TEXT_INPUT in capabilities.supported
    assert LLMCapability.STREAMING not in capabilities.supported


def test_two_requests_built_from_equal_fields_are_equal():
    block_a = LLMContentBlock(content_type=LLMContentType.TEXT, text="x")
    block_b = LLMContentBlock(content_type=LLMContentType.TEXT, text="x")
    assert block_a == block_b
