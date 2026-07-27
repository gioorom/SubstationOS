"""
Deterministic mapping: provider-neutral ``LLMRequest`` -> local
``AnthropicPreparedRequest`` (EPIC 4, Milestone 16). Anthropic's
Messages API has no distinct "system" role inside its ``messages``
array - a system prompt is a separate top-level string - so
``LLMMessageRole.INSTRUCTION`` content is concatenated into
``AnthropicPreparedRequest.system``, and every other (conversational)
role's content becomes content blocks on a single synthetic
``role="user"`` message (Anthropic requires at least one message,
starting with ``user``). This milestone's ``PromptPackage`` never
produces an actual end-user question or a prior assistant turn (no
conversation exists yet - see ``LLMMessageRole``'s own docstring), so
today every non-instruction section lands on that one synthetic
message; Milestone 17 (LLM Invocation Runtime) is expected to append a
real, additional user turn once one exists, not to change this
mapping's own system/conversational split.
"""

from __future__ import annotations

from app.application.models.llm_exceptions import ProviderRequestMappingError
from app.application.models.llm_request import LLMMessageRole, LLMRequest
from app.infrastructure.llm.anthropic.anthropic_models import (
    AnthropicContentBlock,
    AnthropicMessage,
    AnthropicPreparedRequest,
)

_SYSTEM_ROLES = frozenset({LLMMessageRole.INSTRUCTION})


def _system_text(request: LLMRequest) -> str:
    lines = [
        block.text
        for message in request.messages
        if message.role in _SYSTEM_ROLES
        for block in message.content_blocks
    ]

    return "\n".join(lines)


def _conversational_content_blocks(
    request: LLMRequest,
) -> tuple[AnthropicContentBlock, ...]:
    return tuple(
        AnthropicContentBlock(type="text", text=block.text)
        for message in request.messages
        if message.role not in _SYSTEM_ROLES
        for block in message.content_blocks
    )


def map_llm_request_to_anthropic_prepared_request(
    request: LLMRequest, *, default_max_output_tokens: int
) -> AnthropicPreparedRequest:
    system_text = _system_text(request)
    conversational_blocks = _conversational_content_blocks(request)

    if not conversational_blocks:
        raise ProviderRequestMappingError(
            "anthropic",
            "No conversational content is available to populate the "
            "required Anthropic 'messages' array.",
        )

    messages = (AnthropicMessage(role="user", content=conversational_blocks),)

    max_tokens = (
        request.generation_parameters.max_output_tokens
        or default_max_output_tokens
    )

    return AnthropicPreparedRequest(
        model=request.model_selection.model_identifier,
        system=system_text,
        messages=messages,
        max_tokens=max_tokens,
        temperature=request.generation_parameters.temperature,
        stop_sequences=request.generation_parameters.stop_sequences,
        trace_metadata=(
            ("request_correlation_id", request.metadata.request_correlation_id),
            ("project_id", str(request.metadata.project_id)),
        ),
    )
