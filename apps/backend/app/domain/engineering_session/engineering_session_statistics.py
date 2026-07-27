"""
Statistics for Engineering Session (Milestone 19). Summarizes the
already-assembled responses and timeline into one
``EngineeringSessionStatistics`` value object - never a recomputation
of anything an earlier operation already decided. O(1) given the
already-materialized response/event counts and the caller-supplied
``created_at``/``now``. Deliberately no token accounting - that remains
Prompt Builder's own approximate, provider-independent responsibility
upstream.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionEvent,
    EngineeringSessionStatistics,
)


def build_statistics(
    *,
    responses: tuple[EngineeringResponse, ...],
    events: tuple[EngineeringSessionEvent, ...],
    created_at: datetime,
    now: datetime,
) -> EngineeringSessionStatistics:
    return EngineeringSessionStatistics(
        response_count=len(responses),
        timeline_event_count=len(events),
        session_duration_seconds=(now - created_at).total_seconds(),
        last_activity_at=now,
    )
