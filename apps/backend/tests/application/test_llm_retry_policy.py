from __future__ import annotations

import random

import pytest

from app.application.models.llm_invocation import (
    LLMProviderErrorCategory,
    LLMRetryPolicy,
)
from app.application.policies.llm_retry_policy import (
    RETRYABLE_CATEGORIES,
    LLMRetryDecisionMaker,
)

ALL_CATEGORIES = set(LLMProviderErrorCategory)
NON_RETRYABLE_CATEGORIES = ALL_CATEGORIES - RETRYABLE_CATEGORIES


def _policy(**overrides) -> LLMRetryPolicy:
    defaults = dict(
        version="1.0",
        max_attempts=3,
        base_delay_seconds=1.0,
        max_delay_seconds=10.0,
        jitter_enabled=False,
    )
    defaults.update(overrides)
    return LLMRetryPolicy(**defaults)


@pytest.mark.parametrize(
    "category",
    [
        LLMProviderErrorCategory.CONNECTION_FAILURE,
        LLMProviderErrorCategory.CONNECTION_TIMEOUT,
        LLMProviderErrorCategory.READ_TIMEOUT,
        LLMProviderErrorCategory.RATE_LIMITED,
        LLMProviderErrorCategory.PROVIDER_OVERLOADED,
        LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
    ],
)
def test_retryable_categories_are_retried_on_a_fresh_attempt(category):
    decision = LLMRetryDecisionMaker.decide(
        error_category=category,
        attempt_number=1,
        policy=_policy(),
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(1),
    )
    assert decision.should_retry is True


@pytest.mark.parametrize(
    "category",
    [
        LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
        LLMProviderErrorCategory.AUTHORIZATION_FAILURE,
        LLMProviderErrorCategory.INVALID_REQUEST,
        LLMProviderErrorCategory.UNSUPPORTED_REQUEST,
        LLMProviderErrorCategory.MODEL_NOT_FOUND,
        LLMProviderErrorCategory.REQUEST_TOO_LARGE,
        LLMProviderErrorCategory.INVALID_CONFIGURATION,
        LLMProviderErrorCategory.RUNTIME_DISABLED,
        LLMProviderErrorCategory.CANCELLED,
        LLMProviderErrorCategory.CONTENT_POLICY_REJECTION,
        LLMProviderErrorCategory.TOTAL_DEADLINE_EXCEEDED,
        LLMProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
    ],
)
def test_non_retryable_categories_are_never_retried(category):
    decision = LLMRetryDecisionMaker.decide(
        error_category=category,
        attempt_number=1,
        policy=_policy(),
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(1),
    )
    assert decision.should_retry is False


def test_every_category_is_classified_exactly_once():
    # Documents the exhaustive mapping this milestone requires -
    # every LLMProviderErrorCategory value is either retryable or not,
    # with no gaps.
    assert RETRYABLE_CATEGORIES | NON_RETRYABLE_CATEGORIES == ALL_CATEGORIES
    assert RETRYABLE_CATEGORIES & NON_RETRYABLE_CATEGORIES == set()


def test_maximum_attempts_stops_retrying():
    policy = _policy(max_attempts=2)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.RATE_LIMITED,
        attempt_number=2,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(1),
    )
    assert decision.should_retry is False
    assert "maximum" in decision.reason.lower()


def test_backoff_is_exponential_and_bounded():
    policy = _policy(base_delay_seconds=1.0, max_delay_seconds=100.0, max_attempts=10)

    first = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )
    second = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=2,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )
    third = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=3,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )

    assert first.delay_seconds == pytest.approx(1.0)
    assert second.delay_seconds == pytest.approx(2.0)
    assert third.delay_seconds == pytest.approx(4.0)


def test_delay_is_capped_at_max_delay_seconds():
    policy = _policy(base_delay_seconds=1.0, max_delay_seconds=3.0, max_attempts=10)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=5,  # would be 16s uncapped
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )
    assert decision.delay_seconds == pytest.approx(3.0)


def test_retry_after_hint_is_respected_but_still_bounded():
    policy = _policy(base_delay_seconds=1.0, max_delay_seconds=5.0)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.RATE_LIMITED,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=100.0,  # far beyond max_delay
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )
    assert decision.delay_seconds == pytest.approx(5.0)


def test_retry_after_hint_below_backoff_does_not_shrink_the_delay():
    policy = _policy(base_delay_seconds=2.0, max_delay_seconds=10.0)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.RATE_LIMITED,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=0.1,
        remaining_deadline_seconds=1000.0,
        random_source=random.Random(1),
    )
    assert decision.delay_seconds == pytest.approx(2.0)


def test_jitter_is_deterministic_for_a_seeded_random_source():
    policy = _policy(base_delay_seconds=1.0, max_delay_seconds=10.0, jitter_enabled=True)

    first = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(42),
    )
    second = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(42),
    )

    assert first.delay_seconds == second.delay_seconds
    # Jitter perturbs the base 1.0s delay within +/-20%.
    assert 0.8 <= first.delay_seconds <= 1.2


def test_jitter_disabled_produces_exact_backoff():
    policy = _policy(base_delay_seconds=1.0, max_delay_seconds=10.0, jitter_enabled=False)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=100.0,
        random_source=random.Random(999),
    )
    assert decision.delay_seconds == pytest.approx(1.0)


def test_insufficient_remaining_deadline_prevents_another_attempt():
    policy = _policy(base_delay_seconds=5.0, max_delay_seconds=10.0)
    decision = LLMRetryDecisionMaker.decide(
        error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
        attempt_number=1,
        policy=policy,
        retry_after_seconds=None,
        remaining_deadline_seconds=2.0,  # less than the 5s delay
        random_source=random.Random(1),
    )
    assert decision.should_retry is False
    assert "deadline" in decision.reason.lower()
