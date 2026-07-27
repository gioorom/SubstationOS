from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)
from app.schemas.engineering_response import (
    EngineeringResponseRead,
    engineering_response_from_schema,
)

# --- Request -----------------------------------------------------------


class ConversationCreateRequestBody(BaseModel):
    """
    A conversation-creation request. ``project_id`` is deliberately
    absent - the path's own ``{project_id}`` is authoritative.
    ``conversation_id`` is deliberately absent too - the composition
    root (the router) generates a fresh identifier, the same discipline
    ``EngineeringSessionId`` generation already established.
    """

    session_id: str
    created_by: str | None = None


class ConversationEventRead(BaseModel):
    event_type: ConversationEventType
    sequence: int
    occurred_at: datetime
    description: str

    model_config = ConfigDict(from_attributes=True)


class ConversationTimelineRead(BaseModel):
    events: list[ConversationEventRead]

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageContentRead(BaseModel):
    text: str

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageMetadataRead(BaseModel):
    conversation_version: str
    turn_id: str
    sequence: int

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageRead(BaseModel):
    message_id: str
    turn_id: str
    role: ConversationMessageRole
    content: ConversationMessageContentRead
    sequence: int
    created_at: datetime
    metadata: ConversationMessageMetadataRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, message: ConversationMessage) -> "ConversationMessageRead":
        return cls(
            message_id=message.message_id.value,
            turn_id=message.turn_id.value,
            role=message.role,
            content=ConversationMessageContentRead.model_validate(message.content),
            sequence=message.sequence,
            created_at=message.created_at,
            metadata=ConversationMessageMetadataRead.model_validate(
                message.metadata
            ),
        )


class ConversationTurnMetadataRead(BaseModel):
    conversation_id: str
    sequence: int
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ConversationTurnStatisticsRead(BaseModel):
    message_count: int
    engineering_response_count: int
    turn_duration_seconds: float | None

    model_config = ConfigDict(from_attributes=True)


class ConversationTurnRead(BaseModel):
    turn_id: str
    conversation_id: str
    status: ConversationTurnStatus
    sequence: int
    messages: list[ConversationMessageRead]
    engineering_responses: list[EngineeringResponseRead]
    timeline: ConversationTimelineRead
    metadata: ConversationTurnMetadataRead
    statistics: ConversationTurnStatisticsRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, turn: ConversationTurn) -> "ConversationTurnRead":
        return cls(
            turn_id=turn.turn_id.value,
            conversation_id=turn.conversation_id.value,
            status=turn.status,
            sequence=turn.sequence,
            messages=[
                ConversationMessageRead.from_domain(message)
                for message in turn.messages
            ],
            engineering_responses=[
                EngineeringResponseRead.model_validate(response)
                for response in turn.engineering_responses
            ],
            timeline=ConversationTimelineRead.model_validate(turn.timeline),
            metadata=ConversationTurnMetadataRead.model_validate(turn.metadata),
            statistics=ConversationTurnStatisticsRead.model_validate(
                turn.statistics
            ),
        )


class ConversationMetadataRead(BaseModel):
    conversation_version: str
    conversation_policy_version: str
    project_id: int
    session_id: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class ConversationStatisticsRead(BaseModel):
    turn_count: int
    message_count: int
    engineering_response_count: int
    timeline_event_count: int
    conversation_duration_seconds: float
    last_activity_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationVersionRead(BaseModel):
    conversation_version: str
    conversation_policy_version: str
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class ConversationRead(BaseModel):
    """
    The Conversation aggregate's own API response shape - and, per this
    milestone's "no persistence" instruction, also the shape every
    subsequent ``start-turn``/``add-message``/``attach-response``/
    ``complete-turn``/``change-status`` call accepts back as its own
    input, since nothing is held in memory between requests.
    """

    conversation_id: str
    session_id: str
    project_id: int
    status: ConversationStatus
    turns: list[ConversationTurnRead]
    timeline: ConversationTimelineRead
    metadata: ConversationMetadataRead
    statistics: ConversationStatisticsRead
    version: ConversationVersionRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationRead":
        return cls(
            conversation_id=conversation.conversation_id.value,
            session_id=conversation.session_id.value,
            project_id=conversation.project_id,
            status=conversation.status,
            turns=[
                ConversationTurnRead.from_domain(turn)
                for turn in conversation.turns
            ],
            timeline=ConversationTimelineRead.model_validate(conversation.timeline),
            metadata=ConversationMetadataRead.model_validate(conversation.metadata),
            statistics=ConversationStatisticsRead.model_validate(
                conversation.statistics
            ),
            version=ConversationVersionRead.model_validate(conversation.version),
        )


class ConversationValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class ConversationBuilderResultRead(BaseModel):
    project_id: int
    conversation: ConversationRead
    validation: ConversationValidationResultRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "ConversationBuilderResultRead":
        return cls(
            project_id=result.project_id,
            conversation=ConversationRead.from_domain(result.conversation),
            validation=ConversationValidationResultRead.model_validate(
                result.validation
            ),
        )


class ConversationStartTurnRequestBody(BaseModel):
    conversation: ConversationRead


class ConversationAddMessageRequestBody(BaseModel):
    conversation: ConversationRead
    role: ConversationMessageRole
    text: str


class ConversationAttachResponseRequestBody(BaseModel):
    conversation: ConversationRead
    response: EngineeringResponseRead


class ConversationCompleteTurnRequestBody(BaseModel):
    conversation: ConversationRead


class ConversationChangeStatusRequestBody(BaseModel):
    conversation: ConversationRead
    target_status: ConversationStatus


# --- Reconstruction ------------------------------------------------------


def _message_from_read(model: ConversationMessageRead) -> ConversationMessage:
    return ConversationMessage(
        message_id=ConversationMessageId(value=model.message_id),
        turn_id=ConversationTurnId(value=model.turn_id),
        role=model.role,
        content=ConversationMessageContent(text=model.content.text),
        sequence=model.sequence,
        created_at=model.created_at,
        metadata=ConversationMessageMetadata(
            conversation_version=model.metadata.conversation_version,
            turn_id=model.metadata.turn_id,
            sequence=model.metadata.sequence,
        ),
    )


def _turn_from_read(model: ConversationTurnRead) -> ConversationTurn:
    return ConversationTurn(
        turn_id=ConversationTurnId(value=model.turn_id),
        conversation_id=ConversationId(value=model.conversation_id),
        status=model.status,
        sequence=model.sequence,
        messages=tuple(_message_from_read(m) for m in model.messages),
        engineering_responses=tuple(
            engineering_response_from_schema(r) for r in model.engineering_responses
        ),
        timeline=ConversationTimeline(
            events=tuple(
                ConversationEvent(
                    event_type=e.event_type,
                    sequence=e.sequence,
                    occurred_at=e.occurred_at,
                    description=e.description,
                )
                for e in model.timeline.events
            )
        ),
        metadata=ConversationTurnMetadata(
            conversation_id=model.metadata.conversation_id,
            sequence=model.metadata.sequence,
            started_at=model.metadata.started_at,
            completed_at=model.metadata.completed_at,
        ),
        statistics=ConversationTurnStatistics(
            message_count=model.statistics.message_count,
            engineering_response_count=(
                model.statistics.engineering_response_count
            ),
            turn_duration_seconds=model.statistics.turn_duration_seconds,
        ),
    )


def conversation_from_schema(model: ConversationRead) -> Conversation:
    return Conversation(
        conversation_id=ConversationId(value=model.conversation_id),
        session_id=EngineeringSessionId(value=model.session_id),
        project_id=model.project_id,
        status=model.status,
        turns=tuple(_turn_from_read(turn) for turn in model.turns),
        timeline=ConversationTimeline(
            events=tuple(
                ConversationEvent(
                    event_type=e.event_type,
                    sequence=e.sequence,
                    occurred_at=e.occurred_at,
                    description=e.description,
                )
                for e in model.timeline.events
            )
        ),
        metadata=ConversationMetadata(
            conversation_version=model.metadata.conversation_version,
            conversation_policy_version=model.metadata.conversation_policy_version,
            project_id=model.metadata.project_id,
            session_id=model.metadata.session_id,
            created_by=model.metadata.created_by,
            created_at=model.metadata.created_at,
            updated_at=model.metadata.updated_at,
            package_version=model.metadata.package_version,
        ),
        statistics=ConversationStatistics(
            turn_count=model.statistics.turn_count,
            message_count=model.statistics.message_count,
            engineering_response_count=model.statistics.engineering_response_count,
            timeline_event_count=model.statistics.timeline_event_count,
            conversation_duration_seconds=(
                model.statistics.conversation_duration_seconds
            ),
            last_activity_at=model.statistics.last_activity_at,
        ),
        version=ConversationVersion(
            conversation_version=model.version.conversation_version,
            conversation_policy_version=model.version.conversation_policy_version,
            package_version=model.version.package_version,
        ),
    )


__all__ = [
    "ConversationCreateRequestBody",
    "ConversationStartTurnRequestBody",
    "ConversationAddMessageRequestBody",
    "ConversationAttachResponseRequestBody",
    "ConversationCompleteTurnRequestBody",
    "ConversationChangeStatusRequestBody",
    "ConversationRead",
    "ConversationBuilderResultRead",
    "conversation_from_schema",
]
