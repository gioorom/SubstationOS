"""
Local, immutable representations of an Anthropic Messages API request
(EPIC 4, Milestone 16) - **never** an Anthropic SDK object, never
serialized, never sent over the network. These types mirror the
*shape* of a real Anthropic request only because that shape is what a
future invocation runtime (Milestone 17) will eventually need to send;
nothing here imports the ``anthropic`` package.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnthropicContentBlock:
    type: str
    text: str


@dataclass(frozen=True, slots=True)
class AnthropicMessage:
    role: str
    content: tuple[AnthropicContentBlock, ...]


@dataclass(frozen=True, slots=True)
class AnthropicPreparedRequest:
    """
    A local stand-in for what would become an Anthropic Messages API
    request body. ``provider_id`` satisfies the application layer's
    ``PreparedProviderRequest`` structural protocol
    (``app.application.models.llm_request``) without that module ever
    importing this one.
    """

    model: str
    system: str
    messages: tuple[AnthropicMessage, ...]
    max_tokens: int
    temperature: float | None
    stop_sequences: tuple[str, ...]
    trace_metadata: tuple[tuple[str, str], ...] = ()
    provider_id: str = "anthropic"
