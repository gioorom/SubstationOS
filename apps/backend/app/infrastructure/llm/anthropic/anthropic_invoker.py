"""
Performs exactly one Anthropic Messages API call for one runtime
attempt (EPIC 4, Milestone 17). Never retries internally (the LLM
Invocation Runtime owns every retry decision), never persists the
request or response, and never lets a raw SDK exception or response
object escape - every failure is normalized through
``anthropic_error_mapper`` before crossing back into
``app.application.services.llm_runtime``.

``asyncio.CancelledError`` deliberately is **not** caught here: it is a
``BaseException`` subclass in this Python version, so the bare
``except Exception`` below never intercepts it - real caller
cancellation during the awaited SDK call propagates untouched, exactly
as Milestone 17 requires ("do not convert cancellation into a
retryable provider error").
"""

from __future__ import annotations

from anthropic import AsyncAnthropic, NOT_GIVEN

from app.application.models.llm_exceptions import ProviderInvocationFailedError
from app.application.models.llm_invocation import (
    LLMInvocationContext,
    LLMInvocationStatus,
    LLMProviderError,
    LLMResponseEnvelope,
    LLMResponseMetadata,
)
from app.application.models.llm_request import LLMRequest
from app.infrastructure.llm.anthropic.anthropic_error_mapper import (
    map_anthropic_exception_to_provider_error,
)
from app.infrastructure.llm.anthropic.anthropic_models import AnthropicPreparedRequest
from app.infrastructure.llm.anthropic.anthropic_response_mapper import (
    map_content,
    map_finish_reason,
    map_usage,
)

ANTHROPIC_PROVIDER_ID = "anthropic"


async def invoke_anthropic(
    *,
    client: AsyncAnthropic,
    prepared_request: AnthropicPreparedRequest,
    request: LLMRequest,
    invocation_context: LLMInvocationContext,
    adapter_version: str,
) -> LLMResponseEnvelope:
    sdk_messages = [
        {
            "role": message.role,
            "content": [
                {"type": block.type, "text": block.text}
                for block in message.content
            ],
        }
        for message in prepared_request.messages
    ]

    try:
        message = await client.messages.create(
            model=prepared_request.model,
            max_tokens=prepared_request.max_tokens,
            system=prepared_request.system,
            messages=sdk_messages,
            temperature=(
                prepared_request.temperature
                if prepared_request.temperature is not None
                else NOT_GIVEN
            ),
            stop_sequences=(
                list(prepared_request.stop_sequences)
                if prepared_request.stop_sequences
                else NOT_GIVEN
            ),
        )
    except Exception as exc:  # noqa: BLE001 - normalized immediately below
        category, safe_message, details = map_anthropic_exception_to_provider_error(
            exc
        )
        raise ProviderInvocationFailedError(
            LLMProviderError(category=category, message=safe_message, details=details)
        ) from exc

    content, content_warnings = map_content(message)
    finish_reason, finish_warnings = map_finish_reason(message.stop_reason)
    usage = map_usage(message)

    return LLMResponseEnvelope(
        provider_id=ANTHROPIC_PROVIDER_ID,
        configured_model_identifier=request.model_selection.model_identifier,
        returned_model_identifier=message.model,
        content=content,
        finish_reason=finish_reason,
        usage=usage,
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id=invocation_context.request_correlation_id,
        provider_request_id=message.id,
        started_at=invocation_context.deadline_at,
        completed_at=invocation_context.deadline_at,
        latency_seconds=0.0,
        attempt_count=1,
        attempts=(),
        warnings=content_warnings + finish_warnings,
        metadata=LLMResponseMetadata(
            runtime_version=invocation_context.policy.runtime_version,
            adapter_version=adapter_version,
            request_preparation_policy_version=(
                request.version.request_preparation_policy_version
            ),
            prompt_package_version=request.metadata.prompt_package_version,
            context_builder_version=request.metadata.context_builder_version,
            prompt_builder_version=request.metadata.prompt_builder_version,
        ),
    )
