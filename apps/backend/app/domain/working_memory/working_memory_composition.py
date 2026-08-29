"""
Working Memory Composition (Milestone 21's central pipeline stage).
Builds every ``WorkingMemoryEntry`` from an already-built
``Conversation``/``EngineeringSession`` - never from raw retrieval,
never from a database, never from an AI provider call of its own.

This module performs **no AI usage, no summarization, and no semantic
interpretation of message or response content**. Every entry below is
derived from *structural* facts already present on its inputs - a
message's own role and position, a turn's own status, an
``EngineeringResponse``'s own already-computed status/warnings/
uncertainties/references - never by reading and understanding what a
message or response actually *says*. This is why
``CURRENT_OBJECTIVE``/``CURRENT_EQUIPMENT``/``CURRENT_ELECTRICAL_AREA``/
``CURRENT_TASK`` are never produced here: identifying "what equipment
is this conversation about" from free text requires exactly the kind
of semantic interpretation this milestone forbids (see ADR-0018).

Although the milestone frames "EngineeringResponses" as a distinct
input alongside Conversation and EngineeringSession, they are never
passed as a separate parameter here - they are gathered from both
already-supplied objects (``EngineeringSession.engineering_responses``
and every ``Conversation`` turn's own ``engineering_responses``),
avoiding a redundant, potentially-inconsistent second source of the
same data.

O(n) in the number of turns/messages and responses on the input - a
small, constant number of linear passes over already-materialized data.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_models import (
    Conversation,
    ConversationMessage,
    ConversationMessageRole,
    ConversationTurnStatus,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
)
from app.domain.working_memory.working_memory_policy import (
    ENTRY_LIFETIME,
    ENTRY_PRIORITY,
    RECENT_ENGINEERING_RESPONSE_LIMIT,
)
from app.domain.working_memory.working_memory_models import (
    WorkingMemoryEntry,
    WorkingMemoryEntryType,
    WorkingMemorySource,
)


def _open_question(conversation: Conversation) -> ConversationMessage | None:
    """The current open question, if one exists: the conversation's
    most recent turn is still ``STARTED``, and that turn's most recent
    message is a ``USER`` message with no reply yet - a purely
    structural fact (turn status + message role + position), never a
    reading of what the message says."""

    if not conversation.turns:
        return None

    last_turn = conversation.turns[-1]
    if last_turn.status is not ConversationTurnStatus.STARTED:
        return None

    if not last_turn.messages:
        return None

    last_message = last_turn.messages[-1]
    if last_message.role is not ConversationMessageRole.USER:
        return None

    return last_message


def _gather_recent_engineering_responses(
    conversation: Conversation,
    engineering_session: EngineeringSession,
    *,
    limit: int = RECENT_ENGINEERING_RESPONSE_LIMIT,
) -> tuple[EngineeringResponse, ...]:
    """Every ``EngineeringResponse`` reachable from either the owning
    session's own history or the conversation's own turns, deduplicated,
    ordered by ``metadata.assembled_at`` (most recent first), capped at
    ``limit`` - the fixed, documented recency window."""

    gathered: list[EngineeringResponse] = list(
        engineering_session.engineering_responses
    )
    for turn in conversation.turns:
        for response in turn.engineering_responses:
            if response not in gathered:
                gathered.append(response)

    gathered.sort(key=lambda response: response.metadata.assembled_at, reverse=True)

    return tuple(gathered[:limit])


def compose_working_memory_entries(
    conversation: Conversation,
    engineering_session: EngineeringSession,
    *,
    now: datetime,
) -> tuple[WorkingMemoryEntry, ...]:
    entries: list[WorkingMemoryEntry] = []

    def _append(
        entry_type: WorkingMemoryEntryType,
        content: str,
        source: WorkingMemorySource,
        *,
        engineering_response: EngineeringResponse | None = None,
    ) -> None:
        sequence = len(entries)
        entries.append(
            WorkingMemoryEntry(
                entry_id=str(sequence),
                entry_type=entry_type,
                content=content,
                source=source,
                priority=ENTRY_PRIORITY[entry_type],
                lifetime=ENTRY_LIFETIME[entry_type],
                sequence=sequence,
                created_at=now,
                engineering_response=engineering_response,
            )
        )

    open_question = _open_question(conversation)
    if open_question is not None:
        _append(
            WorkingMemoryEntryType.OPEN_QUESTION,
            open_question.content.text,
            WorkingMemorySource.CONVERSATION_MESSAGE,
        )

    recent_responses = _gather_recent_engineering_responses(
        conversation, engineering_session
    )
    for response in recent_responses:
        _append(
            WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE,
            f"status={response.status.value}",
            WorkingMemorySource.ENGINEERING_RESPONSE,
            engineering_response=response,
        )

    seen_item_ids: set[str] = set()
    for response in recent_responses:
        for reference in response.references:
            if reference.item_id in seen_item_ids:
                continue
            seen_item_ids.add(reference.item_id)
            _append(
                WorkingMemoryEntryType.ACTIVE_REFERENCE,
                reference.item_id,
                WorkingMemorySource.ENGINEERING_RESPONSE_REFERENCE,
            )

    if recent_responses:
        latest = recent_responses[0]
        for uncertainty in latest.uncertainties:
            for reason in uncertainty.reasons:
                _append(
                    WorkingMemoryEntryType.ASSUMPTION,
                    reason,
                    WorkingMemorySource.ENGINEERING_RESPONSE_UNCERTAINTY,
                )
        for warning in latest.warnings:
            _append(
                WorkingMemoryEntryType.CONSTRAINT,
                warning.message,
                WorkingMemorySource.ENGINEERING_RESPONSE_WARNING,
            )

    return tuple(entries)
