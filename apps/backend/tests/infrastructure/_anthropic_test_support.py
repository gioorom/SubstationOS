"""
Shared, non-collected helpers for constructing synthetic Anthropic SDK
objects (a real ``httpx.Request``/``Response`` pair, real SDK exception
instances, a real ``anthropic.types.Message``) - never a network call,
never a mock of the SDK's own types. Reused across the error-mapper,
response-mapper, and invoker test modules (EPIC 4, Milestone 17).
Prefixed with an underscore so pytest never tries to collect it as a
test module itself.
"""

from __future__ import annotations

import httpx
from anthropic.types import Message, TextBlock, Usage


def make_httpx_response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code, headers=headers or {}, request=request)


def make_message(
    *,
    message_id: str = "msg_test",
    model: str = "claude-test-model",
    text: str = "This is a test response.",
    stop_reason: str | None = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    content: list | None = None,
) -> Message:
    return Message(
        id=message_id,
        content=content if content is not None else [TextBlock(type="text", text=text)],
        model=model,
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
