"""
Constructs the official Anthropic async SDK client (EPIC 4, Milestone
17) - the **one** place in this codebase allowed to import
``anthropic`` for the new, governed invocation path (the pre-existing
legacy ``app/services/ai/claude_provider.py`` is separate, isolated
code - see ADR-0009/ADR-0014). Never called unless invocation is
enabled and a credential is present; the credential itself is read by
the composition root (``app/routers/llm_provider.py``) and passed in
here as a plain argument - this module never reads an environment
variable directly.

The client is configured with ``max_retries=0``: the LLM Invocation
Runtime (``app.application.services.llm_runtime``) owns every retry
decision, so the SDK must never retry on its own - stacked retries
between the SDK and the runtime would silently multiply attempts
neither layer accounts for.
"""

from __future__ import annotations

import httpx
from anthropic import AsyncAnthropic


def build_anthropic_client(
    *,
    api_key: str,
    connect_timeout_seconds: float,
    read_timeout_seconds: float,
) -> AsyncAnthropic:
    timeout = httpx.Timeout(
        connect=connect_timeout_seconds,
        read=read_timeout_seconds,
        write=read_timeout_seconds,
        pool=connect_timeout_seconds,
    )

    return AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=0)
