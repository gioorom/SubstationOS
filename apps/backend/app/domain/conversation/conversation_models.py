"""
Value objects for Conversation (EPIC 5, Milestone 20). Every type here
is immutable and deterministic: the same sequence of builder
operations, given the same caller-supplied identifiers and ``now``
values, always produces the same ``Conversation``.

Conversation models structured engineering dialogue - it is **not** a
chat log. A ``Conversation`` belongs to exactly one ``EngineeringSession``
(referenced by id, never embedded - the same "reference the owner,
never copy it" direction ``EngineeringSession`` itself already
established toward ``EngineeringResponse``) and owns an ordered
sequence of ``ConversationTurn``s. **``ConversationTurn``, not
``ConversationMessage``, is the primary conversational unit**: future
tool execution, retrieval, agent execution, and assistant reasoning
will all occur inside a Turn (see
``docs/architecture/adr/0017-conversation-foundation.md`` for why).
Messages never own Turns - the ownership direction is strictly
Conversation -> Turn -> Message, one way, never reversed.

A ``ConversationTurn`` references ``EngineeringResponse`` objects
directly (never copies or restates them) - allowed because Conversation
is permitted to depend on the Engineering Response domain contract
directly (unlike Engineering Response's own relationship to the
application-layer ``LLMResponseEnvelope``, which required a translation
seam - see ADR-0015). Conversation performs no AI usage, no I/O, and no
persistence of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)


class ConversationStatus(str, Enum):
    """The lifecycle state of one Conversation - a closed, exhaustive
    set. See ``conversation_state_machine.py`` for the valid transition
    table."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ConversationTurnStatus(str, Enum):
    """The lifecycle state of one Turn - started, then completed, never
    reopened."""

    STARTED = "started"
    COMPLETED = "completed"


class ConversationMessageRole(str, Enum):
    """Every kind of message participant this milestone supports.
    ``TOOL``/``AGENT`` are reserved: no tool or agent execution exists
    yet (a future milestone's concern), but the vocabulary is fixed now
    so a future message never needs a role this enum cannot express."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    AGENT = "agent"


class ConversationEventType(str, Enum):
    """Every kind of deterministic timeline event a conversation (or one
    of its turns) can record - a closed, exhaustive set, never a
    free-form event name."""

    CONVERSATION_CREATED = "conversation_created"
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    MESSAGE_ADDED = "message_added"
    ENGINEERING_RESPONSE_ATTACHED = "engineering_response_attached"
    STATUS_CHANGED = "status_changed"


@dataclass(frozen=True, slots=True)
class ConversationId:
    """A conversation's stable identity. Always caller-supplied (never
    generated inside the domain layer, which must remain deterministic
    and side-effect free) - the composition root (the router) generates
    a fresh identifier per real conversation, the same discipline
    ``EngineeringSessionId`` already established."""

    value: str


@dataclass(frozen=True, slots=True)
class ConversationTurnId:
    """A turn's stable identity. Always caller-supplied, for the same
    reason ``ConversationId`` is."""

    value: str


@dataclass(frozen=True, slots=True)
class ConversationMessageId:
    """
    A message's stable identity. Unlike ``ConversationId``/
    ``ConversationTurnId``, this is **deterministically derived** by the
    builder from ``turn_id`` and the message's own ``sequence`` -
    ``f"{turn_id.value}:{sequence}"`` - never caller-supplied. A message
    always belongs to exactly one already-identified turn and occupies
    exactly one position within it, so nothing about its identity needs
    external uniqueness a caller would have to invent; deriving it keeps
    ``append_message`` callable with no identifier argument at all.
    """

    value: str


@dataclass(frozen=True, slots=True)
class ConversationEvent:
    """One immutable, deterministically constructed timeline entry.
    ``sequence`` is strictly increasing from zero within one timeline;
    ``occurred_at`` is always caller-supplied, never read from the wall
    clock inside the domain layer."""

    event_type: ConversationEventType
    sequence: int
    occurred_at: datetime
    description: str


@dataclass(frozen=True, slots=True)
class ConversationTimeline:
    """An append-only, ordered ledger of events. Both a ``Conversation``
    and each of its ``ConversationTurn``s carry their own
    ``ConversationTimeline`` - the conversation's own timeline records
    every event across the whole conversation; a turn's own timeline
    records only the events that occurred within that turn - never
    reordered, never mutated in place."""

    events: tuple[ConversationEvent, ...]


@dataclass(frozen=True, slots=True)
class ConversationMessageContent:
    """A message's content. Deliberately minimal (plain text only) -
    multimodal or structured content is out of this milestone's scope."""

    text: str


@dataclass(frozen=True, slots=True)
class ConversationMessageMetadata:
    """Identifying fields echoed onto the message itself, for
    single-place inspection - the same "versioned field plus a metadata
    echo" pattern every upstream context in this pipeline already
    establishes."""

    conversation_version: str
    turn_id: str
    sequence: int


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """One immutable message within a turn. Never modified in place,
    never owns a turn (a message is always the owned side of the
    relationship)."""

    message_id: ConversationMessageId
    turn_id: ConversationTurnId
    role: ConversationMessageRole
    content: ConversationMessageContent
    sequence: int
    created_at: datetime
    metadata: ConversationMessageMetadata


@dataclass(frozen=True, slots=True)
class ConversationTurnMetadata:
    conversation_id: str
    sequence: int
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConversationTurnStatistics:
    message_count: int
    engineering_response_count: int
    turn_duration_seconds: float | None
    """``None`` while the turn is still ``STARTED`` (no ``completed_at``
    yet to measure against) - never estimated or defaulted to zero."""


@dataclass(frozen=True, slots=True)
class ConversationTurnValidationResult:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """
    One complete interaction within a conversation - the primary
    conversational unit (see module docstring and ADR-0017). Owns user
    and assistant messages, ``EngineeringResponse`` references (never
    copies), its own timeline events, metadata, and statistics. Future
    tool executions, agent executions, and retrieval executions will
    also belong here - none exist yet.
    """

    turn_id: ConversationTurnId
    conversation_id: ConversationId
    status: ConversationTurnStatus
    sequence: int
    messages: tuple[ConversationMessage, ...]
    engineering_responses: tuple[EngineeringResponse, ...]
    timeline: ConversationTimeline
    metadata: ConversationTurnMetadata
    statistics: ConversationTurnStatistics


@dataclass(frozen=True, slots=True)
class ConversationPolicy:
    """The versioned, documented conversation policy this bounded
    context applies - which state transitions are valid, never a
    per-request, ad hoc choice."""

    version: str


@dataclass(frozen=True, slots=True)
class ConversationVersion:
    conversation_version: str
    conversation_policy_version: str
    package_version: str


@dataclass(frozen=True, slots=True)
class ConversationMetadata:
    conversation_version: str
    conversation_policy_version: str
    project_id: int
    session_id: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    package_version: str


@dataclass(frozen=True, slots=True)
class ConversationStatistics:
    turn_count: int
    message_count: int
    engineering_response_count: int
    timeline_event_count: int
    conversation_duration_seconds: float
    last_activity_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationValidationResult:
    """
    Whether the just-built ``Conversation`` satisfies every structural
    invariant this milestone requires (ordering, ownership, timeline
    consistency, complete metadata, internally consistent statistics
    and version fields). **No semantic validation** - this never judges
    whether a message's content makes engineering sense, only whether
    the structure is well-formed. Never causes building to raise;
    Conversation always produces a structurally valid object by
    construction - this is an inspectable, testable proof of that, not
    a gate a caller must pass.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Conversation:
    """
    The root of one structured engineering dialogue, belonging to
    exactly one ``EngineeringSession`` (referenced by ``session_id``,
    never embedded). Owns an ordered sequence of ``ConversationTurn``s;
    never owns a Message directly - only a Turn does.
    """

    conversation_id: ConversationId
    session_id: EngineeringSessionId
    project_id: int
    status: ConversationStatus
    turns: tuple[ConversationTurn, ...]
    timeline: ConversationTimeline
    metadata: ConversationMetadata
    statistics: ConversationStatistics
    version: ConversationVersion


@dataclass(frozen=True, slots=True)
class ConversationBuilderResult:
    """The full envelope one Conversation Builder operation returns -
    the request's own project id, paired with the resulting
    ``Conversation`` and its self-validation result. Every builder
    operation (create, start turn, append message, attach an
    EngineeringResponse, complete turn, change status) returns the
    *whole*, updated ``Conversation`` - never a standalone Turn or
    Message object - the same "the aggregate is always returned in
    full" convention ``EngineeringSession`` already established."""

    project_id: int
    conversation: Conversation
    validation: ConversationValidationResult
