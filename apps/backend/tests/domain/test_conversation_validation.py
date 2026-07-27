from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from app.domain.conversation.conversation_models import (
    Conversation,
    ConversationEvent,
    ConversationEventType,
    ConversationId,
    ConversationMessage,
    ConversationMessageContent,
    ConversationMessageId,
    ConversationMessageMetadata,
    ConversationMessageRole,
    ConversationMetadata,
    ConversationStatistics,
    ConversationStatus,
    ConversationTimeline,
    ConversationTurn,
    ConversationTurnId,
    ConversationTurnMetadata,
    ConversationTurnStatistics,
    ConversationTurnStatus,
    ConversationVersion,
)
from app.domain.conversation.conversation_validation import (
    ConversationValidator,
    validate_conversation,
    validate_turn,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)

NOW = datetime(2026, 1, 1, 10, 0, 0)


def _conversation_timeline(*event_types: ConversationEventType) -> ConversationTimeline:
    events = tuple(
        ConversationEvent(
            event_type=event_type,
            sequence=index,
            occurred_at=NOW + timedelta(minutes=index),
            description="event",
        )
        for index, event_type in enumerate(event_types)
    )
    return ConversationTimeline(events=events)


def _turn(**overrides) -> ConversationTurn:
    defaults = dict(
        turn_id=ConversationTurnId(value="turn-1"),
        conversation_id=ConversationId(value="conv-1"),
        status=ConversationTurnStatus.STARTED,
        sequence=0,
        messages=(),
        engineering_responses=(),
        timeline=_conversation_timeline(ConversationEventType.TURN_STARTED),
        metadata=ConversationTurnMetadata(
            conversation_id="conv-1", sequence=0, started_at=NOW, completed_at=None
        ),
        statistics=ConversationTurnStatistics(
            message_count=0, engineering_response_count=0, turn_duration_seconds=None
        ),
    )
    defaults.update(overrides)
    return ConversationTurn(**defaults)


def _conversation(**overrides) -> Conversation:
    turns = overrides.pop("turns", ())
    timeline = overrides.pop(
        "timeline", _conversation_timeline(ConversationEventType.CONVERSATION_CREATED)
    )
    updated_at = overrides.pop("updated_at", NOW)

    message_count = sum(len(turn.messages) for turn in turns)
    response_count = sum(len(turn.engineering_responses) for turn in turns)

    defaults = dict(
        conversation_id=ConversationId(value="conv-1"),
        session_id=EngineeringSessionId(value="sess-1"),
        project_id=1,
        status=ConversationStatus.ACTIVE,
        turns=turns,
        timeline=timeline,
        metadata=ConversationMetadata(
            conversation_version="1.0",
            conversation_policy_version="1.0",
            project_id=1,
            session_id="sess-1",
            created_by=None,
            created_at=NOW,
            updated_at=updated_at,
            package_version="1.0",
        ),
        statistics=ConversationStatistics(
            turn_count=len(turns),
            message_count=message_count,
            engineering_response_count=response_count,
            timeline_event_count=len(timeline.events),
            conversation_duration_seconds=(updated_at - NOW).total_seconds(),
            last_activity_at=updated_at,
        ),
        version=ConversationVersion(
            conversation_version="1.0",
            conversation_policy_version="1.0",
            package_version="1.0",
        ),
    )
    defaults.update(overrides)
    return Conversation(**defaults)


def test_a_well_formed_conversation_is_valid() -> None:
    result = validate_conversation(_conversation())

    assert result.valid is True
    assert result.errors == ()


def test_the_validator_class_delegates_to_the_same_function() -> None:
    conversation = _conversation()

    assert ConversationValidator.validate(conversation) == validate_conversation(
        conversation
    )


def test_a_well_formed_turn_with_a_message_is_valid() -> None:
    message = ConversationMessage(
        message_id=ConversationMessageId(value="turn-1:0"),
        turn_id=ConversationTurnId(value="turn-1"),
        role=ConversationMessageRole.USER,
        content=ConversationMessageContent(text="hi"),
        sequence=0,
        created_at=NOW,
        metadata=ConversationMessageMetadata(
            conversation_version="1.0", turn_id="turn-1", sequence=0
        ),
    )
    turn = _turn(
        messages=(message,),
        timeline=_conversation_timeline(
            ConversationEventType.TURN_STARTED, ConversationEventType.MESSAGE_ADDED
        ),
        statistics=ConversationTurnStatistics(
            message_count=1, engineering_response_count=0, turn_duration_seconds=None
        ),
    )

    result = validate_turn(turn)

    assert result.valid is True
    assert result.errors == ()


def test_a_message_with_wrong_turn_id_is_rejected() -> None:
    message = ConversationMessage(
        message_id=ConversationMessageId(value="turn-1:0"),
        turn_id=ConversationTurnId(value="other-turn"),
        role=ConversationMessageRole.USER,
        content=ConversationMessageContent(text="hi"),
        sequence=0,
        created_at=NOW,
        metadata=ConversationMessageMetadata(
            conversation_version="1.0", turn_id="turn-1", sequence=0
        ),
    )
    turn = _turn(
        messages=(message,),
        statistics=ConversationTurnStatistics(
            message_count=1, engineering_response_count=0, turn_duration_seconds=None
        ),
    )

    result = validate_turn(turn)

    assert result.valid is False
    assert any("does not belong to its owning turn" in e for e in result.errors)


def test_a_message_with_a_non_derived_id_is_rejected() -> None:
    message = ConversationMessage(
        message_id=ConversationMessageId(value="wrong-id"),
        turn_id=ConversationTurnId(value="turn-1"),
        role=ConversationMessageRole.USER,
        content=ConversationMessageContent(text="hi"),
        sequence=0,
        created_at=NOW,
        metadata=ConversationMessageMetadata(
            conversation_version="1.0", turn_id="turn-1", sequence=0
        ),
    )
    turn = _turn(
        messages=(message,),
        statistics=ConversationTurnStatistics(
            message_count=1, engineering_response_count=0, turn_duration_seconds=None
        ),
    )

    result = validate_turn(turn)

    assert result.valid is False
    assert any("not deterministically derived" in e for e in result.errors)


def test_a_started_turn_with_a_completed_at_timestamp_is_rejected() -> None:
    turn = replace(
        _turn(),
        metadata=ConversationTurnMetadata(
            conversation_id="conv-1", sequence=0, started_at=NOW, completed_at=NOW
        ),
    )

    result = validate_turn(turn)

    assert result.valid is False
    assert any("must not have a completed_at" in e for e in result.errors)


def test_a_completed_turn_without_a_completed_at_timestamp_is_rejected() -> None:
    turn = replace(_turn(), status=ConversationTurnStatus.COMPLETED)

    result = validate_turn(turn)

    assert result.valid is False
    assert any("must have a completed_at" in e for e in result.errors)


def test_turn_message_count_inconsistency_is_rejected() -> None:
    turn = replace(
        _turn(),
        statistics=ConversationTurnStatistics(
            message_count=5, engineering_response_count=0, turn_duration_seconds=None
        ),
    )

    result = validate_turn(turn)

    assert result.valid is False
    assert any("message_count" in e for e in result.errors)


def test_turn_out_of_sequence_within_conversation_is_rejected() -> None:
    turn = _turn(sequence=5)
    conversation = _conversation(
        turns=(turn,),
        timeline=_conversation_timeline(
            ConversationEventType.CONVERSATION_CREATED,
            ConversationEventType.TURN_STARTED,
        ),
        statistics=ConversationStatistics(
            turn_count=1,
            message_count=0,
            engineering_response_count=0,
            timeline_event_count=2,
            conversation_duration_seconds=60.0,
            last_activity_at=NOW + timedelta(minutes=1),
        ),
        updated_at=NOW + timedelta(minutes=1),
    )

    result = validate_conversation(conversation)

    assert result.valid is False
    assert any("expected sequence" in e for e in result.errors)


def test_a_timeline_not_starting_with_conversation_created_is_rejected() -> None:
    timeline = _conversation_timeline(ConversationEventType.STATUS_CHANGED)
    conversation = _conversation(
        timeline=timeline,
        statistics=ConversationStatistics(
            turn_count=0,
            message_count=0,
            engineering_response_count=0,
            timeline_event_count=1,
            conversation_duration_seconds=0.0,
            last_activity_at=NOW,
        ),
    )

    result = validate_conversation(conversation)

    assert result.valid is False
    assert any("CONVERSATION_CREATED" in e for e in result.errors)


def test_incomplete_metadata_is_rejected() -> None:
    conversation = _conversation()
    broken_metadata = replace(conversation.metadata, conversation_version="")
    broken = replace(conversation, metadata=broken_metadata)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("Metadata is incomplete" in e for e in result.errors)


def test_version_inconsistent_with_metadata_is_rejected() -> None:
    conversation = _conversation()
    broken_version = replace(conversation.version, conversation_version="9.9")
    broken = replace(conversation, version=broken_version)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("inconsistent with metadata" in e for e in result.errors)


def test_turn_count_inconsistency_is_rejected() -> None:
    conversation = _conversation()
    broken_statistics = replace(conversation.statistics, turn_count=99)
    broken = replace(conversation, statistics=broken_statistics)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("turn_count" in e for e in result.errors)


def test_message_count_inconsistency_is_rejected() -> None:
    conversation = _conversation()
    broken_statistics = replace(conversation.statistics, message_count=99)
    broken = replace(conversation, statistics=broken_statistics)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("message_count" in e for e in result.errors)


def test_last_activity_at_inconsistency_is_rejected() -> None:
    conversation = _conversation()
    broken_statistics = replace(
        conversation.statistics, last_activity_at=NOW + timedelta(days=1)
    )
    broken = replace(conversation, statistics=broken_statistics)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("last_activity_at" in e for e in result.errors)


def test_conversation_duration_inconsistency_is_rejected() -> None:
    conversation = _conversation()
    broken_statistics = replace(
        conversation.statistics, conversation_duration_seconds=12345.0
    )
    broken = replace(conversation, statistics=broken_statistics)

    result = validate_conversation(broken)

    assert result.valid is False
    assert any("conversation_duration_seconds" in e for e in result.errors)
