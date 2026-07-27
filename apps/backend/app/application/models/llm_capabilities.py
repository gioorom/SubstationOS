"""
The provider-neutral capability vocabulary (EPIC 4, Milestone 16). A
closed, exhaustive set of capabilities any language-model provider
adapter may declare support for - never a provider-specific concept,
never an open-ended free-form string. An adapter may only declare a
capability supported once its own ``prepare_request`` implementation
genuinely honors it; declaring a capability the adapter cannot actually
prepare a request for would silently mislead every caller that checks
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LLMCapability(str, Enum):
    TEXT_INPUT = "text_input"
    STRUCTURED_TEXT_INPUT = "structured_text_input"
    CONFIGURABLE_MAX_OUTPUT = "configurable_max_output"
    TEMPERATURE = "temperature"
    STOP_SEQUENCES = "stop_sequences"
    STREAMING = "streaming"
    TOOL_USE = "tool_use"
    STRUCTURED_OUTPUT = "structured_output"
    MULTIMODAL_INPUT = "multimodal_input"


@dataclass(frozen=True, slots=True)
class LLMProviderCapabilities:
    """What one configured provider adapter actually declares support
    for - always echoed alongside a prepared request so a caller can
    see exactly which capabilities were available when the request was
    prepared."""

    provider_id: str
    supported: frozenset[LLMCapability]


@dataclass(frozen=True, slots=True)
class LLMCapabilityValidationResult:
    """
    Whether every *required* capability was supported by the resolved
    adapter. A missing required capability is an impossible state for
    request preparation to proceed (see
    ``llm_exceptions.UnsupportedCapabilityError`` - raised, never
    silently downgraded); this result exists so a caller can inspect
    the outcome without re-deriving it, and so a future capability
    that is merely *requested but optional* can be reported here as a
    warning rather than a hard failure.
    """

    valid: bool
    missing_required_capabilities: tuple[LLMCapability, ...]
    unsupported_requested_capabilities: tuple[LLMCapability, ...]
