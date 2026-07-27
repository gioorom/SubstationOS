from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationStatus,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMUsage,
)
from app.domain.engineering_session.engineering_session_builder import (
    EngineeringSessionBuilder,
    append_engineering_response,
    build_initial_session,
    change_session_state,
    update_session_configuration,
)
from app.domain.engineering_session.engineering_session_exceptions import (
    InvalidProjectIdError,
    InvalidSessionIdError,
    InvalidSessionTransitionError,
    ProjectIdMismatchError,
    SessionNotMutableError,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionEventType,
    EngineeringSessionStatus,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.services import context_builder_service, engineering_response_service, prompt_builder_service

PROJECT_ID = 41
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _engineering_response(project_id: int = PROJECT_ID, now: datetime = NOW):
    collection = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_result = context_builder_service.build_context_package(
        project_id=project_id, candidates=collection, now=now
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=now
    )
    envelope = LLMResponseEnvelope(
        provider_id="fake",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="Answer.",
                provider_block_type=None,
                annotations=(),
            ),
        ),
        finish_reason=LLMFinishReason.COMPLETED,
        usage=LLMUsage(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        ),
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id="corr-1",
        provider_request_id=None,
        started_at=now,
        completed_at=now,
        latency_seconds=0.1,
        attempt_count=1,
        attempts=(),
        warnings=(),
        metadata=LLMResponseMetadata(
            runtime_version="1.0",
            adapter_version="1.0",
            request_preparation_policy_version="1.0",
            prompt_package_version=prompt_result.package.version.package_version,
            context_builder_version=prompt_result.package.metadata.context_builder_version,
            prompt_builder_version=prompt_result.package.version.prompt_builder_version,
        ),
    )
    return engineering_response_service.build_engineering_response(
        project_id=project_id,
        context_package=context_result.package,
        prompt_package=prompt_result.package,
        llm_response_envelope=envelope,
        now=now,
    ).response


def test_build_initial_session_produces_a_valid_created_session() -> None:
    result = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="A title"
    )

    assert result.validation.valid is True
    session = result.session
    assert session.state.status is EngineeringSessionStatus.CREATED
    assert session.engineering_responses == ()
    assert session.configuration.title == "A title"
    assert len(session.timeline.events) == 1
    assert session.timeline.events[0].event_type is (
        EngineeringSessionEventType.SESSION_CREATED
    )
    assert session.timeline.events[0].sequence == 0
    assert session.statistics.response_count == 0
    assert session.statistics.timeline_event_count == 1
    assert session.statistics.session_duration_seconds == 0.0


def test_build_initial_session_rejects_a_non_positive_project_id() -> None:
    with pytest.raises(InvalidProjectIdError):
        build_initial_session(project_id=0, session_id="s-1", now=NOW)


def test_build_initial_session_rejects_a_blank_session_id() -> None:
    with pytest.raises(InvalidSessionIdError):
        build_initial_session(project_id=PROJECT_ID, session_id="   ", now=NOW)


def test_identical_inputs_produce_an_identical_initial_session() -> None:
    first = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="A title"
    )
    second = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="A title"
    )

    assert first.session == second.session
    assert first.validation == second.validation


def test_append_engineering_response_updates_statistics_and_timeline() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    t1 = NOW + timedelta(minutes=1)
    response = _engineering_response(now=t1)

    result = append_engineering_response(session, response, now=t1)

    assert result.validation.valid is True
    updated = result.session
    assert updated.engineering_responses == (response,)
    assert updated.statistics.response_count == 1
    assert updated.statistics.timeline_event_count == 2
    assert updated.statistics.last_activity_at == t1
    assert updated.metadata.updated_at == t1
    last_event = updated.timeline.events[-1]
    assert last_event.event_type is (
        EngineeringSessionEventType.ENGINEERING_RESPONSE_ADDED
    )
    assert last_event.sequence == 1


def test_append_engineering_response_rejects_a_project_id_mismatch() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    other_response = _engineering_response(project_id=PROJECT_ID + 1)

    with pytest.raises(ProjectIdMismatchError):
        append_engineering_response(session, other_response, now=NOW)


def test_append_engineering_response_rejects_a_completed_session() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    t1 = NOW + timedelta(minutes=1)
    session = change_session_state(
        session, EngineeringSessionStatus.ACTIVE, now=t1
    ).session
    t2 = NOW + timedelta(minutes=2)
    session = change_session_state(
        session, EngineeringSessionStatus.COMPLETED, now=t2
    ).session

    with pytest.raises(SessionNotMutableError):
        append_engineering_response(
            session, _engineering_response(now=t2), now=t2
        )


@pytest.mark.parametrize(
    "current,target",
    [
        (EngineeringSessionStatus.CREATED, EngineeringSessionStatus.ACTIVE),
        (EngineeringSessionStatus.ACTIVE, EngineeringSessionStatus.PAUSED),
        (EngineeringSessionStatus.ACTIVE, EngineeringSessionStatus.COMPLETED),
        (EngineeringSessionStatus.PAUSED, EngineeringSessionStatus.ACTIVE),
        (EngineeringSessionStatus.PAUSED, EngineeringSessionStatus.COMPLETED),
        (EngineeringSessionStatus.PAUSED, EngineeringSessionStatus.ARCHIVED),
        (EngineeringSessionStatus.COMPLETED, EngineeringSessionStatus.ARCHIVED),
    ],
)
def test_valid_state_transitions_succeed(
    current: EngineeringSessionStatus, target: EngineeringSessionStatus
) -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    # Drive the session to `current` via the same builder operations a
    # real caller would use, rather than constructing an invalid
    # intermediate state directly.
    path: list[EngineeringSessionStatus] = []
    if current is not EngineeringSessionStatus.CREATED:
        path.append(EngineeringSessionStatus.ACTIVE)
    if current in (
        EngineeringSessionStatus.PAUSED,
        EngineeringSessionStatus.COMPLETED,
    ) and current is not EngineeringSessionStatus.ACTIVE:
        if current is EngineeringSessionStatus.PAUSED:
            path.append(EngineeringSessionStatus.PAUSED)
        elif current is EngineeringSessionStatus.COMPLETED:
            path.append(EngineeringSessionStatus.COMPLETED)

    now = NOW
    for status in path:
        now += timedelta(minutes=1)
        session = change_session_state(session, status, now=now).session

    assert session.state.status is current

    now += timedelta(minutes=1)
    result = change_session_state(session, target, now=now)
    assert result.validation.valid is True
    assert result.session.state.status is target
    assert result.session.state.changed_at == now


@pytest.mark.parametrize(
    "current,target",
    [
        (EngineeringSessionStatus.CREATED, EngineeringSessionStatus.PAUSED),
        (EngineeringSessionStatus.CREATED, EngineeringSessionStatus.COMPLETED),
        (EngineeringSessionStatus.CREATED, EngineeringSessionStatus.ARCHIVED),
        (EngineeringSessionStatus.ACTIVE, EngineeringSessionStatus.ARCHIVED),
        (EngineeringSessionStatus.COMPLETED, EngineeringSessionStatus.ACTIVE),
    ],
)
def test_invalid_state_transitions_are_rejected(
    current: EngineeringSessionStatus, target: EngineeringSessionStatus
) -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    now = NOW
    if current is not EngineeringSessionStatus.CREATED:
        now += timedelta(minutes=1)
        session = change_session_state(
            session, EngineeringSessionStatus.ACTIVE, now=now
        ).session
    if current is EngineeringSessionStatus.COMPLETED:
        now += timedelta(minutes=1)
        session = change_session_state(
            session, EngineeringSessionStatus.COMPLETED, now=now
        ).session

    with pytest.raises(InvalidSessionTransitionError):
        change_session_state(session, target, now=now + timedelta(minutes=1))


def test_archived_is_a_terminal_state() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    now = NOW
    for status in (
        EngineeringSessionStatus.ACTIVE,
        EngineeringSessionStatus.PAUSED,
        EngineeringSessionStatus.ARCHIVED,
    ):
        now += timedelta(minutes=1)
        session = change_session_state(session, status, now=now).session

    for target in EngineeringSessionStatus:
        with pytest.raises(InvalidSessionTransitionError):
            change_session_state(session, target, now=now + timedelta(minutes=1))


def test_update_session_configuration_preserves_untouched_fields() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="Original"
    ).session
    t1 = NOW + timedelta(minutes=1)

    result = update_session_configuration(session, now=t1, notes="New notes")

    assert result.validation.valid is True
    updated = result.session
    assert updated.configuration.title == "Original"
    assert updated.configuration.notes == "New notes"
    assert updated.timeline.events[-1].event_type is (
        EngineeringSessionEventType.CONFIGURATION_UPDATED
    )


def test_update_session_configuration_rejects_an_archived_session() -> None:
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW
    ).session
    now = NOW
    for status in (
        EngineeringSessionStatus.ACTIVE,
        EngineeringSessionStatus.COMPLETED,
        EngineeringSessionStatus.ARCHIVED,
    ):
        now += timedelta(minutes=1)
        session = change_session_state(session, status, now=now).session

    with pytest.raises(SessionNotMutableError):
        update_session_configuration(session, now=now, notes="won't land")


def test_the_builder_class_delegates_to_the_same_functions() -> None:
    via_class = EngineeringSessionBuilder.create(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="A title"
    )
    via_function = build_initial_session(
        project_id=PROJECT_ID, session_id="s-1", now=NOW, title="A title"
    )

    assert via_class.session == via_function.session
