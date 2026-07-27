"""
Normalizes a successful Anthropic SDK ``Message`` response into the
provider-neutral content/finish-reason/usage pieces of an
``LLMResponseEnvelope`` (EPIC 4, Milestone 17). Never returns the SDK
``Message`` object itself, never invents a citation or annotation, and
never silently reinterprets an unsupported content block as text.

Finish-reason mapping (Anthropic's ``StopReason`` ->
``LLMFinishReason``):

| Anthropic ``stop_reason`` | Normalized                    |
|---------------------------|--------------------------------|
| ``end_turn``               | ``COMPLETED``                  |
| ``max_tokens``             | ``MAXIMUM_OUTPUT_REACHED``     |
| ``stop_sequence``          | ``STOP_SEQUENCE``              |
| ``tool_use``               | ``TOOL_REQUEST``                |
| ``refusal``                | ``REFUSAL``                    |
| ``pause_turn`` / ``None`` / anything else | ``UNKNOWN`` (with a warning) |
"""

from __future__ import annotations

from anthropic.types import Message

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMResponseContent,
    LLMResponseContentType,
    LLMUsage,
)

_FINISH_REASON_BY_STOP_REASON: dict[str, LLMFinishReason] = {
    "end_turn": LLMFinishReason.COMPLETED,
    "max_tokens": LLMFinishReason.MAXIMUM_OUTPUT_REACHED,
    "stop_sequence": LLMFinishReason.STOP_SEQUENCE,
    "tool_use": LLMFinishReason.TOOL_REQUEST,
    "refusal": LLMFinishReason.REFUSAL,
}


def map_finish_reason(stop_reason: str | None) -> tuple[LLMFinishReason, tuple[str, ...]]:
    if stop_reason is None:
        return LLMFinishReason.UNKNOWN, ("Provider returned no stop reason.",)

    finish_reason = _FINISH_REASON_BY_STOP_REASON.get(stop_reason)
    if finish_reason is None:
        return (
            LLMFinishReason.UNKNOWN,
            (f"Unrecognized provider stop reason: '{stop_reason}'.",),
        )

    return finish_reason, ()


def map_content(message: Message) -> tuple[tuple[LLMResponseContent, ...], tuple[str, ...]]:
    content: list[LLMResponseContent] = []
    warnings: list[str] = []

    for index, block in enumerate(message.content):
        block_type = getattr(block, "type", None)

        if block_type == "text":
            content.append(
                LLMResponseContent(
                    sequence_index=index,
                    content_type=LLMResponseContentType.TEXT,
                    text=block.text,
                    provider_block_type=block_type,
                    annotations=(),
                )
            )
        else:
            content.append(
                LLMResponseContent(
                    sequence_index=index,
                    content_type=LLMResponseContentType.UNSUPPORTED,
                    text="",
                    provider_block_type=block_type,
                    annotations=(),
                )
            )
            warnings.append(
                f"Unsupported provider content block type: '{block_type}'."
            )

    return tuple(content), tuple(warnings)


def map_usage(message: Message) -> LLMUsage:
    usage = message.usage

    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )

    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=getattr(usage, "cache_read_input_tokens", None),
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", None),
    )
