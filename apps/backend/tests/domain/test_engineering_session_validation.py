from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
    EngineeringSessionConfiguration,
    EngineeringSessionEvent,
    EngineeringSessionEventType,
    EngineeringSessionId,
    EngineeringSessionMetadata,
    EngineeringSessionPolicy,
    EngineeringSessionState,
    EngineeringSessionStatistics,
    EngineeringSessionStatus,
    EngineeringSessionTimeline,
    EngineeringSessionVersion,
)
from app.domain.engineering_session.engineering_session_validation import (
    EngineeringSessionValidator,
    validate_session,
)

NOW = datetime(2026, 1, 1, 10, 0, 0)


def _timeline(*event_types: EngineeringSessionEventType) -> EngineeringSessionTimeline:
    events = tuple(
        EngineeringSessionEvent(
            event_type=event_type,
            sequence=index,
            occurred_at=NOW + timedelta(minutes=index),
            description="event",
        )
        for index, event_type in enumerate(event_types)
    )
    return EngineeringSessionTimeline(events=events)


def _session(**overrides) -> EngineeringSession:
    timeline = overrides.pop(
        "timeline", _timeline(EngineeringSessionEventType.SESSION_CREATED)
    )
    updated_at = overrides.pop("updated_at", NOW)

    defaults = dict(
        session_id=EngineeringSessionId(value="s-1"),
        project_id=1,
        state=EngineeringSessionState(
            status=EngineeringSessionStatus.CREATED, changed_at=NOW
        ),
        engineering_responses=(),
        configuration=EngineeringSessionConfiguration(
            session_policy=EngineeringSessionPolicy(version="1.0"),
            engineering_session_version="1.0",
            title=None,
            notes=None,
        ),
        timeline=timeline,
        metadata=EngineeringSessionMetadata(
            engineering_session_version="1.0",
            session_policy_version="1.0",
            project_id=1,
            created_by=None,
            created_at=NOW,
            updated_at=updated_at,
            package_version="1.0",
        ),
        statistics=EngineeringSessionStatistics(
            response_count=0,
            timeline_event_count=len(timeline.events),
            session_duration_seconds=(updated_at - NOW).total_seconds(),
            last_activity_at=updated_at,
        ),
        version=EngineeringSessionVersion(
            engineering_session_version="1.0",
            session_policy_version="1.0",
            package_version="1.0",
        ),
    )
    defaults.update(overrides)
    return EngineeringSession(**defaults)


def test_a_well_formed_session_is_valid() -> None:
    result = validate_session(_session())

    assert result.valid is True
    assert result.errors == ()


def test_the_validator_class_delegates_to_the_same_function() -> None:
    session = _session()

    assert EngineeringSessionValidator.validate(session) == validate_session(
        session
    )


def test_a_blank_session_id_is_rejected() -> None:
    session = replace(_session(), session_id=EngineeringSessionId(value=""))

    result = validate_session(session)

    assert result.valid is False
    assert any("session_id is blank" in error for error in result.errors)


def test_a_non_positive_project_id_is_rejected() -> None:
    session = replace(_session(), project_id=0)

    result = validate_session(session)

    assert result.valid is False
    assert any("project_id is not positive" in error for error in result.errors)


def test_a_timeline_not_starting_with_session_created_is_rejected() -> None:
    timeline = _timeline(EngineeringSessionEventType.STATE_CHANGED)
    session = _session(
        timeline=timeline,
        statistics=EngineeringSessionStatistics(
            response_count=0,
            timeline_event_count=1,
            session_duration_seconds=0.0,
            last_activity_at=NOW,
        ),
    )

    result = validate_session(session)

    assert result.valid is False
    assert any("SESSION_CREATED" in error for error in result.errors)


def test_out_of_sequence_timeline_events_are_rejected() -> None:
    events = (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.SESSION_CREATED,
            sequence=0,
            occurred_at=NOW,
            description="created",
        ),
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.STATE_CHANGED,
            sequence=5,
            occurred_at=NOW + timedelta(minutes=1),
            description="broken sequence",
        ),
    )
    session = _session(
        timeline=EngineeringSessionTimeline(events=events),
        statistics=EngineeringSessionStatistics(
            response_count=0,
            timeline_event_count=2,
            session_duration_seconds=60.0,
            last_activity_at=NOW + timedelta(minutes=1),
        ),
        updated_at=NOW + timedelta(minutes=1),
    )

    result = validate_session(session)

    assert result.valid is False
    assert any("sequenced contiguously" in error for error in result.errors)


def test_out_of_order_timestamps_are_rejected() -> None:
    events = (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.SESSION_CREATED,
            sequence=0,
            occurred_at=NOW,
            description="created",
        ),
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.STATE_CHANGED,
            sequence=1,
            occurred_at=NOW - timedelta(minutes=5),
            description="time travel",
        ),
    )
    session = _session(
        timeline=EngineeringSessionTimeline(events=events),
        statistics=EngineeringSessionStatistics(
            response_count=0,
            timeline_event_count=2,
            session_duration_seconds=0.0,
            last_activity_at=NOW,
        ),
    )

    result = validate_session(session)

    assert result.valid is False
    assert any("chronologically ordered" in error for error in result.errors)


def test_state_changed_at_inconsistent_with_timeline_is_rejected() -> None:
    events = (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.SESSION_CREATED,
            sequence=0,
            occurred_at=NOW,
            description="created",
        ),
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.STATE_CHANGED,
            sequence=1,
            occurred_at=NOW + timedelta(minutes=1),
            description="state changed",
        ),
    )
    session = _session(
        timeline=EngineeringSessionTimeline(events=events),
        state=EngineeringSessionState(
            status=EngineeringSessionStatus.ACTIVE,
            changed_at=NOW + timedelta(minutes=99),
        ),
        statistics=EngineeringSessionStatistics(
            response_count=0,
            timeline_event_count=2,
            session_duration_seconds=60.0,
            last_activity_at=NOW + timedelta(minutes=1),
        ),
        updated_at=NOW + timedelta(minutes=1),
    )

    result = validate_session(session)

    assert result.valid is False
    assert any("STATE_CHANGED" in error for error in result.errors)


def test_incomplete_metadata_is_rejected() -> None:
    session = _session()
    broken_metadata = replace(session.metadata, engineering_session_version="")
    broken = replace(session, metadata=broken_metadata)

    result = validate_session(broken)

    assert result.valid is False
    assert any("Metadata is incomplete" in error for error in result.errors)


def test_version_inconsistent_with_metadata_is_rejected() -> None:
    session = _session()
    broken_version = replace(session.version, engineering_session_version="9.9")
    broken = replace(session, version=broken_version)

    result = validate_session(broken)

    assert result.valid is False
    assert any("inconsistent with metadata" in error for error in result.errors)


def test_response_count_inconsistency_is_rejected() -> None:
    session = _session()
    broken_statistics = replace(session.statistics, response_count=5)
    broken = replace(session, statistics=broken_statistics)

    result = validate_session(broken)

    assert result.valid is False
    assert any("response_count" in error for error in result.errors)


def test_timeline_event_count_inconsistency_is_rejected() -> None:
    session = _session()
    broken_statistics = replace(session.statistics, timeline_event_count=99)
    broken = replace(session, statistics=broken_statistics)

    result = validate_session(broken)

    assert result.valid is False
    assert any("timeline_event_count" in error for error in result.errors)


def test_last_activity_at_inconsistency_is_rejected() -> None:
    session = _session()
    broken_statistics = replace(
        session.statistics, last_activity_at=NOW + timedelta(days=1)
    )
    broken = replace(session, statistics=broken_statistics)

    result = validate_session(broken)

    assert result.valid is False
    assert any("last_activity_at" in error for error in result.errors)


def test_session_duration_inconsistency_is_rejected() -> None:
    session = _session()
    broken_statistics = replace(
        session.statistics, session_duration_seconds=12345.0
    )
    broken = replace(session, statistics=broken_statistics)

    result = validate_session(broken)

    assert result.valid is False
    assert any("session_duration_seconds" in error for error in result.errors)
