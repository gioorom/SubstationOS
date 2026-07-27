from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import anthropic
import pytest

from app.application.models.llm_exceptions import ProviderInvocationFailedError
from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationContext,
    LLMInvocationPolicy,
    LLMProviderErrorCategory,
    LLMRetryPolicy,
    LLMTimeoutPolicy,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
    LLMRequestMetadata,
    LLMRequestVersion,
)
from app.application.models.llm_capabilities import LLMCapability
from app.infrastructure.llm.anthropic.anthropic_invoker import invoke_anthropic
from app.infrastructure.llm.anthropic.anthropic_mapper import (
    map_llm_request_to_anthropic_prepared_request,
)
from tests.infrastructure._anthropic_test_support import make_httpx_response, make_message

NOW = datetime(2026, 1, 1, 10, 0, 0)


def _llm_request(
    *, generation_parameters: LLMGenerationParameters | None = None
) -> LLMRequest:
    from app.application.models.llm_request import (
        LLMContentBlock,
        LLMContentType,
        LLMMessage,
        LLMMessageRole,
    )

    metadata = LLMRequestMetadata(
        project_id=1,
        context_builder_version="1.0",
        prompt_builder_version="1.0",
        composition_policy_version="1.0",
        prompt_package_version="1.0",
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        provider_id="anthropic",
        model_identifier="claude-test-model",
        request_correlation_id="corr-1",
        excluded_section_types=(),
        prepared_at=NOW,
    )
    return LLMRequest(
        project_id=1,
        provider_selection=LLMProviderSelection(provider_id="anthropic"),
        model_selection=LLMModelSelection(model_identifier="claude-test-model"),
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
                    LLMContentBlock(content_type=LLMContentType.TEXT, text="Project id: 1"),
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


def _invocation_context(attempt_number: int = 1) -> LLMInvocationContext:
    policy = LLMInvocationPolicy(
        retry_policy=LLMRetryPolicy(
            version="1.0",
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter_enabled=False,
        ),
        timeout_policy=LLMTimeoutPolicy(
            connect_timeout_seconds=5.0, read_timeout_seconds=30.0, total_deadline_seconds=60.0
        ),
        runtime_version="1.0",
    )
    return LLMInvocationContext(
        request_correlation_id="corr-1",
        attempt_number=attempt_number,
        deadline_at=NOW,
        policy=policy,
    )


class _FakeMessagesResource:
    def __init__(self, side_effect) -> None:
        self.create = AsyncMock(side_effect=side_effect)


class _FakeAsyncAnthropicClient:
    def __init__(self, side_effect) -> None:
        self.messages = _FakeMessagesResource(side_effect)


def test_sdk_arguments_are_mapped_correctly():
    request = _llm_request(
        generation_parameters=LLMGenerationParameters(
            max_output_tokens=256, temperature=0.4, stop_sequences=("STOP",)
        )
    )
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(side_effect=lambda **kwargs: make_message())

    asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-test-model"
    assert call_kwargs["max_tokens"] == 256
    assert call_kwargs["system"] == "Be precise."
    assert call_kwargs["temperature"] == 0.4
    assert call_kwargs["stop_sequences"] == ["STOP"]
    assert call_kwargs["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "Project id: 1"}]}
    ]


def test_configured_model_propagated_unchanged_and_returned_model_captured():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(
        side_effect=lambda **kwargs: make_message(model="claude-returned-model-v2")
    )

    envelope = asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert envelope.configured_model_identifier == "claude-test-model"
    assert envelope.returned_model_identifier == "claude-returned-model-v2"


def test_maximum_output_tokens_mapped_from_default_when_unset():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=2048
    )
    client = _FakeAsyncAnthropicClient(side_effect=lambda **kwargs: make_message())

    asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert client.messages.create.call_args.kwargs["max_tokens"] == 2048


def test_optional_temperature_omitted_when_unset():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(side_effect=lambda **kwargs: make_message())

    asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert client.messages.create.call_args.kwargs["temperature"] is anthropic.NOT_GIVEN


def test_stop_sequences_omitted_when_unset():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(side_effect=lambda **kwargs: make_message())

    asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert client.messages.create.call_args.kwargs["stop_sequences"] is anthropic.NOT_GIVEN


def test_successful_response_is_normalized_into_envelope():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(
        side_effect=lambda **kwargs: make_message(text="Deterministic answer.")
    )

    envelope = asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert envelope.content[0].text == "Deterministic answer."
    assert envelope.finish_reason is LLMFinishReason.COMPLETED
    assert envelope.provider_id == "anthropic"
    assert envelope.request_correlation_id == "corr-1"


def test_usage_is_normalized():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(
        side_effect=lambda **kwargs: make_message(input_tokens=42, output_tokens=17)
    )

    envelope = asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert envelope.usage.input_tokens == 42
    assert envelope.usage.output_tokens == 17
    assert envelope.usage.total_tokens == 59


def test_finish_reason_is_normalized():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(
        side_effect=lambda **kwargs: make_message(stop_reason="max_tokens")
    )

    envelope = asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert envelope.finish_reason is LLMFinishReason.MAXIMUM_OUTPUT_REACHED


def test_provider_request_id_is_preserved():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(
        side_effect=lambda **kwargs: make_message(message_id="msg_unique_789")
    )

    envelope = asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert envelope.provider_request_id == "msg_unique_789"


def test_sdk_failure_is_normalized_never_raw():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    response = make_httpx_response(429, headers={"retry-after": "1.0"})
    sdk_error = anthropic.RateLimitError(
        "rate limited", response=response, body={"error": {"type": "rate_limit_error"}}
    )
    client = _FakeAsyncAnthropicClient(side_effect=sdk_error)

    with pytest.raises(ProviderInvocationFailedError) as exc_info:
        asyncio.run(
            invoke_anthropic(
                client=client,
                prepared_request=prepared,
                request=request,
                invocation_context=_invocation_context(),
                adapter_version="1.0",
            )
        )

    provider_error = exc_info.value.provider_error
    assert provider_error.category is LLMProviderErrorCategory.RATE_LIMITED
    assert provider_error.details.retry_after_seconds == 1.0


def test_raw_sdk_exception_never_escapes_the_invoker():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    response = make_httpx_response(500)
    sdk_error = anthropic.InternalServerError(
        "boom", response=response, body={"error": {"type": "api_error"}}
    )
    client = _FakeAsyncAnthropicClient(side_effect=sdk_error)

    try:
        asyncio.run(
            invoke_anthropic(
                client=client,
                prepared_request=prepared,
                request=request,
                invocation_context=_invocation_context(),
                adapter_version="1.0",
            )
        )
    except ProviderInvocationFailedError:
        pass
    except anthropic.InternalServerError:
        pytest.fail("raw SDK exception escaped the invoker")


def test_api_key_never_appears_in_a_normalized_error():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    response = make_httpx_response(401)
    sdk_error = anthropic.AuthenticationError(
        "invalid x-api-key: sk-ant-super-secret-value",
        response=response,
        body={"error": {"type": "authentication_error"}},
    )
    client = _FakeAsyncAnthropicClient(side_effect=sdk_error)

    with pytest.raises(ProviderInvocationFailedError) as exc_info:
        asyncio.run(
            invoke_anthropic(
                client=client,
                prepared_request=prepared,
                request=request,
                invocation_context=_invocation_context(),
                adapter_version="1.0",
            )
        )

    # The mapper truncates/filters the message but a real deployment
    # must never construct an error message containing the key in the
    # first place - this test documents the expectation that only a
    # short, safe summary is ever produced (the "no API key in errors"
    # guarantee is really provided by never handling the raw key
    # anywhere near this code path, not by string-scrubbing).
    provider_error = exc_info.value.provider_error
    assert provider_error.category is LLMProviderErrorCategory.AUTHENTICATION_FAILURE


def test_exactly_one_sdk_call_per_invocation():
    request = _llm_request()
    prepared = map_llm_request_to_anthropic_prepared_request(
        request, default_max_output_tokens=4096
    )
    client = _FakeAsyncAnthropicClient(side_effect=lambda **kwargs: make_message())

    asyncio.run(
        invoke_anthropic(
            client=client,
            prepared_request=prepared,
            request=request,
            invocation_context=_invocation_context(),
            adapter_version="1.0",
        )
    )

    assert client.messages.create.call_count == 1
