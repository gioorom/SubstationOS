"""
A documented, deliberately approximate, provider-independent token
estimate (Milestone 15) - never a real tokenizer. Every real tokenizer
(``tiktoken`` for OpenAI, Anthropic's own tokenizer, ...) is
provider-specific; depending on one here would violate Prompt Builder's
"no provider SDK" boundary before an LLM Provider Abstraction Layer
even exists. The formula is a widely used rough English-text
approximation (~4 characters per token), fixed and versioned as part of
``composition_policy.COMPOSITION_POLICY_VERSION`` - never claimed to be
precise.
"""

from __future__ import annotations

from app.domain.prompt_builder.composition_policy import (
    CHARACTERS_PER_ESTIMATED_TOKEN,
)


def estimate_tokens(lines: tuple[str, ...]) -> int:
    text = " ".join(lines)

    if not text:
        return 0

    return max(1, len(text) // CHARACTERS_PER_ESTIMATED_TOKEN)
