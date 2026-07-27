"""
The provider-neutral response contract (EPIC 4, Milestone 16) - a
placeholder, forward-compatible normalized envelope. **Not populated or
returned by any code path in this milestone**: no LLM invocation exists
yet (see the milestone's explicit non-goals). Reserved for Milestone 17
(LLM Invocation Runtime), which will populate it from a real,
provider-specific response after translating that response back into
this neutral shape - the same "provider knowledge stays in the
adapter" discipline this milestone's request side already establishes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMResponseEnvelope:
    request_correlation_id: str
    provider_id: str
    model_identifier: str
    content: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
