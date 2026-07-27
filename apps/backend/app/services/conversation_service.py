"""
Application service for Conversation (EPIC 5, Milestone 20). Thin
orchestration over the pure domain builder
(``conversation_builder.py``) - like Engineering Session's own service,
this needs no application-layer translation seam, because Conversation's
inputs (an already-built ``EngineeringResponse``) are already domain
types. Performs no persistence and no I/O of any kind.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_builder import (
    append_message,
    attach_engineering_response,
    change_conversation_status,
    complete_turn,
    create_conversation,
    start_turn,
)
from app.domain.conversation.conversation_models import (
    Conversation,
    ConversationBuilderResult,
    ConversationMessageRole,
    ConversationStatus,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)


def create(
    *,
    project_id: int,
    session_id: str,
    conversation_id: str,
    now: datetime,
    created_by: str | None = None,
) -> ConversationBuilderResult:
    return create_conversation(
        project_id=project_id,
        session_id=session_id,
        conversation_id=conversation_id,
        now=now,
        created_by=created_by,
    )


def start_new_turn(
    *, conversation: Conversation, turn_id: str, now: datetime
) -> ConversationBuilderResult:
    return start_turn(conversation, turn_id, now=now)


def add_message(
    *,
    conversation: Conversation,
    role: ConversationMessageRole,
    text: str,
    now: datetime,
) -> ConversationBuilderResult:
    return append_message(conversation, role, text, now=now)


def attach_response(
    *,
    conversation: Conversation,
    response: EngineeringResponse,
    now: datetime,
) -> ConversationBuilderResult:
    return attach_engineering_response(conversation, response, now=now)


def finish_turn(
    *, conversation: Conversation, now: datetime
) -> ConversationBuilderResult:
    return complete_turn(conversation, now=now)


def change_status(
    *,
    conversation: Conversation,
    target_status: ConversationStatus,
    now: datetime,
) -> ConversationBuilderResult:
    return change_conversation_status(conversation, target_status, now=now)
