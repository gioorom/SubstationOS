"""
The Conversation and Turn state machines - the same "explicit
transition table plus a pure membership check" convention
``app.domain.project.project_lifecycle`` and
``app.domain.engineering_session.engineering_session_state_machine``
already established.
"""

from __future__ import annotations

from app.domain.conversation.conversation_models import (
    ConversationStatus,
    ConversationTurnStatus,
)

# ACTIVE -> COMPLETED -> ARCHIVED (a strict, linear chain). ARCHIVED is
# terminal - no transition leaves it.
CONVERSATION_VALID_TRANSITIONS: dict[
    ConversationStatus, frozenset[ConversationStatus]
] = {
    ConversationStatus.ACTIVE: frozenset({ConversationStatus.COMPLETED}),
    ConversationStatus.COMPLETED: frozenset({ConversationStatus.ARCHIVED}),
    ConversationStatus.ARCHIVED: frozenset(),
}

# Only an ACTIVE conversation accepts a new turn or a status change of
# its own - COMPLETED/ARCHIVED are read-only, the same "terminal states
# are immutable" discipline every prior bounded context in this
# pipeline establishes.
MUTABLE_CONVERSATION_STATUSES: frozenset[ConversationStatus] = frozenset(
    {ConversationStatus.ACTIVE}
)


def is_conversation_transition_valid(
    current: ConversationStatus, target: ConversationStatus
) -> bool:
    return target in CONVERSATION_VALID_TRANSITIONS[current]


# STARTED -> COMPLETED. A turn, once completed, is never reopened.
TURN_VALID_TRANSITIONS: dict[
    ConversationTurnStatus, frozenset[ConversationTurnStatus]
] = {
    ConversationTurnStatus.STARTED: frozenset(
        {ConversationTurnStatus.COMPLETED}
    ),
    ConversationTurnStatus.COMPLETED: frozenset(),
}

# Only a STARTED turn accepts new messages or an attached
# EngineeringResponse.
MUTABLE_TURN_STATUSES: frozenset[ConversationTurnStatus] = frozenset(
    {ConversationTurnStatus.STARTED}
)


def is_turn_transition_valid(
    current: ConversationTurnStatus, target: ConversationTurnStatus
) -> bool:
    return target in TURN_VALID_TRANSITIONS[current]
