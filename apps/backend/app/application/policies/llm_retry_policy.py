"""
The fixed, documented, versioned retry policy for the LLM Invocation
Runtime (EPIC 4, Milestone 17). Classifies every
``LLMProviderErrorCategory`` into retryable or non-retryable exactly
once, here - no other module decides retryability. Bounded exponential
backoff with optional, injected (never global) jitter; every delay is
capped by ``LLMRetryPolicy.max_delay_seconds`` regardless of the
provider's own ``Retry-After`` hint or the computed backoff value.
"""

from __future__ import annotations

import random

from app.application.models.llm_invocation import (
    LLMProviderErrorCategory,
    LLMRetryDecision,
    LLMRetryPolicy,
)

RETRY_POLICY_VERSION = "1.0"

# A random +/-20% jitter band applied to the computed backoff delay
# when LLMRetryPolicy.jitter_enabled is True - fixed and documented, so
# a bump to this fraction is itself a policy-version change.
JITTER_FRACTION = 0.2

# Every category not listed here is non-retryable by definition - this
# is the single, authoritative classification (Milestone 17's own
# "the exact mapping must be documented and covered by tests" rule).
# UNKNOWN_PROVIDER_ERROR is deliberately non-retryable: an error this
# runtime cannot even categorize is treated conservatively, not
# assumed transient.
RETRYABLE_CATEGORIES: frozenset[LLMProviderErrorCategory] = frozenset(
    {
        LLMProviderErrorCategory.CONNECTION_FAILURE,
        LLMProviderErrorCategory.CONNECTION_TIMEOUT,
        LLMProviderErrorCategory.READ_TIMEOUT,
        LLMProviderErrorCategory.RATE_LIMITED,
        LLMProviderErrorCategory.PROVIDER_OVERLOADED,
        LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
    }
)


def _backoff_delay_seconds(
    attempt_number: int,
    policy: LLMRetryPolicy,
    retry_after_seconds: float | None,
    random_source: random.Random,
) -> float:
    computed = policy.base_delay_seconds * (2 ** (attempt_number - 1))
    delay = max(computed, retry_after_seconds or 0.0)
    delay = min(delay, policy.max_delay_seconds)

    if policy.jitter_enabled:
        jitter = random_source.uniform(-JITTER_FRACTION, JITTER_FRACTION)
        delay = delay * (1 + jitter)
        delay = max(0.0, min(delay, policy.max_delay_seconds))

    return delay


class LLMRetryDecisionMaker:
    @staticmethod
    def decide(
        *,
        error_category: LLMProviderErrorCategory,
        attempt_number: int,
        policy: LLMRetryPolicy,
        retry_after_seconds: float | None,
        remaining_deadline_seconds: float,
        random_source: random.Random,
    ) -> LLMRetryDecision:
        if error_category not in RETRYABLE_CATEGORIES:
            return LLMRetryDecision(
                should_retry=False,
                delay_seconds=0.0,
                reason=f"'{error_category.value}' is not retryable.",
            )

        if attempt_number >= policy.max_attempts:
            return LLMRetryDecision(
                should_retry=False,
                delay_seconds=0.0,
                reason=(
                    f"Maximum attempts ({policy.max_attempts}) already reached."
                ),
            )

        delay = _backoff_delay_seconds(
            attempt_number, policy, retry_after_seconds, random_source
        )

        if delay >= remaining_deadline_seconds:
            return LLMRetryDecision(
                should_retry=False,
                delay_seconds=0.0,
                reason=(
                    "Insufficient remaining deadline "
                    f"({remaining_deadline_seconds:.3f}s) for another "
                    f"attempt after a {delay:.3f}s retry delay."
                ),
            )

        return LLMRetryDecision(
            should_retry=True,
            delay_seconds=delay,
            reason=f"'{error_category.value}' is retryable.",
        )
