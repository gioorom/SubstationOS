# ADR-0017: Conversation Foundation

## Status

Accepted.

## Context

By Milestone 19 (Engineering Session Foundation, ADR-0016),
`EngineeringSession` exists as the root aggregate for one engineering
work session - project identity, session state, an ordered history of
`EngineeringResponse`s, a timeline, statistics, and version metadata.
It explicitly does not yet own conversation turns, chat history,
memory, tools, or agents.

This milestone introduces `Conversation` - structured engineering
dialogue belonging to an `EngineeringSession`. The obvious, naive shape
would be "a conversation is a list of messages" - the shape every
consumer chat product uses. This milestone deliberately rejects that
shape: **`ConversationTurn`, not `ConversationMessage`, is the primary
conversational unit.** Messages are owned by turns; turns are owned by
conversations; messages never own turns, and the ownership direction is
strictly one way, never reversed.

## Decision

### 1. Turn, not Message, is the primary conversational unit

A single exchange in engineering dialogue is rarely one message - it is
typically: a user's question, some amount of retrieval/context
assembly/provider invocation happening on its behalf, an
`EngineeringResponse` produced from that work, and the assistant's
reply built from it. Modeling this as a flat list of messages forces
every future capability (tool execution, retrieval, agent execution,
assistant reasoning - this milestone's own explicitly named future
work) to either invent its own parallel structure to group "the work
that happened during this exchange," or to awkwardly encode that
structure as synthetic messages that were never really said by
anyone. Making `ConversationTurn` the primary unit gives all of that
future work a single, correctly-scoped home from day one: **future
tool execution, retrieval, agent execution, and assistant reasoning
will all occur inside a Turn**, never bolted onto a flat message list
after the fact.

### 2. EngineeringResponse is referenced by Turn, never copied

A `ConversationTurn` holds a tuple of `EngineeringResponse` objects
directly - by reference (Python object identity through an immutable,
frozen dataclass), never by restating or duplicating their fields.
This is possible without violating the Dependency Rule because
Conversation is explicitly permitted to depend on the Engineering
Response domain contract directly (unlike Engineering Response's own
relationship to the application-layer `LLMResponseEnvelope`, which
required a translation seam - ADR-0015). Engineering Response itself
remains completely unaware that Conversation exists - the same
"upstream never knows about downstream" direction this entire pipeline
already enforces (Structured Retrieval does not know Context Builder
exists; Context Builder does not know Prompt Builder exists).

### 3. Conversation belongs to EngineeringSession by reference, not by embedding

`Conversation.session_id: EngineeringSessionId` names the session a
conversation belongs to; `Conversation` is never embedded inside
`EngineeringSession` as a field, and `EngineeringSession` is never
modified by this milestone. This preserves Milestone 19's own design
without redesigning it (this milestone's own instruction: "do not
redesign previous milestones") while still expressing the "belongs to"
relationship explicitly and durably.

### 4. Only one Turn may be open at a time

`start_turn` raises `TurnAlreadyInProgressError` if the conversation's
most recent turn is still `STARTED`. A conversation's dialogue is
inherently sequential - exactly one interaction is ever "in progress"
at once - so every mutation (`append_message`,
`attach_engineering_response`, `complete_turn`) implicitly targets
"whichever turn is currently open," with no `turn_id` parameter the
caller must track or pass through the API. This keeps the API surface
small and mirrors exactly how `EngineeringSession`'s own operations
never require the caller to re-supply identifiers already implied by
"the current state."

### 5. Message ids are derived, not caller-supplied

Unlike `ConversationId`/`ConversationTurnId` (caller-supplied, the same
discipline `EngineeringSessionId` established), `ConversationMessageId`
is deterministically computed by the builder as
`f"{turn_id.value}:{sequence}"`. A message always belongs to exactly
one already-identified turn and occupies exactly one position within
it - nothing about its identity needs external uniqueness a caller
would have to invent, and deriving it keeps `append_message` callable
with no identifier argument at all.

### 6. No semantic validation

`ConversationValidator`/turn/message validation checks structure only -
ordering, ownership, timeline consistency, complete metadata,
consistent statistics and version fields - never whether a message's
content is coherent, relevant, or engineering-correct. Semantic
judgment of dialogue content is not a solved problem this milestone
attempts to solve; it remains explicitly out of scope, the same
"structure, not semantics" boundary Engineering Response's own
validator (ADR-0015) already draws.

## Consequences

**Easier:**

- Milestone 21 (Conversation Memory Foundation) can introduce
  `ConversationMemory`/`MemoryEntry`/`MemoryWindow`/`MemoryCompaction`
  operating over the existing Conversation -> Turn -> Message
  hierarchy without redesigning it - memory summarizes or windows
  *turns*, a shape that already exists.
- Future tool/retrieval/agent execution has an obvious home (inside a
  Turn) already reserved by this milestone's own vocabulary
  (`ConversationEventType` already includes hooks like
  `ENGINEERING_RESPONSE_ATTACHED`; adding
  `TOOL_EXECUTED`/`AGENT_EXECUTED` later is a vocabulary extension, not
  a structural redesign).
- Conversation's dependency surface stays minimal (exactly two domain
  contexts: `engineering_session`, `engineering_response`) and fully
  application-layer-free, the same guarantee Engineering Session's own
  architecture test established, verified with zero exceptions.

**Harder / deferred:**

- No persistence exists yet - a conversation's lifetime today is
  exactly one client's own request/response chain, the same posture
  Engineering Session already takes.
- `attach-response` and `change-status` endpoints were not literally
  named in this milestone's own "such as" endpoint list, but were added
  because `ENGINEERING_RESPONSE_ATTACHED` (a Turn's own explicitly
  required responsibility: "EngineeringResponse references") and
  `STATUS_CHANGED` (an explicitly required timeline event type) would
  otherwise have no real caller ever exercising them - the same
  documented, in-scope extension precedent ADR-0016 already established
  for `update-configuration`.
- Only one turn may be open at a time - a deliberate simplification
  that keeps this milestone's API surface small; if a future need for
  concurrent/branching turns emerges, it is a documented extension
  point, not solved speculatively here.

## Rejected Alternatives

- **Model Conversation as a flat, ordered list of Messages (the
  standard chat-log shape).** Rejected explicitly by this milestone's
  own framing ("Conversation is NOT a chat log") and on the merits: it
  gives future tool/retrieval/agent execution no natural home without
  either inventing a parallel structure or encoding non-message events
  as synthetic messages - see Decision SS1.
- **Let Message reference or own its parent Turn as more than an id
  (e.g. embed the Turn inside the Message).** Rejected: ownership in
  this pipeline is always one-directional and enforced structurally -
  "Messages never own Turns" is this milestone's own explicit
  instruction, and reversing it would make a Turn's own identity
  ambiguous (which Message's embedded copy is authoritative?).
- **Copy/restate `EngineeringResponse` fields onto the Turn instead of
  holding the object by reference.** Rejected: unlike
  `LLMResponseEnvelope` (an application-layer type Engineering Response
  itself had to restate to obey the Dependency Rule, ADR-0015),
  `EngineeringResponse` is already a domain type Conversation is
  explicitly permitted to depend on - restating it here would be a
  needless, driftable duplication with no Dependency Rule problem to
  solve.
- **Allow multiple concurrently open turns per conversation** (e.g. for
  future parallel tool calls). Rejected for this milestone: no concrete
  requirement demonstrated a need for it, and it would meaningfully
  complicate the state machine and API surface (which turn does a
  message belong to?) for a capability (tools/agents) this milestone
  explicitly excludes.
- **Persist conversations in this milestone.** Rejected, for the same
  reason ADR-0016 rejected persisting sessions: explicitly out of
  scope, and no concrete requirement demonstrated a need for it yet.
