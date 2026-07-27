# ADR-0018: Working Memory Foundation

## Status

Accepted.

## Context

By Milestone 20 (Conversation Foundation, ADR-0017), a `Conversation`
owns an ordered sequence of `ConversationTurn`s, each owning ordered
`ConversationMessage`s and referencing `EngineeringResponse`s produced
during that turn. Nothing yet exists that gives a future assistant or
tool a bounded, structured view of "what matters right now to keep
reasoning" without re-reading the entire conversation and re-deriving
that view by hand every time.

The obvious temptation is to build something that *sounds* like
working memory in most AI products: a running summary maintained by an
LLM, updated turn by turn, that compresses history into "what the
assistant currently believes." This milestone rejects that shape
entirely. **Working Memory is not conversation history and is not
project knowledge.** It is the temporary engineering context required
to continue reasoning during a session, and it can always be rebuilt
from deterministic inputs - it is never maintained as evolving state an
LLM writes to.

## Decision

### 1. Working Memory is neither Conversation nor Knowledge

Two distinct things it is easy to confuse Working Memory with, and
why it is neither:

- **Not Conversation.** `Conversation` (Milestone 20) is the permanent,
  ordered record of what was actually said and done - every turn,
  every message, every attached response, forever (for as long as the
  conversation exists). Working Memory is a *derived*, *bounded*,
  *disposable* view over a slice of that record - the open question, a
  handful of recent responses, their references, their already-computed
  caveats. Deleting a `WorkingMemory` loses nothing, because it was
  never the source of truth; deleting a `Conversation` loses the actual
  dialogue.
- **Not Knowledge.** The Project Knowledge Graph (EPIC 3) is
  reviewed, versioned, permanent engineering fact - `CanonicalFact`s
  that survive across every session and every conversation, admitted
  only through the mandatory review gate (ADR-0004). Working Memory is
  session-scoped and conversation-scoped context that exists only to
  keep reasoning going *right now* - it never gets reviewed, never gets
  promoted into the graph, and disappears the moment nothing rebuilds
  it. Conflating the two would let ephemeral, unreviewed context
  masquerade as engineering truth - exactly what ADR-0004 and ADR-0006
  already forbid.

### 2. Working Memory is deterministic because it must always be rebuildable

Every entry is derived from *structural* facts already present on its
inputs - a message's own role and position within a turn, a turn's own
status, an `EngineeringResponse`'s own already-computed status,
warnings, uncertainties, and references - never from reading and
understanding what a message or response actually *says*. Given the
same `Conversation` and `EngineeringSession`, `build_working_memory`
always produces the same `WorkingMemory`. This is not a convenience;
it is the entire point: Working Memory carries no information a caller
could not re-derive on demand, so nothing about it can ever drift out
of sync with its own source, and nothing about it needs to be trusted
as an independent record.

### 3. LLMs never edit Working Memory

There is no mutation operation, no "update working memory with what the
model just said," and no field an LLM's own output writes into. The
**only** way a `WorkingMemory`'s contents change is by rebuilding it
from a (possibly now-different) `Conversation`/`EngineeringSession` -
i.e. by the underlying structural facts actually changing (a new
message added, a new response attached, a turn completed), never by an
LLM directly asserting "remember this." This closes off an entire
class of risk this codebase has guarded against since ADR-0006 (AI
composes and translates; it never becomes a source of truth) - an LLM
that could freely edit its own working memory could smuggle
unreviewed, self-asserted "facts" into every future turn's context
with no structural trace of where they came from.

### 4. Entries are typed and structurally derived, never semantically interpreted

`WorkingMemoryEntryType` includes types this milestone's builder
*does* populate today - `OPEN_QUESTION` (the last unanswered `USER`
message in a still-open turn, verbatim), `RECENT_ENGINEERING_RESPONSE`
(referenced by object, never copied, the same discipline
`ConversationTurn.engineering_responses` already established),
`ACTIVE_REFERENCE` (each recent response's own already-computed
evidence references, deduplicated), `ASSUMPTION` (the most recent
response's own uncertainty reasons, verbatim), and `CONSTRAINT` (the
most recent response's own warning messages, verbatim) - and types it
deliberately does **not** populate today: `CURRENT_OBJECTIVE`,
`CURRENT_EQUIPMENT`, `CURRENT_ELECTRICAL_AREA`, `CURRENT_TASK`.
Identifying "what equipment is this conversation about" from free text
requires genuine language understanding - exactly the semantic
interpretation this milestone forbids. These four types exist in the
vocabulary (this milestone's own instruction lists them as content
Working Memory "may contain") so a future, genuinely structural source
(e.g. an explicit field a user or tool sets directly) can populate them
without a schema change - the same "reserved but honestly unpopulated"
precedent ADR-0015 established for `SUMMARY`/`TECHNICAL_EXPLANATION`/
`ASSUMPTIONS`/`NEXT_ACTIONS`.

### 5. "Build" and "rebuild" are the same computation

Because nothing is ever persisted, there is no existing `WorkingMemory`
state a "rebuild" could differentially update against. `rebuild_working_memory`
is a thin alias for `build_working_memory` - kept as a distinct name
only because the milestone names it as a separate capability with a
separate endpoint. `WorkingMemoryId` is itself deterministically
derived from `ConversationId` (`f"{conversation_id}:working-memory"`),
never caller-supplied or randomly generated, so "build" and "rebuild"
of the same conversation always agree on identity too.

### 6. EngineeringResponses are gathered from both inputs, not passed as a third parameter

Although this milestone frames "EngineeringResponses" as a conceptual
input alongside `Conversation` and `EngineeringSession`, the builder
takes only these two as parameters. Responses are gathered from both:
`EngineeringSession.engineering_responses` (the session's own directly
appended history) and every turn's own `engineering_responses` within
the supplied `Conversation`, deduplicated and ordered by each
response's own `metadata.assembled_at`. A separate, explicit third
parameter would be a redundant, potentially-inconsistent second source
of the same data the other two inputs already carry.

## Consequences

**Easier:**

- A future assistant/tool-execution capability has one small, already-
  bounded, already-structured object to read before reasoning, instead
  of re-scanning an entire conversation and re-deriving the same
  structural facts on every turn.
- Nothing about Working Memory can ever silently disagree with its own
  source - there is no cached, stale copy to reconcile, because nothing
  is ever cached across requests.
- Milestone 22 (Engineering Intent Detection) and beyond can extend
  `WorkingMemoryEntryType`'s reserved types once a genuinely structural
  signal exists for them, without redesigning the aggregate.

**Harder / deferred:**

- No long-term memory, user preferences, or vector memory exist -
  Working Memory is entirely session/conversation-scoped and structural,
  never a semantic index over history. That is explicit future work
  this milestone does not attempt.
- No persistence - a `WorkingMemory`'s lifetime is exactly one
  client's own request/response chain, the same posture every prior
  Milestone 19-20 bounded context takes.
- `CURRENT_OBJECTIVE`/`CURRENT_EQUIPMENT`/`CURRENT_ELECTRICAL_AREA`/
  `CURRENT_TASK` remain permanently unpopulated until a genuinely
  structural source for them exists - not solved speculatively here.

## Rejected Alternatives

- **Maintain Working Memory as LLM-updated running state** (the shape
  most consumer AI products use). Rejected outright by this milestone's
  own framing and on the merits: an LLM-writable memory is an
  unreviewed, self-asserted fact channel with no structural
  trace - exactly the risk ADR-0006 already closed off for engineering
  knowledge generally.
- **Persist Working Memory so it survives across requests.** Rejected:
  explicitly out of scope, and directly contrary to "it can always be
  rebuilt from deterministic inputs" - persisting a derived view
  invites it to drift from the source it was derived from.
- **Summarize recent messages/responses into free text using an LLM.**
  Rejected: this is precisely the "semantic summarization" this
  milestone's own non-goals exclude - every entry here is either a
  verbatim copy of existing structured/textual data or a small,
  deterministic structural label, never a generated summary.
- **Pass EngineeringResponses as a third, independent builder
  parameter** (as the milestone's own framing literally suggests).
  Rejected on the merits: both `Conversation` and `EngineeringSession`
  already carry every `EngineeringResponse` this builder needs; a third
  parameter would be redundant data entry that could disagree with what
  the other two inputs already say.
- **Randomly generate `WorkingMemoryId` per build.** Rejected: it would
  break the stated guarantee that build and rebuild of the same
  conversation agree on identity, for no benefit - deterministically
  deriving it from `ConversationId` costs nothing and is strictly more
  useful.
