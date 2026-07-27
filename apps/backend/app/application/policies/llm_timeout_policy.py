"""
Small, pure helpers around ``LLMTimeoutPolicy`` (EPIC 4, Milestone 17).
The total deadline is a single absolute wall-clock instant, computed
once by the runtime at the very start of an invocation, covering every
attempt and every retry delay - never recomputed per attempt, and
never allowed to let a new attempt start once it has passed.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.application.models.llm_invocation import LLMTimeoutPolicy


def compute_deadline(start: datetime, policy: LLMTimeoutPolicy) -> datetime:
    return start + timedelta(seconds=policy.total_deadline_seconds)


def remaining_seconds(deadline_at: datetime, now: datetime) -> float:
    return (deadline_at - now).total_seconds()


def is_deadline_exceeded(deadline_at: datetime, now: datetime) -> bool:
    return now >= deadline_at
