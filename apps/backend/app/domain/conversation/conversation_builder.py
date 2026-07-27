"""
Conversation Builder (Milestone 20's central pipeline stage). Six
deterministic operations, each returning a new ``ConversationBuilderResult``
(never mutating its input, always returning the *whole* updated
``Conversation`` - never a standalone Turn or Message object):

    create_conversation          - creates a brand-new conversation
    start_turn                   - starts a new turn (only one may be open)
    append_message                - appends one message to the open turn
    attach_engineering_response   - attaches one EngineeringResponse to the open turn
    complete_turn                 - completes the open turn
    change_conversation_status    - transitions conversation status

Every operation appends exactly one new, immutable ``ConversationEvent``
to the conversation's own timeline; ``start_turn``/``append_message``/
``attach_engineering_response``/``complete_turn`` also append the same
kind of event to the affected turn's own timeline. No AI usage, no I/O,
no persistence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.conversation.conversation_exceptions import (
    ConversationNotMutableError,
    InvalidConversationTransitionError,
    InvalidTurnTransitionError,
    NoActiveTurnError,
    TurnAlreadyInProgressError,
)
from app.domain.conversation.conversation_input_validator import (
    ConversationInputValidator,
)
from app.domain.conversation.conversation_metadata import (
    build_metadata,
    build_version,
)
from app.domain.conversation.conversation_models import (
    Conversation,
    ConversationBuilderResult,
    ConversationEvent,
    ConversationEventType,
    ConversationId,
    ConversationMessage,
    ConversationMessageContent,
    ConversationMessageId,
    ConversationMessageMetadata,
    ConversationMessageRole,
    ConversationPolicy,
    ConversationStatus,
    ConversationTimeline,
    ConversationTurn,
    ConversationTurnId,
    ConversationTurnMetadata,
    ConversationTurnStatistics,
    ConversationTurnStatus,
)
from app.domain.conversation.conversation_policy import (
    CONVERSATION_POLICY_VERSION,
    CONVERSATION_VERSION,
)
from app.domain.conversation.conversation_state_machine import (
    MUTABLE_CONVERSATION_STATUSES,
    is_conversation_transition_valid,
    is_turn_transition_valid,
)
from app.domain.conversation.conversation_statistics import (
    build_conversation_statistics,
    build_turn_statistics,
)
from app.domain.conversation.conversation_validation import validate_conversation
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)


def _current_turn(conversation: Conversation) -> ConversationTurn | None:
    """The conversation's most recently started turn, if it is still
    open (``STARTED``) - ``None`` if there is no turn yet, or the most
    recent one has already been completed. Only one turn may be open at
    a time."""

    if not conversation.turns:
        return None

    last_turn = conversation.turns[-1]
    if last_turn.status is ConversationTurnStatus.STARTED:
        return last_turn

    return None


def _finalize(
    *,
    conversation_id: ConversationId,
    session_id: EngineeringSessionId,
    project_id: int,
    status: ConversationStatus,
    turns: tuple[ConversationTurn, ...],
    events: tuple[ConversationEvent, ...],
    created_by: str | None,
    created_at: datetime,
    now: datetime,
) -> ConversationBuilderResult:
    policy = ConversationPolicy(version=CONVERSATION_POLICY_VERSION)
    metadata = build_metadata(
        conversation_version=CONVERSATION_VERSION,
        policy=policy,
        project_id=project_id,
        session_id=session_id.value,
        created_by=created_by,
        created_at=created_at,
        updated_at=now,
    )
    version = build_version(
        conversation_version=CONVERSATION_VERSION, policy=policy
    )
    statistics = build_conversation_statistics(
        turns=turns, events=events, created_at=created_at, now=now
    )

    conversation = Conversation(
        conversation_id=conversation_id,
        session_id=session_id,
        project_id=project_id,
        status=status,
        turns=turns,
        timeline=ConversationTimeline(events=events),
        metadata=metadata,
        statistics=statistics,
        version=version,
    )

    validation = validate_conversation(conversation)

    return ConversationBuilderResult(
        project_id=project_id, conversation=conversation, validation=validation
    )


def create_conversation(
    *,
    project_id: int,
    session_id: str,
    conversation_id: str,
    now: datetime,
    created_by: str | None = None,
) -> ConversationBuilderResult:
    ConversationInputValidator.validate_project_id(project_id)
    ConversationInputValidator.validate_session_id(session_id)
    ConversationInputValidator.validate_conversation_id(conversation_id)

    created_event = ConversationEvent(
        event_type=ConversationEventType.CONVERSATION_CREATED,
        sequence=0,
        occurred_at=now,
        description=f"Conversation created for project {project_id}.",
    )

    return _finalize(
        conversation_id=ConversationId(value=conversation_id),
        session_id=EngineeringSessionId(value=session_id),
        project_id=project_id,
        status=ConversationStatus.ACTIVE,
        turns=(),
        events=(created_event,),
        created_by=created_by,
        created_at=now,
        now=now,
    )


def start_turn(
    conversation: Conversation, turn_id: str, *, now: datetime
) -> ConversationBuilderResult:
    if conversation.status not in MUTABLE_CONVERSATION_STATUSES:
        raise ConversationNotMutableError(conversation.status)

    ConversationInputValidator.validate_turn_id(turn_id)

    existing_open_turn = _current_turn(conversation)
    if existing_open_turn is not None:
        raise TurnAlreadyInProgressError(existing_open_turn.turn_id.value)

    sequence = len(conversation.turns)
    turn_event = ConversationEvent(
        event_type=ConversationEventType.TURN_STARTED,
        sequence=0,
        occurred_at=now,
        description=f"Turn {sequence} started.",
    )
    new_turn = ConversationTurn(
        turn_id=ConversationTurnId(value=turn_id),
        conversation_id=conversation.conversation_id,
        status=ConversationTurnStatus.STARTED,
        sequence=sequence,
        messages=(),
        engineering_responses=(),
        timeline=ConversationTimeline(events=(turn_event,)),
        metadata=ConversationTurnMetadata(
            conversation_id=conversation.conversation_id.value,
            sequence=sequence,
            started_at=now,
            completed_at=None,
        ),
        statistics=ConversationTurnStatistics(
            message_count=0,
            engineering_response_count=0,
            turn_duration_seconds=None,
        ),
    )

    turns = conversation.turns + (new_turn,)
    events = conversation.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.TURN_STARTED,
            sequence=len(conversation.timeline.events),
            occurred_at=now,
            description=f"Turn {sequence} started.",
        ),
    )

    return _finalize(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        status=conversation.status,
        turns=turns,
        events=events,
        created_by=conversation.metadata.created_by,
        created_at=conversation.metadata.created_at,
        now=now,
    )


def _replace_current_turn(
    conversation: Conversation, updated_turn: ConversationTurn
) -> tuple[ConversationTurn, ...]:
    return conversation.turns[:-1] + (updated_turn,)


def append_message(
    conversation: Conversation,
    role: ConversationMessageRole,
    text: str,
    *,
    now: datetime,
) -> ConversationBuilderResult:
    turn = _current_turn(conversation)
    if turn is None:
        raise NoActiveTurnError()

    message_sequence = len(turn.messages)
    message = ConversationMessage(
        message_id=ConversationMessageId(
            value=f"{turn.turn_id.value}:{message_sequence}"
        ),
        turn_id=turn.turn_id,
        role=role,
        content=ConversationMessageContent(text=text),
        sequence=message_sequence,
        created_at=now,
        metadata=ConversationMessageMetadata(
            conversation_version=CONVERSATION_VERSION,
            turn_id=turn.turn_id.value,
            sequence=message_sequence,
        ),
    )

    turn_events = turn.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.MESSAGE_ADDED,
            sequence=len(turn.timeline.events),
            occurred_at=now,
            description=f"Message #{message_sequence} added (role={role.value}).",
        ),
    )
    updated_turn = replace(
        turn,
        messages=turn.messages + (message,),
        timeline=ConversationTimeline(events=turn_events),
    )
    updated_turn = replace(
        updated_turn, statistics=build_turn_statistics(updated_turn)
    )

    turns = _replace_current_turn(conversation, updated_turn)
    events = conversation.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.MESSAGE_ADDED,
            sequence=len(conversation.timeline.events),
            occurred_at=now,
            description=(
                f"Message #{message_sequence} added to turn "
                f"{turn.sequence} (role={role.value})."
            ),
        ),
    )

    return _finalize(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        status=conversation.status,
        turns=turns,
        events=events,
        created_by=conversation.metadata.created_by,
        created_at=conversation.metadata.created_at,
        now=now,
    )


def attach_engineering_response(
    conversation: Conversation,
    response: EngineeringResponse,
    *,
    now: datetime,
) -> ConversationBuilderResult:
    turn = _current_turn(conversation)
    if turn is None:
        raise NoActiveTurnError()

    ConversationInputValidator.validate_response_belongs_to_project(
        conversation.project_id, response
    )

    turn_events = turn.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.ENGINEERING_RESPONSE_ATTACHED,
            sequence=len(turn.timeline.events),
            occurred_at=now,
            description=(
                f"EngineeringResponse attached "
                f"(status={response.status.value})."
            ),
        ),
    )
    updated_turn = replace(
        turn,
        engineering_responses=turn.engineering_responses + (response,),
        timeline=ConversationTimeline(events=turn_events),
    )
    updated_turn = replace(
        updated_turn, statistics=build_turn_statistics(updated_turn)
    )

    turns = _replace_current_turn(conversation, updated_turn)
    events = conversation.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.ENGINEERING_RESPONSE_ATTACHED,
            sequence=len(conversation.timeline.events),
            occurred_at=now,
            description=(
                f"EngineeringResponse attached to turn {turn.sequence} "
                f"(status={response.status.value})."
            ),
        ),
    )

    return _finalize(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        status=conversation.status,
        turns=turns,
        events=events,
        created_by=conversation.metadata.created_by,
        created_at=conversation.metadata.created_at,
        now=now,
    )


def complete_turn(
    conversation: Conversation, *, now: datetime
) -> ConversationBuilderResult:
    turn = _current_turn(conversation)
    if turn is None:
        raise NoActiveTurnError()

    if not is_turn_transition_valid(
        turn.status, ConversationTurnStatus.COMPLETED
    ):
        raise InvalidTurnTransitionError(
            turn.status, ConversationTurnStatus.COMPLETED
        )

    turn_events = turn.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.TURN_COMPLETED,
            sequence=len(turn.timeline.events),
            occurred_at=now,
            description=f"Turn {turn.sequence} completed.",
        ),
    )
    updated_turn = replace(
        turn,
        status=ConversationTurnStatus.COMPLETED,
        metadata=replace(turn.metadata, completed_at=now),
        timeline=ConversationTimeline(events=turn_events),
    )
    updated_turn = replace(
        updated_turn, statistics=build_turn_statistics(updated_turn)
    )

    turns = _replace_current_turn(conversation, updated_turn)
    events = conversation.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.TURN_COMPLETED,
            sequence=len(conversation.timeline.events),
            occurred_at=now,
            description=f"Turn {turn.sequence} completed.",
        ),
    )

    return _finalize(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        status=conversation.status,
        turns=turns,
        events=events,
        created_by=conversation.metadata.created_by,
        created_at=conversation.metadata.created_at,
        now=now,
    )


def change_conversation_status(
    conversation: Conversation,
    target_status: ConversationStatus,
    *,
    now: datetime,
) -> ConversationBuilderResult:
    current_status = conversation.status
    if not is_conversation_transition_valid(current_status, target_status):
        raise InvalidConversationTransitionError(current_status, target_status)

    events = conversation.timeline.events + (
        ConversationEvent(
            event_type=ConversationEventType.STATUS_CHANGED,
            sequence=len(conversation.timeline.events),
            occurred_at=now,
            description=(
                f"Status changed from '{current_status.value}' to "
                f"'{target_status.value}'."
            ),
        ),
    )

    return _finalize(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        status=target_status,
        turns=conversation.turns,
        events=events,
        created_by=conversation.metadata.created_by,
        created_at=conversation.metadata.created_at,
        now=now,
    )


class ConversationBuilder:
    """A thin, named façade over the module-level builder functions -
    kept for the same reason ``EngineeringSessionBuilder`` is: every
    sibling bounded context exposes this logic as plain functions
    instead."""

    @staticmethod
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

    @staticmethod
    def start_turn(
        conversation: Conversation, turn_id: str, *, now: datetime
    ) -> ConversationBuilderResult:
        return start_turn(conversation, turn_id, now=now)

    @staticmethod
    def append_message(
        conversation: Conversation,
        role: ConversationMessageRole,
        text: str,
        *,
        now: datetime,
    ) -> ConversationBuilderResult:
        return append_message(conversation, role, text, now=now)

    @staticmethod
    def attach_engineering_response(
        conversation: Conversation,
        response: EngineeringResponse,
        *,
        now: datetime,
    ) -> ConversationBuilderResult:
        return attach_engineering_response(conversation, response, now=now)

    @staticmethod
    def complete_turn(
        conversation: Conversation, *, now: datetime
    ) -> ConversationBuilderResult:
        return complete_turn(conversation, now=now)

    @staticmethod
    def change_status(
        conversation: Conversation,
        target_status: ConversationStatus,
        *,
        now: datetime,
    ) -> ConversationBuilderResult:
        return change_conversation_status(conversation, target_status, now=now)
