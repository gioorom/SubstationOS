from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.application.models.llm_exceptions import ProviderInvocationFailedError
from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationContext,
    LLMInvocationPolicy,
    LLMProviderErrorCategory,
    LLMResponseContentType,
    LLMRetryPolicy,
    LLMTimeoutPolicy,
)
from app.application.ports.llm_provider_port import LLMProviderPort
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
    FakeLLMProviderAdapter,
)

NOW = datetime(2026, 1, 1, 4, 0, 0)


def _context(attempt_number: int = 1) -> LLMInvocationContext:
    return LLMInvocationContext(
        request_correlation_id="corr-fake",
        attempt_number=attempt_number,
        deadline_at=NOW,
        policy=LLMInvocationPolicy(
            retry_policy=LLMRetryPolicy(
                version="1.0",
                max_attempts=3,
                base_delay_seconds=0.001,
                max_delay_seconds=0.01,
                jitter_enabled=False,
            ),
            timeout_policy=LLMTimeoutPolicy(
                connect_timeout_seconds=1.0,
                read_timeout_seconds=1.0,
                total_deadline_seconds=5.0,
            ),
            runtime_version="1.0",
        ),
    )


def test_fake_adapter_satisfies_the_invocation_port_contract():
    assert isinstance(FakeLLMProviderAdapter(), LLMProviderPort)


def test_deterministic_success_scenario():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True, text="Deterministic."),)
    )
    envelope = asyncio.run(
        adapter.invoke(build_request(), adapter.prepare_request(build_request()), _context())
    )
    assert envelope.content[0].text == "Deterministic."
    assert envelope.finish_reason is LLMFinishReason.COMPLETED


def test_scripted_transient_failure_then_success():
    outcomes = (
        FakeInvocationOutcome(
            succeeds=False, error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE
        ),
        FakeInvocationOutcome(succeeds=True),
    )
    adapter = FakeLLMProviderAdapter(outcomes=outcomes)

    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    request = build_request()
    prepared = adapter.prepare_request(request)

    with pytest.raises(ProviderInvocationFailedError):
        asyncio.run(adapter.invoke(request, prepared, _context(1)))

    envelope = asyncio.run(adapter.invoke(request, prepared, _context(2)))
    assert envelope.finish_reason is LLMFinishReason.COMPLETED


def test_scripted_permanent_failure():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
            ),
        )
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    with pytest.raises(ProviderInvocationFailedError) as exc_info:
        asyncio.run(adapter.invoke(request, prepared, _context()))

    assert (
        exc_info.value.provider_error.category
        is LLMProviderErrorCategory.AUTHENTICATION_FAILURE
    )


def test_rate_limit_scenario_carries_retry_after():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.RATE_LIMITED,
                retry_after_seconds=2.5,
            ),
        )
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    with pytest.raises(ProviderInvocationFailedError) as exc_info:
        asyncio.run(adapter.invoke(request, prepared, _context()))

    assert exc_info.value.provider_error.details.retry_after_seconds == 2.5


def test_delayed_response_is_a_genuine_cancellable_await_point():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    sleep_calls: list[float] = []

    async def _recording_sleeper(seconds: float) -> None:
        sleep_calls.append(seconds)

    adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True, delay_seconds=0.01),),
        sleeper=_recording_sleeper,
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    asyncio.run(adapter.invoke(request, prepared, _context()))
    assert sleep_calls == [0.01]


def test_cancellation_during_delay_propagates():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    async def _cancelling_sleeper(_seconds: float) -> None:
        raise asyncio.CancelledError()

    adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True, delay_seconds=1.0),),
        sleeper=_cancelling_sleeper,
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(adapter.invoke(request, prepared, _context()))


def test_unsupported_response_content_scenario():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=True,
                content_type=LLMResponseContentType.UNSUPPORTED,
                provider_block_type="tool_use",
            ),
        )
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    envelope = asyncio.run(adapter.invoke(request, prepared, _context()))
    assert envelope.content[0].content_type is LLMResponseContentType.UNSUPPORTED
    assert envelope.content[0].text == ""
    assert len(envelope.warnings) == 1


def test_deterministic_usage_scenario():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True, input_tokens=99, output_tokens=11),)
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    envelope = asyncio.run(adapter.invoke(request, prepared, _context()))
    assert envelope.usage.input_tokens == 99
    assert envelope.usage.output_tokens == 11
    assert envelope.usage.total_tokens == 110


def test_deterministic_provider_request_id_scenario():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True, provider_request_id="fake-req-42"),)
    )
    request = build_request()
    prepared = adapter.prepare_request(request)

    envelope = asyncio.run(adapter.invoke(request, prepared, _context()))
    assert envelope.provider_request_id == "fake-req-42"


def test_more_attempts_than_scripted_outcomes_repeats_the_last_one():
    from tests.infrastructure.test_fake_llm_provider_adapter import (
        _request as build_request,
    )

    adapter = FakeLLMProviderAdapter(outcomes=(FakeInvocationOutcome(succeeds=True, text="only one"),))
    request = build_request()
    prepared = adapter.prepare_request(request)

    envelope = asyncio.run(adapter.invoke(request, prepared, _context(5)))
    assert envelope.content[0].text == "only one"
