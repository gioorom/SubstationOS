from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

import pytest

from app.application.models.llm_exceptions import LLMInvocationCancelledError
from app.application.models.llm_invocation import (
    LLMInvocationPolicy,
    LLMInvocationStatus,
    LLMProviderErrorCategory,
    LLMRetryPolicy,
    LLMTimeoutPolicy,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
    LLMRequestMetadata,
    LLMRequestVersion,
)
from app.application.models.llm_capabilities import LLMCapability
from app.application.services.llm_runtime import run_invocation
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
    FakeLLMProviderAdapter,
)

NOW = datetime(2026, 1, 1, 9, 0, 0)


def _request() -> LLMRequest:
    metadata = LLMRequestMetadata(
        project_id=4,
        context_assembly_version="1.0",
        prompt_builder_version="1.0",
        composition_policy_version="1.0",
        prompt_package_version="1.0",
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        provider_id="fake",
        model_identifier="fake-model",
        request_correlation_id="corr-runtime",
        excluded_section_types=(),
        prepared_at=NOW,
    )
    return LLMRequest(
        project_id=4,
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="fake-model"),
        messages=(),
        references=(),
        generation_parameters=LLMGenerationParameters(),
        capability_requirements=LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        ),
        metadata=metadata,
        version=LLMRequestVersion(
            provider_abstraction_version="1.0",
            request_preparation_policy_version="1.0",
        ),
    )


def _policy(
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.01,
    max_delay_seconds: float = 0.05,
    jitter_enabled: bool = False,
    total_deadline_seconds: float = 60.0,
) -> LLMInvocationPolicy:
    return LLMInvocationPolicy(
        retry_policy=LLMRetryPolicy(
            version="1.0",
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_enabled=jitter_enabled,
        ),
        timeout_policy=LLMTimeoutPolicy(
            connect_timeout_seconds=5.0,
            read_timeout_seconds=30.0,
            total_deadline_seconds=total_deadline_seconds,
        ),
        runtime_version="1.0",
    )


class _FakeClock:
    """A deterministic, manually-advanced clock - each call returns the
    next queued timestamp, repeating the last one once exhausted."""

    def __init__(self, timestamps: list[datetime]) -> None:
        self._timestamps = timestamps
        self._index = 0

    def __call__(self) -> datetime:
        value = self._timestamps[min(self._index, len(self._timestamps) - 1)]
        self._index += 1
        return value


async def _no_op_sleeper(_seconds: float) -> None:
    return None


def _run(adapter, *, policy=None, clock=None, sleeper=None, random_source=None):
    return asyncio.run(
        run_invocation(
            adapter=adapter,
            request=_request(),
            prepared_request=adapter.prepare_request(_request()),
            policy=policy or _policy(),
            request_correlation_id="corr-runtime",
            clock=clock or (lambda: NOW),
            sleeper=sleeper or _no_op_sleeper,
            random_source=random_source or random.Random(1),
        )
    )


def test_first_attempt_success():
    adapter = FakeLLMProviderAdapter(outcomes=(FakeInvocationOutcome(succeeds=True),))
    result = _run(adapter)

    assert result.status is LLMInvocationStatus.SUCCEEDED
    assert len(result.attempts) == 1
    assert adapter.call_count == 1


def test_transient_failure_then_success():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    result = _run(adapter)

    assert result.status is LLMInvocationStatus.SUCCEEDED
    assert len(result.attempts) == 2
    assert result.attempts[0].status.value == "failed"
    assert result.attempts[1].status.value == "succeeded"
    assert adapter.call_count == 2


def test_maximum_attempts_reached_is_a_terminal_failure():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
        )
    )
    result = _run(adapter, policy=_policy(max_attempts=3))

    assert result.status is LLMInvocationStatus.FAILED
    assert result.envelope is None
    assert len(result.attempts) == 3
    assert adapter.call_count == 3
    assert result.terminal_error.category is LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE


def test_non_retryable_failure_stops_after_one_attempt():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
            ),
        )
    )
    result = _run(adapter, policy=_policy(max_attempts=5))

    assert result.status is LLMInvocationStatus.FAILED
    assert len(result.attempts) == 1
    assert adapter.call_count == 1
    assert result.terminal_error.category is LLMProviderErrorCategory.AUTHENTICATION_FAILURE


def test_provider_and_model_remain_unchanged_across_retries():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.RATE_LIMITED,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    result = _run(adapter)

    assert result.envelope.provider_id == "fake"
    assert result.envelope.configured_model_identifier == "fake-model"


def test_total_deadline_exhaustion_prevents_a_new_attempt():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
        )
    )
    # Clock calls, in order: start; loop-top check (attempt 1, not
    # exceeded); attempt_started; attempt_completed; remaining-deadline
    # check after the failure (still enough time to retry); loop-top
    # check for attempt 2 (now exceeded - the sleep "used up" the
    # remaining budget from this fake clock's point of view).
    timestamps = [
        NOW,  # start
        NOW,  # loop-top check, attempt 1 (not exceeded)
        NOW,  # attempt_started
        NOW + timedelta(seconds=1),  # attempt_completed
        NOW + timedelta(seconds=1),  # remaining_seconds() check after failure (9s left - retry allowed)
        NOW + timedelta(seconds=100),  # loop-top check, attempt 2 (deadline exceeded)
    ]
    clock = _FakeClock(timestamps)
    result = _run(
        adapter,
        policy=_policy(total_deadline_seconds=10, max_attempts=5),
        clock=clock,
    )

    assert result.status is LLMInvocationStatus.FAILED
    assert result.terminal_error.category is (
        LLMProviderErrorCategory.TOTAL_DEADLINE_EXCEEDED
    )
    assert len(result.attempts) == 1
    assert adapter.call_count == 1


def test_no_attempt_starts_once_deadline_already_exhausted():
    adapter = FakeLLMProviderAdapter(outcomes=(FakeInvocationOutcome(succeeds=True),))
    clock = _FakeClock([NOW, NOW + timedelta(seconds=1000)])
    result = _run(
        adapter, policy=_policy(total_deadline_seconds=10), clock=clock
    )

    assert result.status is LLMInvocationStatus.FAILED
    assert adapter.call_count == 0
    assert result.attempts == ()


def test_attempt_history_is_consistent_with_the_envelope():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    result = _run(adapter)

    assert result.envelope.attempt_count == 2
    assert result.envelope.attempts == result.attempts
    assert len(result.attempts) == 2


def test_one_provider_call_per_attempt():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    result = _run(adapter, policy=_policy(max_attempts=3))

    assert adapter.call_count == 3
    assert len(result.attempts) == 3


def test_cancellation_propagates_and_is_recorded():
    class _CancellingAdapter(FakeLLMProviderAdapter):
        async def invoke(self, request, prepared_request, invocation_context):
            raise asyncio.CancelledError()

    adapter = _CancellingAdapter()

    with pytest.raises(LLMInvocationCancelledError) as exc_info:
        _run(adapter)

    assert len(exc_info.value.attempts) == 1
    assert exc_info.value.attempts[0].status.value == "cancelled"


def test_no_retry_after_cancellation():
    call_count = 0

    class _CancellingThenSucceedingAdapter(FakeLLMProviderAdapter):
        async def invoke(self, request, prepared_request, invocation_context):
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

    adapter = _CancellingThenSucceedingAdapter()

    with pytest.raises(LLMInvocationCancelledError):
        _run(adapter, policy=_policy(max_attempts=5))

    assert call_count == 1


def test_bounded_delay_never_exceeds_configured_maximum():
    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    recorded_delays: list[float] = []

    async def _recording_sleeper(seconds: float) -> None:
        recorded_delays.append(seconds)

    _run(
        adapter,
        policy=_policy(
            max_attempts=5,
            base_delay_seconds=1.0,
            max_delay_seconds=1.5,
        ),
        sleeper=_recording_sleeper,
    )

    assert all(delay <= 1.5 for delay in recorded_delays)
    assert len(recorded_delays) == 2
