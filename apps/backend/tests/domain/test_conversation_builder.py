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
from app.domain.conversation.conversation_builder import (
    ConversationBuilder,
    append_message,
    attach_engineering_response,
    change_conversation_status,
    complete_turn,
    create_conversation,
    start_turn,
)
from app.domain.conversation.conversation_exceptions import (
    ConversationNotMutableError,
    InvalidConversationIdError,
    InvalidConversationTransitionError,
    InvalidProjectIdError,
    NoActiveTurnError,
    ProjectIdMismatchError,
    TurnAlreadyInProgressError,
)
from app.domain.conversation.conversation_models import (
    ConversationEventType,
    ConversationMessageRole,
    ConversationStatus,
    ConversationTurnStatus,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.services import context_builder_service, engineering_response_service, prompt_builder_service

PROJECT_ID = 61
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


def test_create_conversation_produces_a_valid_active_conversation() -> None:
    result = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    )

    assert result.validation.valid is True
    conversation = result.conversation
    assert conversation.status is ConversationStatus.ACTIVE
    assert conversation.turns == ()
    assert conversation.session_id.value == "sess-1"
    assert len(conversation.timeline.events) == 1
    assert conversation.timeline.events[0].event_type is (
        ConversationEventType.CONVERSATION_CREATED
    )
    assert conversation.statistics.turn_count == 0


def test_create_conversation_rejects_a_non_positive_project_id() -> None:
    with pytest.raises(InvalidProjectIdError):
        create_conversation(
            project_id=0, session_id="sess-1", conversation_id="conv-1", now=NOW
        )


def test_create_conversation_rejects_a_blank_conversation_id() -> None:
    with pytest.raises(InvalidConversationIdError):
        create_conversation(
            project_id=PROJECT_ID, session_id="sess-1", conversation_id="  ", now=NOW
        )


def test_identical_inputs_produce_an_identical_conversation() -> None:
    first = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    )
    second = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    )

    assert first.conversation == second.conversation


def test_start_turn_appends_a_started_turn() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)

    result = start_turn(conversation, "turn-1", now=t1)

    assert result.validation.valid is True
    turn = result.conversation.turns[0]
    assert turn.status is ConversationTurnStatus.STARTED
    assert turn.sequence == 0
    assert result.conversation.statistics.turn_count == 1


def test_start_turn_rejects_a_second_open_turn() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation

    with pytest.raises(TurnAlreadyInProgressError):
        start_turn(conversation, "turn-2", now=t1)


def test_start_turn_rejects_a_non_active_conversation() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = change_conversation_status(
        conversation, ConversationStatus.COMPLETED, now=t1
    ).conversation

    with pytest.raises(ConversationNotMutableError):
        start_turn(conversation, "turn-1", now=t1)


def test_append_message_updates_turn_and_conversation_statistics() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)

    result = append_message(
        conversation, ConversationMessageRole.USER, "Hello?", now=t2
    )

    assert result.validation.valid is True
    turn = result.conversation.turns[0]
    assert len(turn.messages) == 1
    message = turn.messages[0]
    assert message.message_id.value == "turn-1:0"
    assert message.role is ConversationMessageRole.USER
    assert message.content.text == "Hello?"
    assert result.conversation.statistics.message_count == 1
    assert turn.statistics.message_count == 1


def test_append_message_rejects_no_active_turn() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation

    with pytest.raises(NoActiveTurnError):
        append_message(conversation, ConversationMessageRole.USER, "Hi", now=NOW)


def test_attach_engineering_response_rejects_a_project_id_mismatch() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    other_response = _engineering_response(project_id=PROJECT_ID + 1)

    with pytest.raises(ProjectIdMismatchError):
        attach_engineering_response(conversation, other_response, now=t1)


def test_attach_engineering_response_updates_statistics() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    response = _engineering_response(now=t2)

    result = attach_engineering_response(conversation, response, now=t2)

    assert result.validation.valid is True
    turn = result.conversation.turns[0]
    assert turn.engineering_responses == (response,)
    assert result.conversation.statistics.engineering_response_count == 1


def test_complete_turn_sets_completed_status_and_duration() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=3)

    result = complete_turn(conversation, now=t2)

    assert result.validation.valid is True
    turn = result.conversation.turns[0]
    assert turn.status is ConversationTurnStatus.COMPLETED
    assert turn.metadata.completed_at == t2
    assert turn.statistics.turn_duration_seconds == 120.0


def test_complete_turn_rejects_no_active_turn() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation

    with pytest.raises(NoActiveTurnError):
        complete_turn(conversation, now=NOW)


def test_a_new_turn_can_start_after_the_previous_one_completes() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = complete_turn(conversation, now=t2).conversation
    t3 = NOW + timedelta(minutes=3)

    result = start_turn(conversation, "turn-2", now=t3)

    assert result.validation.valid is True
    assert len(result.conversation.turns) == 2
    assert result.conversation.turns[1].sequence == 1


@pytest.mark.parametrize(
    "current,target",
    [
        (ConversationStatus.ACTIVE, ConversationStatus.COMPLETED),
        (ConversationStatus.COMPLETED, ConversationStatus.ARCHIVED),
    ],
)
def test_valid_conversation_transitions_succeed(
    current: ConversationStatus, target: ConversationStatus
) -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    now = NOW
    if current is ConversationStatus.COMPLETED:
        now += timedelta(minutes=1)
        conversation = change_conversation_status(
            conversation, ConversationStatus.COMPLETED, now=now
        ).conversation

    now += timedelta(minutes=1)
    result = change_conversation_status(conversation, target, now=now)
    assert result.validation.valid is True
    assert result.conversation.status is target


@pytest.mark.parametrize(
    "current,target",
    [
        (ConversationStatus.ACTIVE, ConversationStatus.ARCHIVED),
        (ConversationStatus.COMPLETED, ConversationStatus.ACTIVE),
        (ConversationStatus.ARCHIVED, ConversationStatus.ACTIVE),
    ],
)
def test_invalid_conversation_transitions_are_rejected(
    current: ConversationStatus, target: ConversationStatus
) -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    ).conversation
    now = NOW
    if current in (ConversationStatus.COMPLETED, ConversationStatus.ARCHIVED):
        now += timedelta(minutes=1)
        conversation = change_conversation_status(
            conversation, ConversationStatus.COMPLETED, now=now
        ).conversation
    if current is ConversationStatus.ARCHIVED:
        now += timedelta(minutes=1)
        conversation = change_conversation_status(
            conversation, ConversationStatus.ARCHIVED, now=now
        ).conversation

    with pytest.raises(InvalidConversationTransitionError):
        change_conversation_status(conversation, target, now=now + timedelta(minutes=1))


def test_the_builder_class_delegates_to_the_same_functions() -> None:
    via_class = ConversationBuilder.create(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    )
    via_function = create_conversation(
        project_id=PROJECT_ID, session_id="sess-1", conversation_id="conv-1", now=NOW
    )

    assert via_class.conversation == via_function.conversation
