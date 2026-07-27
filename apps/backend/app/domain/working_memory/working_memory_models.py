"""
Value objects for Working Memory (EPIC 5, Milestone 21). Every type
here is immutable and deterministic: the same ``Conversation`` and
``EngineeringSession``, given the same ``now``, always produce the same
``WorkingMemory``.

Working Memory is **not** conversation history and **not** project
knowledge. It is the temporary engineering context required to
continue reasoning during a session - current open questions, recently
produced ``EngineeringResponse``s, the evidence references they cite,
and the assumptions/constraints those responses already, deterministically
recorded. It can always be rebuilt from its own inputs (see
``docs/architecture/adr/0018-working-memory-foundation.md``) - nothing
here is ever stored beyond one build, and nothing here is ever edited
by an LLM.

Working Memory belongs to exactly one ``Conversation`` (referenced by
``ConversationId``, never embedded) and, transitively, to the
``EngineeringSession`` that conversation belongs to. It performs no AI
usage, no summarization, and no semantic interpretation of message
content - every entry is derived from *structural* facts already
present on its inputs (message role, turn status, response status,
already-computed warnings/uncertainties/references), never by reading
and understanding what a message or response actually says. This is
why ``CURRENT_OBJECTIVE``/``CURRENT_EQUIPMENT``/
``CURRENT_ELECTRICAL_AREA``/``CURRENT_TASK`` exist as named entry types
but are never populated by this milestone's builder - identifying "what
equipment is this conversation about" from free text is exactly the
kind of semantic interpretation this milestone forbids (see
``working_memory_composition.py``'s own module docstring).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.conversation.conversation_models import ConversationId
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)


class WorkingMemoryEntryType(str, Enum):
    """Every kind of Working Memory entry - a closed, exhaustive set.
    ``CURRENT_OBJECTIVE``/``CURRENT_EQUIPMENT``/
    ``CURRENT_ELECTRICAL_AREA``/``CURRENT_TASK`` are reserved: no
    structural signal exists today that identifies them without
    semantic interpretation, so this milestone's builder never produces
    them - the vocabulary exists so a future, genuinely structural
    source (e.g. an explicit "current equipment" field a user sets)
    could populate them without a schema change."""

    CURRENT_OBJECTIVE = "current_objective"
    CURRENT_EQUIPMENT = "current_equipment"
    CURRENT_ELECTRICAL_AREA = "current_electrical_area"
    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    RECENT_ENGINEERING_RESPONSE = "recent_engineering_response"
    ACTIVE_REFERENCE = "active_reference"
    CURRENT_TASK = "current_task"
    CONSTRAINT = "constraint"


class WorkingMemoryPriority(str, Enum):
    """How urgently this entry matters for continued reasoning - a
    fixed, policy-assigned value per entry type
    (``working_memory_policy.py``'s ``ENTRY_PRIORITY``), never an
    ad hoc per-entry judgment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WorkingMemoryLifetime(str, Enum):
    """The scope an entry remains relevant for - a fixed,
    policy-assigned value per entry type
    (``working_memory_policy.py``'s ``ENTRY_LIFETIME``)."""

    TURN = "turn"
    CONVERSATION = "conversation"
    SESSION = "session"


class WorkingMemorySource(str, Enum):
    """Exactly which structural input produced an entry - recorded so
    "is this rebuildable from deterministic inputs" is always
    verifiable, not merely asserted."""

    CONVERSATION_MESSAGE = "conversation_message"
    ENGINEERING_RESPONSE = "engineering_response"
    ENGINEERING_RESPONSE_WARNING = "engineering_response_warning"
    ENGINEERING_RESPONSE_UNCERTAINTY = "engineering_response_uncertainty"
    ENGINEERING_RESPONSE_REFERENCE = "engineering_response_reference"


@dataclass(frozen=True, slots=True)
class WorkingMemoryId:
    """
    A working memory's identity - deterministically derived from its
    owning ``ConversationId`` (``f"{conversation_id}:working-memory"``),
    **never caller-supplied or randomly generated**. Exactly one
    conversation ever needs exactly one working memory identity, and
    "rebuild" must yield the same identity "build" did - a random or
    caller-invented id would make that guarantee impossible to state.
    """

    value: str


@dataclass(frozen=True, slots=True)
class WorkingMemoryEntry:
    """
    One immutable entry. ``content`` is always either a verbatim copy
    of already-existing text (a message's own content, a warning's own
    message, an uncertainty's own reason, a reference's own candidate
    id) or a small, deterministic structural summary string (e.g. an
    ``EngineeringResponse``'s own status) - never AI-generated, never a
    semantic summary of meaning. ``engineering_response`` is populated
    only for ``RECENT_ENGINEERING_RESPONSE`` entries - held by
    reference, never copied, the same discipline
    ``ConversationTurn.engineering_responses`` already established.
    """

    entry_id: str
    entry_type: WorkingMemoryEntryType
    content: str
    source: WorkingMemorySource
    priority: WorkingMemoryPriority
    lifetime: WorkingMemoryLifetime
    sequence: int
    created_at: datetime
    engineering_response: EngineeringResponse | None = None


@dataclass(frozen=True, slots=True)
class WorkingMemoryPolicy:
    """The versioned, documented policy Working Memory applies - fixed
    entry priority/lifetime assignments and the recency window, never a
    per-request, ad hoc choice."""

    version: str


@dataclass(frozen=True, slots=True)
class WorkingMemoryVersion:
    working_memory_version: str
    working_memory_policy_version: str
    package_version: str


@dataclass(frozen=True, slots=True)
class WorkingMemoryMetadata:
    working_memory_version: str
    working_memory_policy_version: str
    project_id: int
    conversation_id: str
    session_id: str
    built_at: datetime
    package_version: str


@dataclass(frozen=True, slots=True)
class WorkingMemoryStatistics:
    entry_count: int
    open_question_count: int
    assumption_count: int
    constraint_count: int
    active_reference_count: int
    recent_engineering_response_count: int


@dataclass(frozen=True, slots=True)
class WorkingMemoryValidationResult:
    """
    Whether the just-built ``WorkingMemory`` satisfies every structural
    invariant this milestone requires (entry ordering, lifetime/priority
    consistency with policy, complete metadata, internally consistent
    statistics and version fields). **No semantic validation** - never
    whether an entry's content is engineering-correct, only whether the
    structure is well-formed and honestly rebuildable.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkingMemory:
    """
    The temporary engineering context required to continue reasoning
    during a session - belonging to exactly one ``Conversation``
    (referenced, never embedded). Always fully derivable from its own
    inputs; never edited by an LLM; never persisted.
    """

    working_memory_id: WorkingMemoryId
    conversation_id: ConversationId
    session_id: EngineeringSessionId
    project_id: int
    entries: tuple[WorkingMemoryEntry, ...]
    metadata: WorkingMemoryMetadata
    statistics: WorkingMemoryStatistics
    version: WorkingMemoryVersion


@dataclass(frozen=True, slots=True)
class WorkingMemoryBuilderResult:
    project_id: int
    working_memory: WorkingMemory
    validation: WorkingMemoryValidationResult
