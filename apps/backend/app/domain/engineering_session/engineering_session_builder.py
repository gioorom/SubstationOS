"""
Engineering Session Builder (Milestone 19's central pipeline stage).
Three deterministic operations, each returning a new
``EngineeringSessionBuilderResult`` (never mutating its input):

    build_initial_session          - creates a brand-new session
    append_engineering_response    - appends one EngineeringResponse
    change_session_state           - transitions session status
    update_session_configuration   - updates title/notes

Every operation appends exactly one new, immutable
``EngineeringSessionEvent`` to the timeline and recomputes statistics
and ``metadata.updated_at`` from the caller-supplied ``now`` - never
from the wall clock, never as a side effect on an existing object
(CLAUDE.md SS15, "Pure domain"). No AI usage, no I/O, no persistence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_exceptions import (
    InvalidSessionTransitionError,
    SessionNotMutableError,
)
from app.domain.engineering_session.engineering_session_input_validator import (
    EngineeringSessionInputValidator,
)
from app.domain.engineering_session.engineering_session_metadata import (
    build_metadata,
    build_version,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
    EngineeringSessionBuilderResult,
    EngineeringSessionConfiguration,
    EngineeringSessionEvent,
    EngineeringSessionEventType,
    EngineeringSessionId,
    EngineeringSessionPolicy,
    EngineeringSessionState,
    EngineeringSessionStatus,
    EngineeringSessionTimeline,
)
from app.domain.engineering_session.engineering_session_policy import (
    ENGINEERING_SESSION_VERSION,
    SESSION_POLICY_VERSION,
)
from app.domain.engineering_session.engineering_session_state_machine import (
    MUTABLE_STATUSES,
    is_transition_valid,
)
from app.domain.engineering_session.engineering_session_statistics import (
    build_statistics,
)
from app.domain.engineering_session.engineering_session_validation import (
    validate_session,
)


def _finalize(
    *,
    session_id: EngineeringSessionId,
    project_id: int,
    state: EngineeringSessionState,
    responses: tuple[EngineeringResponse, ...],
    configuration: EngineeringSessionConfiguration,
    events: tuple[EngineeringSessionEvent, ...],
    created_by: str | None,
    created_at: datetime,
    now: datetime,
) -> EngineeringSessionBuilderResult:
    metadata = build_metadata(
        configuration=configuration,
        project_id=project_id,
        created_by=created_by,
        created_at=created_at,
        updated_at=now,
    )
    version = build_version(configuration)
    statistics = build_statistics(
        responses=responses, events=events, created_at=created_at, now=now
    )

    session = EngineeringSession(
        session_id=session_id,
        project_id=project_id,
        state=state,
        engineering_responses=responses,
        configuration=configuration,
        timeline=EngineeringSessionTimeline(events=events),
        metadata=metadata,
        statistics=statistics,
        version=version,
    )

    validation = validate_session(session)

    return EngineeringSessionBuilderResult(
        project_id=project_id, session=session, validation=validation
    )


def build_initial_session(
    *,
    project_id: int,
    session_id: str,
    now: datetime,
    created_by: str | None = None,
    title: str | None = None,
    notes: str | None = None,
) -> EngineeringSessionBuilderResult:
    EngineeringSessionInputValidator.validate_project_id(project_id)
    EngineeringSessionInputValidator.validate_session_id(session_id)

    configuration = EngineeringSessionConfiguration(
        session_policy=EngineeringSessionPolicy(version=SESSION_POLICY_VERSION),
        engineering_session_version=ENGINEERING_SESSION_VERSION,
        title=title,
        notes=notes,
    )

    initial_state = EngineeringSessionState(
        status=EngineeringSessionStatus.CREATED, changed_at=now
    )

    created_event = EngineeringSessionEvent(
        event_type=EngineeringSessionEventType.SESSION_CREATED,
        sequence=0,
        occurred_at=now,
        description=f"Session created for project {project_id}.",
    )

    return _finalize(
        session_id=EngineeringSessionId(value=session_id),
        project_id=project_id,
        state=initial_state,
        responses=(),
        configuration=configuration,
        events=(created_event,),
        created_by=created_by,
        created_at=now,
        now=now,
    )


def append_engineering_response(
    session: EngineeringSession,
    response: EngineeringResponse,
    *,
    now: datetime,
) -> EngineeringSessionBuilderResult:
    if session.state.status not in MUTABLE_STATUSES:
        raise SessionNotMutableError(session.state.status)

    EngineeringSessionInputValidator.validate_response_belongs_to_project(
        session.project_id, response
    )

    responses = session.engineering_responses + (response,)
    events = session.timeline.events + (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.ENGINEERING_RESPONSE_ADDED,
            sequence=len(session.timeline.events),
            occurred_at=now,
            description=(
                f"EngineeringResponse #{len(responses)} added "
                f"(status={response.status.value})."
            ),
        ),
    )

    return _finalize(
        session_id=session.session_id,
        project_id=session.project_id,
        state=session.state,
        responses=responses,
        configuration=session.configuration,
        events=events,
        created_by=session.metadata.created_by,
        created_at=session.metadata.created_at,
        now=now,
    )


def change_session_state(
    session: EngineeringSession,
    target_status: EngineeringSessionStatus,
    *,
    now: datetime,
) -> EngineeringSessionBuilderResult:
    current_status = session.state.status
    if not is_transition_valid(current_status, target_status):
        raise InvalidSessionTransitionError(current_status, target_status)

    new_state = EngineeringSessionState(status=target_status, changed_at=now)
    events = session.timeline.events + (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.STATE_CHANGED,
            sequence=len(session.timeline.events),
            occurred_at=now,
            description=(
                f"State changed from '{current_status.value}' to "
                f"'{target_status.value}'."
            ),
        ),
    )

    return _finalize(
        session_id=session.session_id,
        project_id=session.project_id,
        state=new_state,
        responses=session.engineering_responses,
        configuration=session.configuration,
        events=events,
        created_by=session.metadata.created_by,
        created_at=session.metadata.created_at,
        now=now,
    )


def update_session_configuration(
    session: EngineeringSession,
    *,
    now: datetime,
    title: str | None = None,
    notes: str | None = None,
) -> EngineeringSessionBuilderResult:
    if session.state.status not in MUTABLE_STATUSES:
        raise SessionNotMutableError(session.state.status)

    configuration = replace(
        session.configuration,
        title=title if title is not None else session.configuration.title,
        notes=notes if notes is not None else session.configuration.notes,
    )
    events = session.timeline.events + (
        EngineeringSessionEvent(
            event_type=EngineeringSessionEventType.CONFIGURATION_UPDATED,
            sequence=len(session.timeline.events),
            occurred_at=now,
            description="Session configuration updated.",
        ),
    )

    return _finalize(
        session_id=session.session_id,
        project_id=session.project_id,
        state=session.state,
        responses=session.engineering_responses,
        configuration=configuration,
        events=events,
        created_by=session.metadata.created_by,
        created_at=session.metadata.created_at,
        now=now,
    )


class EngineeringSessionBuilder:
    """A thin, named façade over the module-level builder functions -
    kept only because this milestone explicitly names an
    ``EngineeringSessionBuilder`` class; every sibling bounded context
    (Prompt Builder's ``assemble_prompt_package``, Engineering
    Response's ``assemble_engineering_response``) exposes the same
    logic as plain functions instead."""

    @staticmethod
    def create(
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

    @staticmethod
    def append_response(
        session: EngineeringSession,
        response: EngineeringResponse,
        *,
        now: datetime,
    ) -> EngineeringSessionBuilderResult:
        return append_engineering_response(session, response, now=now)

    @staticmethod
    def change_state(
        session: EngineeringSession,
        target_status: EngineeringSessionStatus,
        *,
        now: datetime,
    ) -> EngineeringSessionBuilderResult:
        return change_session_state(session, target_status, now=now)

    @staticmethod
    def update_configuration(
        session: EngineeringSession,
        *,
        now: datetime,
        title: str | None = None,
        notes: str | None = None,
    ) -> EngineeringSessionBuilderResult:
        return update_session_configuration(
            session, now=now, title=title, notes=notes
        )
