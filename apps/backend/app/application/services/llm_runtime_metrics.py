"""
A lightweight, in-process metrics abstraction for the LLM Invocation
Runtime (EPIC 4, Milestone 17) - deliberately not a telemetry
framework, since none exists in this repository yet (Milestone 17's
own "avoid building a large telemetry framework" instruction). Counts
reset when the process restarts; nothing here is persisted or exported
to an external system. No high-cardinality label (project id, prompt
text, response text, correlation id) is ever recorded - only closed,
bounded categories and aggregate numbers.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from app.application.models.llm_invocation import (
    LLMInvocationResult,
    LLMInvocationStatus,
    LLMProviderErrorCategory,
)

_TIMEOUT_CATEGORIES = frozenset(
    {
        LLMProviderErrorCategory.CONNECTION_TIMEOUT,
        LLMProviderErrorCategory.READ_TIMEOUT,
        LLMProviderErrorCategory.TOTAL_DEADLINE_EXCEEDED,
    }
)


@dataclass(frozen=True, slots=True)
class LLMRuntimeMetricsSnapshot:
    total_invocations: int
    success_count: int
    failure_count: int
    cancellation_count: int
    retry_count: int
    timeout_count: int
    total_input_tokens: int
    total_output_tokens: int
    failure_counts_by_category: dict[str, int] = field(default_factory=dict)


class LLMRuntimeMetrics:
    """Thread-safe (a single lock around simple counters - this
    runtime's own call volume never justifies anything more elaborate)
    in-process counters, updated once per completed
    ``LLMInvocationResult``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0
        self._successes = 0
        self._failures = 0
        self._cancellations = 0
        self._retries = 0
        self._timeouts = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._failures_by_category: dict[str, int] = {}

    def record_result(self, result: LLMInvocationResult) -> None:
        with self._lock:
            self._total += 1
            self._retries += max(0, len(result.attempts) - 1)

            if result.status is LLMInvocationStatus.SUCCEEDED:
                self._successes += 1
                if result.envelope is not None:
                    usage = result.envelope.usage
                    self._input_tokens += usage.input_tokens or 0
                    self._output_tokens += usage.output_tokens or 0
            elif result.status is LLMInvocationStatus.CANCELLED:
                self._cancellations += 1
            else:
                self._failures += 1
                if result.terminal_error is not None:
                    category = result.terminal_error.category
                    key = category.value
                    self._failures_by_category[key] = (
                        self._failures_by_category.get(key, 0) + 1
                    )
                    if category in _TIMEOUT_CATEGORIES:
                        self._timeouts += 1

    def snapshot(self) -> LLMRuntimeMetricsSnapshot:
        with self._lock:
            return LLMRuntimeMetricsSnapshot(
                total_invocations=self._total,
                success_count=self._successes,
                failure_count=self._failures,
                cancellation_count=self._cancellations,
                retry_count=self._retries,
                timeout_count=self._timeouts,
                total_input_tokens=self._input_tokens,
                total_output_tokens=self._output_tokens,
                failure_counts_by_category=dict(self._failures_by_category),
            )


# A single, process-wide instance - reset only by process restart,
# never persisted. Acceptable for this milestone's "lightweight,
# in-process telemetry" scope; a real metrics platform is future work.
RUNTIME_METRICS = LLMRuntimeMetrics()
