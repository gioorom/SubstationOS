"""
Value objects for Engineering Session (EPIC 5, Milestone 19). Every
type here is immutable and deterministic: the same sequence of
builder operations, given the same caller-supplied ``session_id`` and
``now`` values, always produces the same ``EngineeringSession``.

Engineering Session is the root aggregate every future conversation,
tool, assistant, and agent will execute inside - but it is not a chat
itself (see
``docs/architecture/adr/0016-engineering-session-foundation.md`` for
why Session precedes Conversation and why Conversation is not the
aggregate root). It owns project identity, session state, the ordered
history of ``EngineeringResponse`` objects generated during the
session, an append-only timeline of deterministic events, statistics,
and version metadata - nothing about conversation turns, chat history,
memory, tools, or agents belongs here yet.

Engineering Session depends on exactly one other domain bounded
context: `app.domain.engineering_response` (to own
``EngineeringResponse`` objects directly - the same "reuse the
upstream domain type" pattern every context in this pipeline already
follows). It performs no AI usage, no I/O, and no persistence of its
own - every session here is a pure, in-memory value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)


class EngineeringSessionStatus(str, Enum):
    """The lifecycle state of one Engineering Session - a closed,
    exhaustive set. See ``engineering_session_state_machine.py`` for
    the valid transition table."""

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class EngineeringSessionEventType(str, Enum):
    """Every kind of deterministic timeline event a session can record
    - a closed, exhaustive set, never a free-form event name."""

    SESSION_CREATED = "session_created"
    ENGINEERING_RESPONSE_ADDED = "engineering_response_added"
    STATE_CHANGED = "state_changed"
    CONFIGURATION_UPDATED = "configuration_updated"


@dataclass(frozen=True, slots=True)
class EngineeringSessionId:
    """A session's stable identity. Always caller-supplied (never
    generated inside the domain layer, which must remain deterministic
    and side-effect free) - the composition root (the router) generates
    a fresh identifier per real session and passes it in explicitly,
    the same "impure id generation at the edge, pure domain underneath"
    discipline the LLM Invocation Runtime already established for
    ``request_correlation_id``."""

    value: str


@dataclass(frozen=True, slots=True)
class EngineeringSessionState:
    """The session's current status plus when it was last changed -
    distinct from the bare ``EngineeringSessionStatus`` enum, which only
    enumerates the possible values."""

    status: EngineeringSessionStatus
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class EngineeringSessionEvent:
    """One immutable, deterministically constructed timeline entry.
    ``sequence`` is strictly increasing from zero within one session's
    timeline; ``occurred_at`` is always caller-supplied, never read from
    the wall clock inside the domain layer."""

    event_type: EngineeringSessionEventType
    sequence: int
    occurred_at: datetime
    description: str


@dataclass(frozen=True, slots=True)
class EngineeringSessionTimeline:
    """An append-only, ordered ledger of every event a session has
    recorded - never reordered, never mutated in place; each builder
    operation returns a new ``EngineeringSessionTimeline`` with one more
    event appended."""

    events: tuple[EngineeringSessionEvent, ...]


@dataclass(frozen=True, slots=True)
class EngineeringSessionPolicy:
    """The versioned, documented session policy Engineering Session
    applies - which state transitions are valid, never a per-request,
    ad hoc choice."""

    version: str


@dataclass(frozen=True, slots=True)
class EngineeringSessionConfiguration:
    """Everything about *how* a session presents itself - never *what*
    engineering work it contains (that is
    ``EngineeringSession.engineering_responses``). ``title``/``notes``
    are the only caller-configurable fields this milestone defines;
    updating either produces a ``CONFIGURATION_UPDATED`` timeline
    event."""

    session_policy: EngineeringSessionPolicy
    engineering_session_version: str
    title: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class EngineeringSessionVersion:
    """The full version identity of one ``EngineeringSession`` - echoed
    again, for convenient single-place inspection, inside
    ``EngineeringSessionMetadata`` (the same "versioned field plus a
    metadata echo" pattern ``PromptVersion``/``EngineeringResponseVersion``
    already established upstream)."""

    engineering_session_version: str
    session_policy_version: str
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringSessionMetadata:
    engineering_session_version: str
    session_policy_version: str
    project_id: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringSessionStatistics:
    response_count: int
    timeline_event_count: int
    session_duration_seconds: float
    last_activity_at: datetime


@dataclass(frozen=True, slots=True)
class EngineeringSessionValidationResult:
    """
    The Validation stage's output: whether the just-built
    ``EngineeringSession`` satisfies every structural invariant this
    milestone requires (valid state transitions, ordered timeline,
    preserved response ordering, complete metadata, internally
    consistent statistics and version fields). Never causes building to
    raise - Engineering Session always produces a structurally valid
    session by construction; this is an inspectable, testable proof of
    that, not a gate a caller must pass.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringSession:
    """
    The root aggregate representing one complete engineering work
    session on a project. Future conversations, tools, assistants, and
    agents will all execute inside an ``EngineeringSession`` - but none
    of that exists yet (see this module's own docstring and ADR-0016).
    """

    session_id: EngineeringSessionId
    project_id: int
    state: EngineeringSessionState
    engineering_responses: tuple[EngineeringResponse, ...]
    configuration: EngineeringSessionConfiguration
    timeline: EngineeringSessionTimeline
    metadata: EngineeringSessionMetadata
    statistics: EngineeringSessionStatistics
    version: EngineeringSessionVersion


@dataclass(frozen=True, slots=True)
class EngineeringSessionBuilderResult:
    """The full envelope one Engineering Session Builder operation
    returns - the request's own project id, paired with the resulting
    ``EngineeringSession`` and its self-validation result."""

    project_id: int
    session: EngineeringSession
    validation: EngineeringSessionValidationResult
