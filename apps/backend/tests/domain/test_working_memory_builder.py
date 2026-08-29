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
    append_message,
    attach_engineering_response,
    complete_turn,
    create_conversation,
    start_turn,
)
from app.domain.conversation.conversation_models import ConversationMessageRole
from app.domain.engineering_session.engineering_session_builder import (
    append_engineering_response,
    build_initial_session,
)
from app.domain.working_memory.working_memory_builder import (
    WorkingMemoryBuilder,
    build_working_memory,
    rebuild_working_memory,
)
from app.domain.working_memory.working_memory_exceptions import (
    ConversationSessionMismatchError,
    ProjectIdMismatchError,
)
from app.domain.working_memory.working_memory_models import WorkingMemoryEntryType
from app.services import context_builder_service, engineering_response_service, prompt_builder_service

from tests._governed_context import designation_result

PROJECT_ID = 81
NOW = datetime(2026, 1, 1, 12, 0, 0)


def _engineering_response(project_id: int = PROJECT_ID, now: datetime = NOW, text: str = "Answer."):
    context_result = context_builder_service.build_context_package(
        project_id=project_id, results=(designation_result("TR1", ()),), now=now
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
                text=text,
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
            context_assembly_version=prompt_result.package.metadata.context_assembly_version,
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


def _session(project_id: int = PROJECT_ID, session_id: str = "sess-1"):
    return build_initial_session(project_id=project_id, session_id=session_id, now=NOW).session


def _conversation(project_id: int = PROJECT_ID, session_id: str = "sess-1"):
    return create_conversation(
        project_id=project_id, session_id=session_id, conversation_id="conv-1", now=NOW
    ).conversation


def test_an_empty_conversation_produces_a_valid_empty_working_memory() -> None:
    result = build_working_memory(
        conversation=_conversation(), engineering_session=_session(), now=NOW
    )

    assert result.validation.valid is True
    assert result.working_memory.entries == ()
    assert result.working_memory.statistics.entry_count == 0
    assert result.working_memory.working_memory_id.value == "conv-1:working-memory"


def test_an_open_user_question_becomes_an_open_question_entry() -> None:
    conversation = _conversation()
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "What does C-295 feed?", now=t2
    ).conversation

    result = build_working_memory(
        conversation=conversation, engineering_session=_session(), now=t2
    )

    assert result.validation.valid is True
    entries = result.working_memory.entries
    assert len(entries) == 1
    assert entries[0].entry_type is WorkingMemoryEntryType.OPEN_QUESTION
    assert entries[0].content == "What does C-295 feed?"
    assert result.working_memory.statistics.open_question_count == 1


def test_an_answered_question_is_not_an_open_question() -> None:
    conversation = _conversation()
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "What does C-295 feed?", now=t2
    ).conversation
    t3 = NOW + timedelta(minutes=3)
    conversation = append_message(
        conversation, ConversationMessageRole.ASSISTANT, "It feeds TR2.", now=t3
    ).conversation

    result = build_working_memory(
        conversation=conversation, engineering_session=_session(), now=t3
    )

    open_questions = [
        e for e in result.working_memory.entries
        if e.entry_type is WorkingMemoryEntryType.OPEN_QUESTION
    ]
    assert open_questions == []


def test_a_completed_turn_has_no_open_question() -> None:
    conversation = _conversation()
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "What does C-295 feed?", now=t2
    ).conversation
    t3 = NOW + timedelta(minutes=3)
    conversation = complete_turn(conversation, now=t3).conversation

    result = build_working_memory(
        conversation=conversation, engineering_session=_session(), now=t3
    )

    open_questions = [
        e for e in result.working_memory.entries
        if e.entry_type is WorkingMemoryEntryType.OPEN_QUESTION
    ]
    assert open_questions == []


def test_recent_engineering_response_active_reference_and_constraint_entries() -> (
    None
):
    conversation = _conversation()
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    response = _engineering_response(now=t2)
    conversation = attach_engineering_response(conversation, response, now=t2).conversation

    result = build_working_memory(
        conversation=conversation, engineering_session=_session(), now=t2
    )

    assert result.validation.valid is True
    entry_types = {e.entry_type for e in result.working_memory.entries}
    assert WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE in entry_types

    response_entry = next(
        e
        for e in result.working_memory.entries
        if e.entry_type is WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
    )
    assert response_entry.engineering_response is response
    assert (
        result.working_memory.statistics.recent_engineering_response_count == 1
    )
    # This synthetic response has no retrieved candidates, so Engineering
    # Response's own builder reports an INSUFFICIENT_EVIDENCE warning -
    # surfaced here as a structural CONSTRAINT entry.
    assert result.working_memory.statistics.constraint_count >= 1


def test_engineering_responses_are_gathered_from_both_session_and_conversation() -> (
    None
):
    session = _session()
    t1 = NOW + timedelta(minutes=1)
    session_response = _engineering_response(now=t1, text="Session-level answer.")
    session = append_engineering_response(session, session_response, now=t1).session

    conversation = _conversation()
    t2 = NOW + timedelta(minutes=2)
    conversation = start_turn(conversation, "turn-1", now=t2).conversation
    t3 = NOW + timedelta(minutes=3)
    turn_response = _engineering_response(now=t3, text="Turn-level answer.")
    conversation = attach_engineering_response(
        conversation, turn_response, now=t3
    ).conversation

    result = build_working_memory(
        conversation=conversation, engineering_session=session, now=t3
    )

    referenced_responses = {
        e.engineering_response
        for e in result.working_memory.entries
        if e.entry_type is WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
    }
    assert session_response in referenced_responses
    assert turn_response in referenced_responses
    # More recent (by metadata.assembled_at) comes first.
    recent_entries = [
        e
        for e in result.working_memory.entries
        if e.entry_type is WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
    ]
    assert recent_entries[0].engineering_response is turn_response
    assert recent_entries[1].engineering_response is session_response


def test_project_id_mismatch_is_rejected() -> None:
    conversation = _conversation(project_id=PROJECT_ID)
    other_session = _session(project_id=PROJECT_ID + 1, session_id="sess-other")

    with pytest.raises(ProjectIdMismatchError):
        build_working_memory(
            conversation=conversation, engineering_session=other_session, now=NOW
        )


def test_session_id_mismatch_is_rejected() -> None:
    conversation = _conversation(session_id="sess-1")
    other_session = _session(session_id="sess-2")

    with pytest.raises(ConversationSessionMismatchError):
        build_working_memory(
            conversation=conversation, engineering_session=other_session, now=NOW
        )


def test_rebuild_produces_an_identical_result_to_build() -> None:
    conversation = _conversation()
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "Question?", now=t2
    ).conversation

    build_result = build_working_memory(
        conversation=conversation, engineering_session=_session(), now=t2
    )
    rebuild_result = rebuild_working_memory(
        conversation=conversation, engineering_session=_session(), now=t2
    )

    assert build_result.working_memory == rebuild_result.working_memory


def test_working_memory_id_is_deterministic_from_conversation_id() -> None:
    result1 = build_working_memory(
        conversation=_conversation(), engineering_session=_session(), now=NOW
    )
    result2 = build_working_memory(
        conversation=_conversation(), engineering_session=_session(), now=NOW
    )

    assert (
        result1.working_memory.working_memory_id
        == result2.working_memory.working_memory_id
    )


def test_the_builder_class_delegates_to_the_same_functions() -> None:
    via_class = WorkingMemoryBuilder.build(
        conversation=_conversation(), engineering_session=_session(), now=NOW
    )
    via_function = build_working_memory(
        conversation=_conversation(), engineering_session=_session(), now=NOW
    )

    assert via_class.working_memory == via_function.working_memory
