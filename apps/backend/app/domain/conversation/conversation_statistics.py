"""
Statistics for Conversation (Milestone 20). Summarizes already-assembled
turns/messages/timeline into ``ConversationStatistics``/
``ConversationTurnStatistics`` - never a recomputation of anything an
earlier operation already decided. O(n) in the number of turns
(bounded, small for a single conversation). No semantic scoring, no
token accounting.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_models import (
    ConversationEvent,
    ConversationStatistics,
    ConversationTurn,
    ConversationTurnStatistics,
)


def build_turn_statistics(turn: ConversationTurn) -> ConversationTurnStatistics:
    duration: float | None = None
    if turn.metadata.completed_at is not None:
        duration = (
            turn.metadata.completed_at - turn.metadata.started_at
        ).total_seconds()

    return ConversationTurnStatistics(
        message_count=len(turn.messages),
        engineering_response_count=len(turn.engineering_responses),
        turn_duration_seconds=duration,
    )


def build_conversation_statistics(
    *,
    turns: tuple[ConversationTurn, ...],
    events: tuple[ConversationEvent, ...],
    created_at: datetime,
    now: datetime,
) -> ConversationStatistics:
    message_count = sum(len(turn.messages) for turn in turns)
    engineering_response_count = sum(
        len(turn.engineering_responses) for turn in turns
    )

    return ConversationStatistics(
        turn_count=len(turns),
        message_count=message_count,
        engineering_response_count=engineering_response_count,
        timeline_event_count=len(events),
        conversation_duration_seconds=(now - created_at).total_seconds(),
        last_activity_at=now,
    )
