"""
The LLM Invocation Runtime (EPIC 4, Milestone 17). Owns the invocation
lifecycle: attempt sequencing, the total-deadline check, retry
decisions (delegated to ``llm_retry_policy.py``, never decided here),
cancellation propagation, and assembling the final, complete attempt
history onto the returned envelope. Never owns retrieval, context
selection, prompt composition, or any engineering interpretation of a
response - this module is a pure, provider-agnostic orchestration loop
around one ``LLMProviderPort.invoke`` call per attempt.

``clock``, ``sleeper``, and ``random_source`` are always supplied by
the caller - never read from the wall clock, ``asyncio.sleep``, or the
global ``random`` module directly inside this function - so the entire
attempt/retry/deadline loop is deterministic and testable without any
real delay or real randomness.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime

from app.application.models.llm_exceptions import (
    LLMInvocationCancelledError,
    ProviderInvocationFailedError,
)
from app.application.models.llm_invocation import (
    LLMInvocationAttempt,
    LLMInvocationAttemptStatus,
    LLMInvocationContext,
    LLMInvocationPolicy,
    LLMInvocationResult,
    LLMInvocationStatus,
    LLMProviderError,
    LLMProviderErrorCategory,
    LLMProviderErrorDetails,
    LLMTimeoutPhase,
)
from app.application.models.llm_request import LLMRequest, PreparedProviderRequest
from app.application.policies.llm_retry_policy import LLMRetryDecisionMaker
from app.application.policies.llm_timeout_policy import (
    compute_deadline,
    is_deadline_exceeded,
    remaining_seconds,
)
from app.application.ports.llm_provider_port import LLMProviderPort
from app.application.validation.llm_response_validator import validate_envelope

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


def _no_response_error() -> LLMProviderError:
    return LLMProviderError(
        category=LLMProviderErrorCategory.TOTAL_DEADLINE_EXCEEDED,
        message=(
            "The total invocation deadline was exhausted before this "
            "attempt could start."
        ),
        details=LLMProviderErrorDetails(
            http_status=None,
            provider_error_type=None,
            provider_request_id=None,
            retry_after_seconds=None,
            timeout_phase=LLMTimeoutPhase.TOTAL_DEADLINE,
        ),
    )


def _cancellation_error() -> LLMProviderError:
    return LLMProviderError(
        category=LLMProviderErrorCategory.CANCELLED,
        message="The invocation was cancelled.",
        details=LLMProviderErrorDetails(
            http_status=None,
            provider_error_type=None,
            provider_request_id=None,
            retry_after_seconds=None,
            timeout_phase=None,
        ),
    )


async def run_invocation(
    *,
    adapter: LLMProviderPort,
    request: LLMRequest,
    prepared_request: PreparedProviderRequest,
    policy: LLMInvocationPolicy,
    request_correlation_id: str,
    clock: Clock,
    sleeper: Sleeper,
    random_source: random.Random,
) -> LLMInvocationResult:
    provider_id = request.provider_selection.provider_id
    start = clock()
    deadline_at = compute_deadline(start, policy.timeout_policy)
    attempts: list[LLMInvocationAttempt] = []
    attempt_number = 0

    logger.info(
        "llm invocation started provider=%s model=%s correlation_id=%s",
        provider_id,
        request.model_selection.model_identifier,
        request_correlation_id,
    )

    while True:
        attempt_number += 1
        now = clock()

        if is_deadline_exceeded(deadline_at, now):
            logger.warning(
                "llm invocation terminal category=total_deadline_exceeded "
                "correlation_id=%s attempts=%d",
                request_correlation_id,
                len(attempts),
            )
            return LLMInvocationResult(
                status=LLMInvocationStatus.FAILED,
                envelope=None,
                terminal_error=_no_response_error(),
                attempts=tuple(attempts),
                request_correlation_id=request_correlation_id,
                validation=None,
            )

        invocation_context = LLMInvocationContext(
            request_correlation_id=request_correlation_id,
            attempt_number=attempt_number,
            deadline_at=deadline_at,
            policy=policy,
        )

        attempt_started = clock()
        logger.info(
            "llm invocation attempt started correlation_id=%s attempt=%d",
            request_correlation_id,
            attempt_number,
        )

        try:
            envelope = await adapter.invoke(
                request, prepared_request, invocation_context
            )
        except asyncio.CancelledError:
            attempt_completed = clock()
            attempts.append(
                LLMInvocationAttempt(
                    attempt_number=attempt_number,
                    status=LLMInvocationAttemptStatus.CANCELLED,
                    started_at=attempt_started,
                    completed_at=attempt_completed,
                    latency_seconds=(
                        attempt_completed - attempt_started
                    ).total_seconds(),
                    error=_cancellation_error(),
                )
            )
            logger.info(
                "llm invocation cancelled correlation_id=%s attempt=%d",
                request_correlation_id,
                attempt_number,
            )
            raise LLMInvocationCancelledError(tuple(attempts)) from None
        except ProviderInvocationFailedError as exc:
            attempt_completed = clock()
            provider_error = exc.provider_error
            attempts.append(
                LLMInvocationAttempt(
                    attempt_number=attempt_number,
                    status=LLMInvocationAttemptStatus.FAILED,
                    started_at=attempt_started,
                    completed_at=attempt_completed,
                    latency_seconds=(
                        attempt_completed - attempt_started
                    ).total_seconds(),
                    error=provider_error,
                )
            )
            logger.warning(
                "llm invocation attempt failed correlation_id=%s attempt=%d "
                "category=%s",
                request_correlation_id,
                attempt_number,
                provider_error.category.value,
            )

            remaining_after = remaining_seconds(deadline_at, clock())
            decision = LLMRetryDecisionMaker.decide(
                error_category=provider_error.category,
                attempt_number=attempt_number,
                policy=policy.retry_policy,
                retry_after_seconds=provider_error.details.retry_after_seconds,
                remaining_deadline_seconds=remaining_after,
                random_source=random_source,
            )

            if not decision.should_retry:
                logger.warning(
                    "llm invocation terminal correlation_id=%s attempts=%d "
                    "reason=%s",
                    request_correlation_id,
                    len(attempts),
                    decision.reason,
                )
                return LLMInvocationResult(
                    status=LLMInvocationStatus.FAILED,
                    envelope=None,
                    terminal_error=provider_error,
                    attempts=tuple(attempts),
                    request_correlation_id=request_correlation_id,
                    validation=None,
                )

            logger.info(
                "llm invocation retry scheduled correlation_id=%s attempt=%d "
                "delay_seconds=%.3f",
                request_correlation_id,
                attempt_number,
                decision.delay_seconds,
            )
            await sleeper(decision.delay_seconds)
            continue
        else:
            attempt_completed = clock()
            attempts.append(
                LLMInvocationAttempt(
                    attempt_number=attempt_number,
                    status=LLMInvocationAttemptStatus.SUCCEEDED,
                    started_at=attempt_started,
                    completed_at=attempt_completed,
                    latency_seconds=(
                        attempt_completed - attempt_started
                    ).total_seconds(),
                    error=None,
                )
            )

            final_completed = clock()
            final_envelope = replace(
                envelope,
                started_at=start,
                completed_at=final_completed,
                latency_seconds=(final_completed - start).total_seconds(),
                attempts=tuple(attempts),
                attempt_count=len(attempts),
            )
            validation = validate_envelope(
                final_envelope,
                configured_model_identifier=request.model_selection.model_identifier,
            )

            logger.info(
                "llm invocation completed correlation_id=%s attempts=%d "
                "latency_seconds=%.3f",
                request_correlation_id,
                len(attempts),
                final_envelope.latency_seconds,
            )
            return LLMInvocationResult(
                status=LLMInvocationStatus.SUCCEEDED,
                envelope=final_envelope,
                terminal_error=None,
                attempts=tuple(attempts),
                request_correlation_id=request_correlation_id,
                validation=validation,
            )
