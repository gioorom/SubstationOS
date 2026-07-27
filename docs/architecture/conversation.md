# Conversation

**Status:** As-built reference, Milestone 20 (Conversation Foundation).
Describes the `conversation` bounded context as implemented - for the
decision record (why Turn, not Message, is the primary conversational
unit, why EngineeringResponse is referenced rather than copied, why
future tools belong to Turn), see
[ADR-0017](adr/0017-conversation-foundation.md). For where this context
sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[engineering_session.md](engineering_session.md).

## What Conversation is - and is not

`Conversation` models structured engineering dialogue. It is **not** a
chat log. A `Conversation` belongs to exactly one `EngineeringSession`
(referenced by `session_id`, never embedded) and owns an ordered
sequence of `ConversationTurn`s. **`ConversationTurn`, not
`ConversationMessage`, is the primary conversational unit** - future
tool execution, retrieval, agent execution, and assistant reasoning
will all occur inside a Turn. Messages never own Turns; the ownership
direction is strictly Conversation -> Turn -> Message, one way, never
reversed.

## Structure

```
Conversation
        |
   Ordered Turns
        |
   Ordered Messages
```

Every Turn belongs to exactly one Conversation
(`ConversationTurn.conversation_id`). Every Message belongs to exactly
one Turn (`ConversationMessage.turn_id`). Only one Turn may be
`STARTED` (open) at a time - `start_turn` raises
`TurnAlreadyInProgressError` otherwise.

## What a Turn owns

- User and assistant messages (`ConversationMessage`, ordered).
- `EngineeringResponse` references - held directly, by object identity,
  never copied or restated (see ADR-0017 SS2 for why this is safe here
  but was not safe for `LLMResponseEnvelope` in Engineering Response).
- Its own timeline events (a `ConversationTimeline` scoped to just this
  turn, alongside the conversation's own timeline recording the same
  events at the conversation level).
- Metadata (`sequence`, `started_at`, `completed_at`) and statistics
  (`message_count`, `engineering_response_count`, `turn_duration_seconds`).
- **Not yet:** tool executions, agent executions, retrieval executions
  - reserved for future milestones; `ConversationMessageRole.TOOL`/
  `.AGENT` exist in the enum today precisely so a future message never
  needs a role this vocabulary cannot already express.

## Domain model

`app/domain/conversation/conversation_models.py`: `Conversation`/
`ConversationId`/`ConversationStatus`/`ConversationMetadata`/
`ConversationVersion`/`ConversationPolicy`/`ConversationStatistics`/
`ConversationValidationResult`/`ConversationBuilderResult`;
`ConversationTurn`/`ConversationTurnId`/`ConversationTurnStatus`/
`ConversationTurnMetadata`/`ConversationTurnStatistics`/
`ConversationTurnValidationResult`; `ConversationMessage`/
`ConversationMessageId`/`ConversationMessageRole`/
`ConversationMessageContent`/`ConversationMessageMetadata`;
`ConversationTimeline`/`ConversationEvent`/`ConversationEventType`. All
frozen, slotted dataclasses.

## Dependency surface

`app/domain/conversation/**` depends on exactly two other domain
contexts: `app.domain.engineering_session` (for `EngineeringSessionId`,
to reference the owning session) and `app.domain.engineering_response`
(for `EngineeringResponse`, held directly by Turn). Nothing else: no
Prompt Builder, no Context Builder, no Structured Retrieval, no Graph
Query, no provider SDK, no `app.application.**` of any kind, no LLM
Invocation Runtime module. Enforced by
`tests/architecture/test_bounded_context_dependencies.py`'s
`test_conversation_does_not_import_forbidden_modules`,
`test_conversation_surface_has_no_ai_or_provider_dependency`, and
`test_conversation_domain_never_imports_the_application_layer` - the
last with no exceptions anywhere, the same guarantee Engineering
Session's own equivalent test establishes.

## State machines

`conversation_state_machine.py`:

```
Conversation:  ACTIVE -> COMPLETED -> ARCHIVED  (ARCHIVED terminal)
Turn:          STARTED -> COMPLETED             (COMPLETED terminal)
```

`MUTABLE_CONVERSATION_STATUSES = {ACTIVE}`;
`MUTABLE_TURN_STATUSES = {STARTED}`. An invalid transition raises
`InvalidConversationTransitionError`/`InvalidTurnTransitionError`; a
mutation attempted on a non-mutable conversation raises
`ConversationNotMutableError`; one attempted with no open turn raises
`NoActiveTurnError`.

## Message identity

`ConversationId`/`ConversationTurnId` are always caller-supplied (the
router generates a fresh `uuid.uuid4()` when creating a conversation or
starting a turn). `ConversationMessageId` is the one exception: it is
**deterministically derived** by the builder as
`f"{turn_id.value}:{sequence}"`, never caller-supplied - a message
always belongs to an already-identified turn and occupies exactly one
position within it, so nothing about its identity needs external
uniqueness a caller would have to invent.

## Timeline

`ConversationEventType`: `CONVERSATION_CREATED`, `TURN_STARTED`,
`TURN_COMPLETED`, `MESSAGE_ADDED`, `ENGINEERING_RESPONSE_ATTACHED`,
`STATUS_CHANGED`. Append-only; both the `Conversation` and each of its
`ConversationTurn`s carry their own `ConversationTimeline` - the
conversation's records every event across the whole conversation, a
turn's records only the events that occurred within it.

## Validation

`conversation_validation.py`'s `validate_conversation`/`validate_turn`
(wrapped by the milestone-named `ConversationValidator` class) check
ordering (turn sequence, message sequence, timeline sequence),
ownership (every turn belongs to its conversation, every message
belongs to its turn), timeline consistency (starts with the right
event type, strictly sequenced, chronological), metadata completeness,
version consistency, and statistics consistency. **No semantic
validation** - never whether a message's content makes engineering
sense.

## Builders

`conversation_builder.py` (the milestone-named `ConversationBuilder`
class is a thin façade): `create_conversation`, `start_turn`,
`append_message`, `attach_engineering_response`, `complete_turn`,
`change_conversation_status`. Each returns a `ConversationBuilderResult`
- the *whole* updated `Conversation`, never a standalone Turn or
Message object, the same convention `EngineeringSession` already
established.

## Service

`app/services/conversation_service.py`: `create`, `start_new_turn`,
`add_message`, `attach_response`, `finish_turn`, `change_status` - thin
orchestration, no translation seam needed (Conversation's inputs are
already domain types), no persistence, no I/O.

## API

```
POST /projects/{project_id}/conversation
POST /projects/{project_id}/conversation/start-turn
POST /projects/{project_id}/conversation/add-message
POST /projects/{project_id}/conversation/attach-response
POST /projects/{project_id}/conversation/complete-turn
POST /projects/{project_id}/conversation/change-status
```

**No persistence** - per this milestone's own instruction, each
endpoint (except creation) accepts the current `ConversationRead` as
part of its own request body and returns the updated one.
`conversation_id`/`turn_id` generation (`uuid.uuid4()`) happens only at
the router. `add-message`/`attach-response`/`complete-turn` never
accept a `turn_id` - they always operate on whichever turn is currently
open, since only one may ever be open at a time. The path's
`project_id` is authoritative; a supplied conversation naming a
different project is rejected with `422`.

### Errors

Every `ConversationError` subtype (invalid project id, blank
identifiers, a project id mismatch, an invalid state transition, a
second turn started while one is open, a mutation with no open turn)
maps to `422 Unprocessable Entity`.

## Determinism

Identical inputs (the same identifiers, the same sequence of builder
operations, the same `now` at each step) always produce an identical
`Conversation`. All timestamps are caller-supplied; message ids are
derived, never random. Proven at the domain level
(`tests/domain/test_conversation_builder.py::test_identical_inputs_produce_an_identical_conversation`)
and, since the router itself is impure, at the API level by comparing
timeline *structure* across repeated calls rather than exact timestamps
(`tests/api/test_conversation_api.py::test_determinism_across_repeated_calls`).

## Performance

Every builder operation is O(1) in the number of already-materialized
turns/messages (appending one item to an existing tuple) - independent
of graph size, since Conversation performs no database query and no AI
invocation of its own. See
[performance_baseline.md](performance_baseline.md) for the recorded
`conversation_turn_lifecycle` benchmark operation.

## What this milestone deliberately does not do

- No memory, retrieval execution, assistant reasoning, or intent
  detection.
- No tool execution or agents - reserved for future milestones (see
  `ConversationMessageRole.TOOL`/`.AGENT`, reserved but unused).
- No persistence - a conversation's lifetime today is exactly one
  client's own request/response chain.
- No frontend changes.

These are Milestone 21's (Conversation Memory Foundation) and later
EPIC 5 milestones' concern, not this one's.
