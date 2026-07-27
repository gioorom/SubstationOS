from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.engineering_session.engineering_session_exceptions import (
    InvalidSessionTransitionError,
    SessionNotMutableError,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionStatus,
)
from app.services import engineering_session_service

PROJECT_ID = 51
NOW = datetime(2026, 1, 1, 11, 0, 0)


def test_create_session_returns_a_valid_created_session() -> None:
    result = engineering_session_service.create_session(
        project_id=PROJECT_ID, session_id="svc-1", now=NOW, title="Review"
    )

    assert result.project_id == PROJECT_ID
    assert result.session.state.status is EngineeringSessionStatus.CREATED
    assert result.validation.valid is True


def test_change_state_transitions_and_records_timeline() -> None:
    session = engineering_session_service.create_session(
        project_id=PROJECT_ID, session_id="svc-2", now=NOW
    ).session
    t1 = NOW + timedelta(minutes=1)

    result = engineering_session_service.change_state(
        session=session, target_status=EngineeringSessionStatus.ACTIVE, now=t1
    )

    assert result.session.state.status is EngineeringSessionStatus.ACTIVE
    assert len(result.session.timeline.events) == 2


def test_change_state_rejects_an_invalid_transition() -> None:
    session = engineering_session_service.create_session(
        project_id=PROJECT_ID, session_id="svc-3", now=NOW
    ).session

    with pytest.raises(InvalidSessionTransitionError):
        engineering_session_service.change_state(
            session=session,
            target_status=EngineeringSessionStatus.COMPLETED,
            now=NOW,
        )


def test_update_configuration_rejects_a_completed_session() -> None:
    session = engineering_session_service.create_session(
        project_id=PROJECT_ID, session_id="svc-4", now=NOW
    ).session
    t1 = NOW + timedelta(minutes=1)
    session = engineering_session_service.change_state(
        session=session, target_status=EngineeringSessionStatus.ACTIVE, now=t1
    ).session
    t2 = NOW + timedelta(minutes=2)
    session = engineering_session_service.change_state(
        session=session,
        target_status=EngineeringSessionStatus.COMPLETED,
        now=t2,
    ).session

    with pytest.raises(SessionNotMutableError):
        engineering_session_service.update_configuration(
            session=session, now=t2, notes="too late"
        )
