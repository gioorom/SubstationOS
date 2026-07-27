"""
Validation for Conversation (Milestone 20). Proves, after each builder
operation, that a ``Conversation`` (and each of its ``ConversationTurn``s
and ``ConversationMessage``s) satisfies every structural invariant this
milestone requires: ordering, ownership, timeline consistency, complete
metadata, and internally consistent statistics/version fields. **No
semantic validation** - this never judges whether a message's content
makes engineering sense, only whether the structure is well-formed.
Never causes building to raise - Conversation always produces a
structurally valid object by construction; this is an inspectable,
testable proof of that, not a gate a caller must pass.
"""

from __future__ import annotations

from app.domain.conversation.conversation_models import (
    Conversation,
    ConversationEventType,
    ConversationMessage,
    ConversationTurn,
    ConversationTurnStatus,
    ConversationTurnValidationResult,
    ConversationValidationResult,
)


def _validate_message(
    message: ConversationMessage, turn: ConversationTurn, expected_sequence: int
) -> list[str]:
    errors: list[str] = []

    if message.turn_id != turn.turn_id:
        errors.append(
            f"Message at sequence {expected_sequence} does not belong "
            "to its owning turn."
        )

    if message.sequence != expected_sequence:
        errors.append(
            f"Message sequence {message.sequence} does not match its "
            f"position {expected_sequence} within the turn."
        )

    expected_message_id = f"{turn.turn_id.value}:{expected_sequence}"
    if message.message_id.value != expected_message_id:
        errors.append(
            f"Message id '{message.message_id.value}' is not "
            f"deterministically derived (expected '{expected_message_id}')."
        )

    if (
        message.metadata.turn_id != turn.turn_id.value
        or message.metadata.sequence != expected_sequence
    ):
        errors.append(
            f"Message metadata is inconsistent with its own turn_id/sequence "
            f"at position {expected_sequence}."
        )

    return errors


def validate_turn(turn: ConversationTurn) -> ConversationTurnValidationResult:
    errors: list[str] = []

    if not turn.turn_id.value or not turn.turn_id.value.strip():
        errors.append("turn_id is blank.")

    for index, message in enumerate(turn.messages):
        errors.extend(_validate_message(message, turn, index))

    events = turn.timeline.events
    if not events:
        errors.append("Turn timeline must contain at least one event.")
    else:
        if events[0].event_type is not ConversationEventType.TURN_STARTED:
            errors.append("Turn timeline does not begin with TURN_STARTED.")

        expected_sequence = 0
        previous_occurred_at = None
        for event in events:
            if event.sequence != expected_sequence:
                errors.append(
                    "Turn timeline events are not sequenced contiguously "
                    "from zero."
                )
                break
            expected_sequence += 1
            if (
                previous_occurred_at is not None
                and event.occurred_at < previous_occurred_at
            ):
                errors.append(
                    "Turn timeline events are not chronologically ordered."
                )
                break
            previous_occurred_at = event.occurred_at

    if turn.status is ConversationTurnStatus.STARTED:
        if turn.metadata.completed_at is not None:
            errors.append(
                "A STARTED turn must not have a completed_at timestamp."
            )
    elif turn.status is ConversationTurnStatus.COMPLETED:
        if turn.metadata.completed_at is None:
            errors.append("A COMPLETED turn must have a completed_at timestamp.")
        elif turn.metadata.completed_at < turn.metadata.started_at:
            errors.append("completed_at precedes started_at.")

    if turn.statistics.message_count != len(turn.messages):
        errors.append(
            "Turn statistics message_count is inconsistent with the "
            "assembled messages."
        )
    if turn.statistics.engineering_response_count != len(
        turn.engineering_responses
    ):
        errors.append(
            "Turn statistics engineering_response_count is inconsistent "
            "with the assembled EngineeringResponses."
        )

    if turn.status is ConversationTurnStatus.STARTED:
        if turn.statistics.turn_duration_seconds is not None:
            errors.append(
                "turn_duration_seconds must be None while the turn is "
                "still STARTED."
            )
    else:
        expected_duration = (
            turn.metadata.completed_at - turn.metadata.started_at
        ).total_seconds() if turn.metadata.completed_at is not None else None
        if turn.statistics.turn_duration_seconds != expected_duration:
            errors.append(
                "turn_duration_seconds is inconsistent with "
                "started_at/completed_at."
            )

    return ConversationTurnValidationResult(valid=not errors, errors=tuple(errors))


def validate_conversation(conversation: Conversation) -> ConversationValidationResult:
    errors: list[str] = []

    if (
        not conversation.conversation_id.value
        or not conversation.conversation_id.value.strip()
    ):
        errors.append("conversation_id is blank.")

    if conversation.project_id <= 0:
        errors.append("project_id is not positive.")

    if not conversation.session_id.value or not conversation.session_id.value.strip():
        errors.append("session_id is blank.")

    turns = conversation.turns
    started_turn_count = 0
    for index, turn in enumerate(turns):
        if turn.sequence != index:
            errors.append(
                f"Turn at position {index} does not have the expected "
                "sequence."
            )
        if turn.conversation_id != conversation.conversation_id:
            errors.append(
                f"Turn at position {index} does not belong to this "
                "conversation."
            )
        if turn.status is ConversationTurnStatus.STARTED:
            started_turn_count += 1

        turn_validation = validate_turn(turn)
        if not turn_validation.valid:
            errors.extend(turn_validation.errors)

    if started_turn_count > 1:
        errors.append("More than one turn is STARTED at the same time.")
    if started_turn_count == 1 and turns and turns[-1].status is not (
        ConversationTurnStatus.STARTED
    ):
        errors.append("The STARTED turn is not the most recent turn.")

    events = conversation.timeline.events
    if not events:
        errors.append("Timeline must contain at least one event.")
    else:
        if events[0].event_type is not ConversationEventType.CONVERSATION_CREATED:
            errors.append("Timeline does not begin with CONVERSATION_CREATED.")

        expected_sequence = 0
        previous_occurred_at = None
        for event in events:
            if event.sequence != expected_sequence:
                errors.append(
                    "Timeline events are not sequenced contiguously "
                    "from zero."
                )
                break
            expected_sequence += 1
            if (
                previous_occurred_at is not None
                and event.occurred_at < previous_occurred_at
            ):
                errors.append("Timeline events are not chronologically ordered.")
                break
            previous_occurred_at = event.occurred_at

    metadata = conversation.metadata
    if (
        not metadata.conversation_version
        or not metadata.conversation_policy_version
        or not metadata.package_version
        or metadata.project_id <= 0
        or not metadata.session_id
        or metadata.created_at is None
        or metadata.updated_at is None
        or metadata.updated_at < metadata.created_at
    ):
        errors.append("Metadata is incomplete or inconsistent.")

    version = conversation.version
    if (
        not version.conversation_version
        or not version.conversation_policy_version
        or not version.package_version
    ):
        errors.append("Version fields are incomplete.")
    elif (
        version.conversation_version != metadata.conversation_version
        or version.conversation_policy_version
        != metadata.conversation_policy_version
        or version.package_version != metadata.package_version
    ):
        errors.append("Version fields are inconsistent with metadata.")

    statistics = conversation.statistics
    if statistics.turn_count != len(turns):
        errors.append(
            "Statistics turn_count is inconsistent with the assembled turns."
        )
    expected_message_count = sum(len(turn.messages) for turn in turns)
    if statistics.message_count != expected_message_count:
        errors.append(
            "Statistics message_count is inconsistent with the "
            "assembled turns' messages."
        )
    expected_response_count = sum(
        len(turn.engineering_responses) for turn in turns
    )
    if statistics.engineering_response_count != expected_response_count:
        errors.append(
            "Statistics engineering_response_count is inconsistent with "
            "the assembled turns' EngineeringResponses."
        )
    if statistics.timeline_event_count != len(events):
        errors.append(
            "Statistics timeline_event_count is inconsistent with the "
            "assembled timeline."
        )
    if statistics.last_activity_at != metadata.updated_at:
        errors.append(
            "Statistics last_activity_at is inconsistent with "
            "metadata.updated_at."
        )
    expected_duration = (metadata.updated_at - metadata.created_at).total_seconds()
    if statistics.conversation_duration_seconds != expected_duration:
        errors.append(
            "Statistics conversation_duration_seconds is inconsistent "
            "with metadata's created_at/updated_at."
        )

    return ConversationValidationResult(valid=not errors, errors=tuple(errors))


class ConversationValidator:
    """A thin, named façade over ``validate_conversation`` - kept only
    for the same reason every sibling bounded context's own validator
    class is: every one of them exposes the same logic as a plain
    function instead."""

    @staticmethod
    def validate(conversation: Conversation) -> ConversationValidationResult:
        return validate_conversation(conversation)
