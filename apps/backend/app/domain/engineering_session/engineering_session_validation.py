"""
Validation for Engineering Session (Milestone 19). Proves, after each
builder operation, that an ``EngineeringSession`` satisfies every
structural invariant this milestone requires: the timeline starts with
``SESSION_CREATED`` at sequence zero and is strictly ordered, every
``EngineeringResponse`` belongs to the session's own project, metadata
is complete, and every statistic/version field is internally
consistent. Never causes building to raise - Engineering Session
always produces a structurally valid session by construction; this is
an inspectable, testable proof of that, not a gate a caller must pass.
O(n) in the number of timeline events and responses (both small,
bounded collections for a single work session).
"""

from __future__ import annotations

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
    EngineeringSessionEventType,
    EngineeringSessionValidationResult,
)


def validate_session(
    session: EngineeringSession,
) -> EngineeringSessionValidationResult:
    errors: list[str] = []

    if not session.session_id.value or not session.session_id.value.strip():
        errors.append("session_id is blank.")

    if session.project_id <= 0:
        errors.append("project_id is not positive.")

    events = session.timeline.events
    if not events:
        errors.append("Timeline must contain at least one event.")
    else:
        if events[0].event_type is not EngineeringSessionEventType.SESSION_CREATED:
            errors.append("Timeline does not begin with SESSION_CREATED.")

        expected_sequence = 0
        previous_occurred_at = None
        for event in events:
            if event.sequence != expected_sequence:
                errors.append(
                    "Timeline events are not sequenced contiguously "
                    "from zero."
                )
                break
            expected_sequence += 1

            if previous_occurred_at is not None and event.occurred_at < previous_occurred_at:
                errors.append("Timeline events are not chronologically ordered.")
                break
            previous_occurred_at = event.occurred_at

        state_changed_events = [
            event
            for event in events
            if event.event_type is EngineeringSessionEventType.STATE_CHANGED
        ]
        if state_changed_events and (
            state_changed_events[-1].occurred_at != session.state.changed_at
        ):
            errors.append(
                "Current state's changed_at is inconsistent with the "
                "most recent STATE_CHANGED timeline event."
            )

    for response in session.engineering_responses:
        if response.project_id != session.project_id:
            errors.append(
                "An owned EngineeringResponse belongs to a different "
                "project than the session itself."
            )
            break

    metadata = session.metadata
    if (
        not metadata.engineering_session_version
        or not metadata.session_policy_version
        or not metadata.package_version
        or metadata.project_id <= 0
        or metadata.created_at is None
        or metadata.updated_at is None
        or metadata.updated_at < metadata.created_at
    ):
        errors.append("Metadata is incomplete or inconsistent.")

    version = session.version
    if (
        not version.engineering_session_version
        or not version.session_policy_version
        or not version.package_version
    ):
        errors.append("Version fields are incomplete.")
    elif (
        version.engineering_session_version
        != metadata.engineering_session_version
        or version.session_policy_version != metadata.session_policy_version
        or version.package_version != metadata.package_version
    ):
        errors.append("Version fields are inconsistent with metadata.")

    statistics = session.statistics
    if statistics.response_count != len(session.engineering_responses):
        errors.append(
            "Statistics response_count is inconsistent with the "
            "owned engineering responses."
        )
    if statistics.timeline_event_count != len(events):
        errors.append(
            "Statistics timeline_event_count is inconsistent with the "
            "assembled timeline."
        )
    if statistics.last_activity_at != metadata.updated_at:
        errors.append(
            "Statistics last_activity_at is inconsistent with "
            "metadata.updated_at."
        )
    expected_duration = (
        metadata.updated_at - metadata.created_at
    ).total_seconds()
    if statistics.session_duration_seconds != expected_duration:
        errors.append(
            "Statistics session_duration_seconds is inconsistent with "
            "metadata's created_at/updated_at."
        )

    return EngineeringSessionValidationResult(
        valid=not errors, errors=tuple(errors)
    )


class EngineeringSessionValidator:
    """A thin, named façade over ``validate_session`` - kept only
    because this milestone explicitly names an
    ``EngineeringSessionValidator`` class; every sibling bounded context
    exposes the same logic as a plain function instead."""

    @staticmethod
    def validate(
        session: EngineeringSession,
    ) -> EngineeringSessionValidationResult:
        return validate_session(session)
