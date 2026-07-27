# Engineering Session

**Status:** As-built reference, Milestone 19 (Engineering Session
Foundation). Describes the `engineering_session` bounded context as
implemented - for the decision record (why Session precedes
Conversation, why Conversation will not be the aggregate root, why
EngineeringResponse belongs to Session), see
[ADR-0016](adr/0016-engineering-session-foundation.md). For where this
context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[engineering_response.md](engineering_response.md).

## What Engineering Session is - and is not

`EngineeringSession` is the root aggregate representing one complete
engineering work session on a project. It is **not** a chat. Future
conversations, tools, assistants, and agents will all execute inside an
`EngineeringSession` - none of that exists yet. Today a session owns:
project identity, creation/update timestamps, a session identifier,
session state, the ordered `EngineeringResponse` objects generated
during the session, session configuration, an append-only timeline of
events, statistics, and version metadata. It does **not** own
conversation turns, chat history, memory, tools, or agents (Milestone
20 and later).

## Pipeline

```
(create)                 build_initial_session
(append a response)      append_engineering_response
(change state)           change_session_state
(update configuration)   update_session_configuration
        |
   each returns a new EngineeringSessionBuilderResult -
   never mutates its input
```

Every operation is a pure function of its inputs: the current
`EngineeringSession` (except for creation), plus caller-supplied data,
plus a caller-supplied `now`. No AI usage, no I/O, no persistence -
`app/domain/engineering_session/**` performs none of these, and
`app/services/engineering_session_service.py` is a thin orchestration
layer with nothing to translate (unlike Engineering Response's own
service, Engineering Session's input - an already-built
`EngineeringResponse`, itself a domain type - needs no application-layer
translation seam at all).

## Domain model

`app/domain/engineering_session/engineering_session_models.py`:
`EngineeringSession`, `EngineeringSessionId` (always caller-supplied,
never generated inside the domain layer), `EngineeringSessionStatus`,
`EngineeringSessionState` (status + when it last changed - distinct
from the bare status enum), `EngineeringSessionEvent`/
`EngineeringSessionEventType`/`EngineeringSessionTimeline`,
`EngineeringSessionPolicy`/`EngineeringSessionConfiguration` (title/
notes - the only caller-configurable fields this milestone defines),
`EngineeringSessionMetadata`/`EngineeringSessionVersion`,
`EngineeringSessionStatistics`, `EngineeringSessionValidationResult`,
`EngineeringSessionBuilderResult`. All frozen, slotted dataclasses.

## Dependency surface

`app/domain/engineering_session/**` depends on exactly one other
domain context - `app.domain.engineering_response` (to own
`EngineeringResponse` objects directly). Nothing else: no Prompt
Builder, no Context Builder, no Structured Retrieval, no Graph Query,
no provider SDK, no `app.application.**` of any kind, no LLM Invocation
Runtime module. "Project identity" is a plain `project_id: int`, the
same convention every context in this pipeline already uses - no import
of `app.domain.project` exists or is needed. Enforced by
`tests/architecture/test_bounded_context_dependencies.py`'s
`test_engineering_session_does_not_import_forbidden_modules`,
`test_engineering_session_surface_has_no_ai_or_provider_dependency`,
and `test_engineering_session_domain_never_imports_the_application_layer`
- the last of which has no exceptions anywhere, unlike Engineering
Response's own equivalent test (which exempts its own translation
seam), because Engineering Session has no application-layer input to
translate in the first place.

## State machine

`engineering_session_state_machine.py`, the same explicit
transition-table-plus-membership-check convention
`app.domain.project.project_lifecycle` established for
`ProjectLifecycleState`:

```
CREATED   -> ACTIVE
ACTIVE    -> {PAUSED, COMPLETED}
PAUSED    -> {ACTIVE, COMPLETED, ARCHIVED}
COMPLETED -> ARCHIVED
ARCHIVED  -> (terminal - no transition leaves it)
```

`MUTABLE_STATUSES = {CREATED, ACTIVE, PAUSED}` - only these accept new
`EngineeringResponse`s or configuration updates;
`COMPLETED`/`ARCHIVED` are read-only, raising `SessionNotMutableError`.
An invalid transition raises `InvalidSessionTransitionError`.

## Timeline

`EngineeringSessionEventType`: `SESSION_CREATED`,
`ENGINEERING_RESPONSE_ADDED`, `STATE_CHANGED`, `CONFIGURATION_UPDATED`.
Every builder operation appends exactly one new, immutable event;
`sequence` is strictly increasing from zero, `occurred_at` is always
caller-supplied. The timeline is never reordered or rewritten - a
complete, replayable record of what happened and when.

## Engineering Response ownership

`EngineeringSession.engineering_responses` is an ordered tuple,
appended to (never mutated in place) by `append_engineering_response`.
Appending validates that the response's own `project_id` matches the
session's (`ProjectIdMismatchError` otherwise) and that the session is
currently mutable (`SessionNotMutableError` otherwise). Ordering and
provenance are preserved exactly as Engineering Response produced them.

## Statistics

`EngineeringSessionStatistics`: `response_count`,
`timeline_event_count`, `session_duration_seconds` (computed from
`metadata.created_at`/`updated_at`, both caller-supplied), and
`last_activity_at`. Deliberately no token accounting.

## Validation

`engineering_session_validation.py`'s `validate_session` (wrapped by
the milestone-named `EngineeringSessionValidator` class) checks: the
timeline begins with `SESSION_CREATED` at sequence zero and is
strictly, chronologically ordered; the current state's `changed_at` is
consistent with the most recent `STATE_CHANGED` event; every owned
`EngineeringResponse` belongs to the session's own project; metadata is
complete; version fields are consistent with metadata; and every
statistic is internally consistent with the assembled
responses/timeline/metadata. Never a gate - building always produces a
structurally valid session by construction.

## Builder

`engineering_session_builder.py` (the milestone-named
`EngineeringSessionBuilder` class is a thin façade over these
functions): `build_initial_session`, `append_engineering_response`,
`change_session_state`, `update_session_configuration`. Each returns an
`EngineeringSessionBuilderResult` (the resulting session plus its
self-validation).

## Service

`app/services/engineering_session_service.py`: `create_session`,
`append_response`, `change_state`, `update_configuration` - thin
orchestration over the domain builder, no persistence, no I/O.

## API

```
POST /projects/{project_id}/engineering-session
POST /projects/{project_id}/engineering-session/append-response
POST /projects/{project_id}/engineering-session/change-state
POST /projects/{project_id}/engineering-session/update-configuration
```

**No persistence exists** - per this milestone's own instruction, each
endpoint accepts the current `EngineeringSessionRead` as part of its own
request body (except creation, which starts fresh) and returns the
updated one, the same "each stage's endpoint takes the prior stage's
output as input" convention every governed router in this pipeline
follows. `session_id` generation (`uuid.uuid4()`) happens only at the
router - the one impure edge - never inside the domain layer. The
path's `project_id` is authoritative; a supplied session naming a
different project is rejected with `422`, the same convention every
governed router in this pipeline follows.

### Errors

Every `EngineeringSessionError` subtype (invalid project id, blank
session id, a project id mismatch, an invalid state transition, a
mutation attempted on a non-mutable session) maps to
`422 Unprocessable Entity`.

## Determinism

Identical inputs (the same `session_id`, the same sequence of builder
operations, the same `now` at each step) always produce an identical
`EngineeringSession`. All timestamps are caller-supplied; no session id
is ever generated inside the domain layer. Proven at the domain level
(`tests/domain/test_engineering_session_builder.py::test_identical_inputs_produce_an_identical_initial_session`)
and, since the router itself is impure (`now=datetime.utcnow()` per
call, the same discipline every governed router in this pipeline
follows), at the API level by comparing timeline *structure*
(event types and sequence numbers) across repeated calls rather than
exact timestamps
(`tests/api/test_engineering_session_api.py::test_determinism_across_repeated_state_changes`).

## Performance

Every builder operation is O(1) in the number of already-materialized
responses/events (appending one item to an existing tuple) -
independent of graph size, since Engineering Session performs no
database query and no AI invocation of its own. See
[performance_baseline.md](performance_baseline.md) for the recorded
`engineering_session_lifecycle` benchmark operation.

## What this milestone deliberately does not do

- No conversation, chat history, or memory.
- No tool execution or agents.
- No persistence beyond the designed domain model - a session's
  lifetime today is exactly one client's own request/response chain.
- No authentication or per-user session ownership - `created_by` is an
  optional, unenforced field.
- No frontend changes.

These are Milestone 20's (Conversation Foundation) and later EPIC 5
milestones' concern, not this one's.
