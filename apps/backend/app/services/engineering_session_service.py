"""
Application service for Engineering Session (EPIC 5, Milestone 19).
Thin orchestration over the pure domain builder
(``engineering_session_builder.py``) - unlike
``engineering_response_service.py``, this service needs no
application-layer translation seam, because Engineering Session's
input (an already-built ``EngineeringResponse``) is already a domain
type. Performs no persistence and no I/O of any kind.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_builder import (
    append_engineering_response,
    build_initial_session,
    change_session_state,
    update_session_configuration,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
    EngineeringSessionBuilderResult,
    EngineeringSessionStatus,
)


def create_session(
    *,
    project_id: int,
    session_id: str,
    now: datetime,
    created_by: str | None = None,
    title: str | None = None,
    notes: str | None = None,
) -> EngineeringSessionBuilderResult:
    return build_initial_session(
        project_id=project_id,
        session_id=session_id,
        now=now,
        created_by=created_by,
        title=title,
        notes=notes,
    )


def append_response(
    *,
    session: EngineeringSession,
    response: EngineeringResponse,
    now: datetime,
) -> EngineeringSessionBuilderResult:
    return append_engineering_response(session, response, now=now)


def change_state(
    *,
    session: EngineeringSession,
    target_status: EngineeringSessionStatus,
    now: datetime,
) -> EngineeringSessionBuilderResult:
    return change_session_state(session, target_status, now=now)


def update_configuration(
    *,
    session: EngineeringSession,
    now: datetime,
    title: str | None = None,
    notes: str | None = None,
) -> EngineeringSessionBuilderResult:
    return update_session_configuration(
        session, now=now, title=title, notes=notes
    )
