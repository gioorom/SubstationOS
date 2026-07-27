# ADR-0016: Engineering Session Foundation

## Status

Accepted.

## Context

By Milestone 18 (Engineering Response Foundation, ADR-0015), an
`LLMResponseEnvelope` is normalized into `EngineeringResponse` - the
canonical, domain-owned representation of one AI answer. Nothing yet
exists that represents the *work session* an engineer is actually
having on a project: a sequence of engineering responses, produced over
time, with a lifecycle of its own (created, worked on, paused, finished,
archived) and a deterministic record of what happened and when.

The obvious next step would seem to be "build the conversation" -
turns, messages, chat history. This milestone deliberately does not do
that. It introduces `EngineeringSession` first: the root aggregate that
owns project identity, session state, the ordered history of
`EngineeringResponse` objects produced during the session, an
append-only timeline, statistics, and version metadata. Conversation,
chat history, memory, tools, and agents are explicitly out of scope -
they arrive in Milestone 20 (Conversation Foundation) and beyond, and
they will execute *inside* an `EngineeringSession`, never stand as their
own root.

## Decision

### 1. Session precedes Conversation, and Conversation will not be the aggregate root

A conversation is one *kind* of activity that can happen during an
engineering work session - but not the only one. A future capability
that runs a structured retrieval, builds a report, or invokes a tool
without any chat turn at all still happens *during* a session, and
still produces `EngineeringResponse`s that belong to that session. If
`Conversation` were the root aggregate, every one of those non-chat
capabilities would have to be modeled as a degenerate, single-message
conversation to fit - an awkward inversion. Making `EngineeringSession`
the root, with `Conversation` arriving later as one of the things a
session *owns* (see the target architecture in this milestone's own
brief: `EngineeringSession → Conversation (future)`), keeps the
aggregate boundary aligned with what is actually permanent - the work
session - rather than with one particular interaction style.

### 2. EngineeringResponse belongs to Session, not the other way around

`EngineeringSession.engineering_responses` is an ordered tuple of
`EngineeringResponse` objects, preserving both ordering and
provenance, never modified in place. Engineering Response itself
(ADR-0015) has no concept of "the session it was produced in" - it is
a self-contained, traceable artifact producible independent of any
session context. Session is the layer that accumulates them into a
history; Response is not, and should not become, aware of its own
container. This mirrors the same "downstream owns a reference to the
upstream artifact, upstream never knows about downstream" direction
this entire pipeline already uses (Context Builder owns
`KnowledgeCandidate`s without Structured Retrieval knowing about
Context Builder; Prompt Builder owns a `ContextPackage` without Context
Builder knowing about Prompt Builder).

### 3. Engineering Session is a genuine domain bounded context with almost no dependencies

`app/domain/engineering_session/**` depends on exactly one other
domain context - `engineering_response`, to own `EngineeringResponse`
objects directly - and nothing else. No Prompt Builder, no Context
Builder, no Structured Retrieval, no Graph Query, no provider SDK, no
LLM Invocation Runtime module, and critically, no `app.application.**`
of any kind: unlike Engineering Response, Engineering Session has no
application-layer input to translate at all, so it needs no exception
anywhere, not even in its own service module (verified by a dedicated
architecture test, mirroring Engineering Response's own but with zero
carve-outs). "Project identity" is carried as a plain `project_id: int`
- the same convention every context in this pipeline already uses -
never a dependency on `app.domain.project` itself.

### 4. Session state is an explicit, validated state machine

`EngineeringSessionStatus` (`CREATED`/`ACTIVE`/`PAUSED`/`COMPLETED`/
`ARCHIVED`) follows the same explicit transition-table-plus-membership-
check convention `app.domain.project.project_lifecycle` already
established for `ProjectLifecycleState`: `CREATED → ACTIVE`,
`ACTIVE → {PAUSED, COMPLETED}`, `PAUSED → {ACTIVE, COMPLETED,
ARCHIVED}`, `COMPLETED → ARCHIVED`, and `ARCHIVED` is terminal.
`COMPLETED`/`ARCHIVED` are read-only, the same "terminal states are
immutable" discipline `MUTABLE_STATES` already established for
Project.

### 5. The timeline is an append-only, deterministic ledger

Every builder operation (`build_initial_session`,
`append_engineering_response`, `change_session_state`,
`update_session_configuration`) appends exactly one new, immutable
`EngineeringSessionEvent` - never rewrites history, never reorders
existing entries. `sequence` is strictly increasing from zero;
`occurred_at` is always caller-supplied. This gives every session a
complete, replayable record of what happened and when, the same
auditability principle ADR-0014 established for invocation attempts
and ADR-0015 for evidence preservation.

### 6. No persistence, no session-id generation inside the domain

Per this milestone's own instruction, no database, no in-memory store,
and no server-side session table exists. Every API endpoint accepts the
current `EngineeringSession` as part of its own request body and
returns the updated one - the same "each stage's endpoint takes the
prior stage's output as input" convention every governed router in
this pipeline already follows (`/context-builder/build` takes a
`KnowledgeCandidateCollection`; `/prompt-builder/build` takes a
`ContextPackage`; here, `/engineering-session/append-response` takes an
`EngineeringSession` and an `EngineeringResponse`). `session_id`
generation (`uuid.uuid4()`) happens only at the composition root (the
router), never inside the domain layer, keeping every builder operation
itself pure and deterministic given the same `session_id`/`now`.

## Consequences

**Easier:**

- Milestone 20 (Conversation Foundation) can introduce `Conversation`/
  `ConversationTurn`/`ConversationMessage` as things an
  `EngineeringSession` owns, without redesigning the aggregate root or
  migrating any already-shipped session data (none exists to migrate -
  no persistence yet).
- Every session's full history (state transitions, responses added,
  configuration changes) is inspectable from its own timeline alone, no
  external audit log required to answer "what happened in this
  session."
- Engineering Session's dependency surface is the smallest of any
  bounded context in this pipeline so far (one domain dependency, zero
  I/O, zero application-layer coupling) - the architecture test
  enforcing it has no exceptions to reason about.

**Harder / deferred:**

- No persistence exists yet, so a session's lifetime today is exactly
  one client's own request/response chain - nothing survives between
  API calls unless the caller resends the full session object each
  time. A real, multi-request session store is explicit future work,
  not solved speculatively here (Milestone 19's own "No persistence
  beyond the designed domain model" instruction).
- `update-configuration` is not literally named in this milestone's own
  "equivalent to" endpoint list, but was added because
  `CONFIGURATION_UPDATED` is an explicitly required timeline event type
  that would otherwise never be exercised by any real caller - a small,
  documented, in-scope extension, not scope creep.
- No authentication or per-user session ownership exists - `created_by`
  is an optional, unenforced field, the same posture every other
  bounded context in this pipeline takes toward identity today.

## Rejected Alternatives

- **Make `Conversation` the aggregate root, with `EngineeringSession`
  folded into it as metadata.** Rejected: a conversation is one kind of
  session activity, not the container for everything a session can
  produce - see Decision §1. Would also directly contradict this
  milestone's own explicit framing ("Engineering Session is NOT a
  chat").
- **Let `EngineeringResponse` carry a `session_id` field pointing back
  to its owning session.** Rejected: this would make Engineering
  Response aware of a concept (sessions) that did not exist when it was
  designed (Milestone 18), coupling an already-shipped, self-contained
  artifact to a downstream context - the same "upstream never knows
  about downstream" direction this pipeline enforces everywhere else.
- **Generate `session_id` inside the domain builder (e.g.
  `uuid.uuid4()` at the top of `build_initial_session`).** Rejected:
  would make the domain layer's own core operation non-deterministic
  and impure, breaking the "identical inputs produce identical
  sessions" guarantee this milestone explicitly requires. Identifier
  generation stays at the composition root, exactly where
  `request_correlation_id` generation already lives for the LLM
  Invocation Runtime.
- **Persist sessions in this milestone**, so a session survives across
  requests without the caller resending it. Rejected: explicitly out of
  scope ("No persistence beyond the designed domain model"), and no
  concrete requirement demonstrated a need for it yet - the same
  Change Discipline every prior ADR in this pipeline has followed.
