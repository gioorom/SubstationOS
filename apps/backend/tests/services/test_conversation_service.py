from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.conversation.conversation_exceptions import (
    NoActiveTurnError,
    TurnAlreadyInProgressError,
)
from app.domain.conversation.conversation_models import (
    ConversationMessageRole,
    ConversationStatus,
)
from app.services import conversation_service

PROJECT_ID = 71
NOW = datetime(2026, 1, 1, 11, 0, 0)


def test_create_returns_a_valid_active_conversation() -> None:
    result = conversation_service.create(
        project_id=PROJECT_ID, session_id="svc-sess-1", conversation_id="svc-conv-1", now=NOW
    )

    assert result.project_id == PROJECT_ID
    assert result.conversation.status is ConversationStatus.ACTIVE
    assert result.validation.valid is True


def test_start_new_turn_then_add_message_then_complete() -> None:
    conversation = conversation_service.create(
        project_id=PROJECT_ID, session_id="svc-sess-2", conversation_id="svc-conv-2", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = conversation_service.start_new_turn(
        conversation=conversation, turn_id="svc-turn-1", now=t1
    ).conversation
    t2 = NOW + timedelta(minutes=2)
    conversation = conversation_service.add_message(
        conversation=conversation,
        role=ConversationMessageRole.USER,
        text="Hello",
        now=t2,
    ).conversation
    t3 = NOW + timedelta(minutes=3)
    result = conversation_service.finish_turn(conversation=conversation, now=t3)

    assert result.validation.valid is True
    assert result.conversation.turns[0].messages[0].content.text == "Hello"


def test_start_new_turn_rejects_a_second_open_turn() -> None:
    conversation = conversation_service.create(
        project_id=PROJECT_ID, session_id="svc-sess-3", conversation_id="svc-conv-3", now=NOW
    ).conversation
    t1 = NOW + timedelta(minutes=1)
    conversation = conversation_service.start_new_turn(
        conversation=conversation, turn_id="svc-turn-1", now=t1
    ).conversation

    with pytest.raises(TurnAlreadyInProgressError):
        conversation_service.start_new_turn(
            conversation=conversation, turn_id="svc-turn-2", now=t1
        )


def test_add_message_rejects_no_active_turn() -> None:
    conversation = conversation_service.create(
        project_id=PROJECT_ID, session_id="svc-sess-4", conversation_id="svc-conv-4", now=NOW
    ).conversation

    with pytest.raises(NoActiveTurnError):
        conversation_service.add_message(
            conversation=conversation,
            role=ConversationMessageRole.USER,
            text="Hi",
            now=NOW,
        )
