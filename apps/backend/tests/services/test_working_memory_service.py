from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.conversation.conversation_builder import (
    append_message,
    create_conversation,
    start_turn,
)
from app.domain.conversation.conversation_models import ConversationMessageRole
from app.domain.engineering_session.engineering_session_builder import (
    build_initial_session,
)
from app.domain.working_memory.working_memory_exceptions import (
    ConversationSessionMismatchError,
)
from app.domain.working_memory.working_memory_models import WorkingMemoryEntryType
from app.services import working_memory_service

PROJECT_ID = 91
NOW = datetime(2026, 1, 1, 14, 0, 0)


def test_build_returns_a_valid_working_memory() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="svc-sess-1", conversation_id="svc-conv-1", now=NOW
    ).conversation
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="svc-sess-1", now=NOW
    ).session

    result = working_memory_service.build(
        conversation=conversation, engineering_session=session, now=NOW
    )

    assert result.project_id == PROJECT_ID
    assert result.validation.valid is True
    assert result.working_memory.entries == ()


def test_build_surfaces_an_open_question() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="svc-sess-2", conversation_id="svc-conv-2", now=NOW
    ).conversation
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="svc-sess-2", now=NOW
    ).session
    t1 = NOW + timedelta(minutes=1)
    conversation = start_turn(conversation, "svc-turn-1", now=t1).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "Which breaker protects TR2?", now=t2
    ).conversation

    result = working_memory_service.build(
        conversation=conversation, engineering_session=session, now=t2
    )

    assert result.working_memory.entries[0].entry_type is (
        WorkingMemoryEntryType.OPEN_QUESTION
    )


def test_rebuild_matches_build() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="svc-sess-3", conversation_id="svc-conv-3", now=NOW
    ).conversation
    session = build_initial_session(
        project_id=PROJECT_ID, session_id="svc-sess-3", now=NOW
    ).session

    build_result = working_memory_service.build(
        conversation=conversation, engineering_session=session, now=NOW
    )
    rebuild_result = working_memory_service.rebuild(
        conversation=conversation, engineering_session=session, now=NOW
    )

    assert build_result.working_memory == rebuild_result.working_memory


def test_session_mismatch_is_rejected() -> None:
    conversation = create_conversation(
        project_id=PROJECT_ID, session_id="svc-sess-4", conversation_id="svc-conv-4", now=NOW
    ).conversation
    other_session = build_initial_session(
        project_id=PROJECT_ID, session_id="svc-sess-other", now=NOW
    ).session

    with pytest.raises(ConversationSessionMismatchError):
        working_memory_service.build(
            conversation=conversation, engineering_session=other_session, now=NOW
        )
