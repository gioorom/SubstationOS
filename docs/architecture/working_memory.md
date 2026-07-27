# Working Memory

**Status:** As-built reference, Milestone 21 (Working Memory
Foundation). Describes the `working_memory` bounded context as
implemented - for the decision record (why Working Memory is neither
Conversation nor Knowledge, why it is deterministic, why LLMs never
edit it), see [ADR-0018](adr/0018-working-memory-foundation.md). For
where this context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[conversation.md](conversation.md).

## What Working Memory is - and is not

Working Memory is the temporary engineering context required to
continue reasoning during a session. It is **not** conversation
history (`Conversation`, Milestone 20, is the permanent record of what
was actually said and done) and **not** project knowledge (the
Project Knowledge Graph is reviewed, versioned, permanent engineering
fact). It can always be rebuilt from deterministic inputs, and it is
never edited by an LLM.

## Pipeline

```
Conversation + EngineeringSession
        |
   Composition          (working_memory_composition.py - pure, no I/O,
        |                no AI, no summarization, no semantic
        |                interpretation)
        |
   Statistics            (working_memory_statistics.py)
        |
   Metadata/Versioning   (working_memory_metadata.py)
        |
   Validation            (working_memory_validation.py)
   WorkingMemoryBuilderResult
```

`app/services/working_memory_service.py` is thin orchestration - like
Conversation and Engineering Session's own services, Working Memory's
inputs are already domain types, so no application-layer translation
seam is needed.

## What Working Memory never stores

Per this milestone's own instruction: the entire conversation, canonical
project knowledge, tool outputs, or an LLM's own hidden reasoning.
Everything on a `WorkingMemory` must be derivable from its own inputs -
`Conversation` and `EngineeringSession` - alone.

## Domain model

`app/domain/working_memory/working_memory_models.py`: `WorkingMemory`/
`WorkingMemoryId` (deterministically derived from `ConversationId`,
never caller-supplied)/`WorkingMemoryMetadata`/`WorkingMemoryVersion`/
`WorkingMemoryPolicy`/`WorkingMemoryStatistics`/
`WorkingMemoryValidationResult`/`WorkingMemoryBuilderResult`;
`WorkingMemoryEntry`/`WorkingMemoryEntryType`/`WorkingMemoryPriority`/
`WorkingMemoryLifetime`/`WorkingMemorySource`. All frozen, slotted.

## Entry types: populated today vs. reserved

| Entry type | Populated today? | Derived from |
|---|---|---|
| `OPEN_QUESTION` | Yes | The last `USER` message in a still-`STARTED` turn, verbatim |
| `RECENT_ENGINEERING_RESPONSE` | Yes | Recent `EngineeringResponse`s (by `metadata.assembled_at`), held by reference |
| `ACTIVE_REFERENCE` | Yes | Each recent response's own evidence references, deduplicated |
| `ASSUMPTION` | Yes | The most recent response's own uncertainty reasons, verbatim |
| `CONSTRAINT` | Yes | The most recent response's own warning messages, verbatim |
| `CURRENT_OBJECTIVE` | No (reserved) | No structural signal exists today |
| `CURRENT_EQUIPMENT` | No (reserved) | No structural signal exists today |
| `CURRENT_ELECTRICAL_AREA` | No (reserved) | No structural signal exists today |
| `CURRENT_TASK` | No (reserved) | No structural signal exists today |

**Why the reserved four are never populated:** identifying "what
equipment is this conversation about" from free text requires genuine
language understanding - exactly the semantic interpretation this
milestone forbids. They exist in the vocabulary so a future, genuinely
structural source can populate them without a schema change - the same
precedent ADR-0015 established for Engineering Response's own always-
empty `SUMMARY`/`TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`NEXT_ACTIONS`
sections.

## Dependency surface

`app/domain/working_memory/**` depends on exactly three other domain
contexts: `conversation` (its primary input), `engineering_session`
(its other primary input), and `engineering_response` (entries
reference `EngineeringResponse` objects directly, never copied).
Nothing else: no Prompt Builder, no Context Builder, no Structured
Retrieval, no Graph Query, no provider SDK, no `app.application.**` of
any kind, no LLM Invocation Runtime module. Enforced by
`tests/architecture/test_bounded_context_dependencies.py`'s
`test_working_memory_does_not_import_forbidden_modules`,
`test_working_memory_surface_has_no_ai_or_provider_dependency`, and
`test_working_memory_domain_never_imports_the_application_layer` - the
last with no exceptions anywhere, the same guarantee Engineering
Session's and Conversation's own equivalent tests establish.

## Builder

`working_memory_builder.py` (the milestone-named `WorkingMemoryBuilder`
class is a thin façade): `build_working_memory`,
`rebuild_working_memory`. **These are the same computation** -
`rebuild_working_memory` is a thin alias, kept as a distinct name only
because the milestone names it as a separate capability with a
separate endpoint; nothing is ever persisted, so there is no existing
state a "rebuild" could differentially update against.
`working_memory_composition.py`'s `compose_working_memory_entries`
does the actual entry derivation - see its own module docstring for the
full, explicit reasoning on what counts as "structural" versus
"semantic interpretation."

## Validation

`working_memory_validation.py`'s `validate_working_memory` (wrapped by
the milestone-named `WorkingMemoryValidator` class) checks entry
ordering (sequenced contiguously from zero), lifetime/priority
consistency with the fixed policy table for each entry's type, that
only `RECENT_ENGINEERING_RESPONSE` entries carry an
`engineering_response` reference, metadata completeness, version
consistency, and statistics consistency. **No semantic validation** -
never whether an entry's content is engineering-correct.

## Service

`app/services/working_memory_service.py`: `build`, `rebuild` - thin
orchestration, no translation seam needed, no persistence, no I/O.

## API

```
POST /projects/{project_id}/working-memory/build
POST /projects/{project_id}/working-memory/rebuild
```

Both accept `conversation`/`engineering_session` (exactly the objects a
prior `/conversation`/`/engineering-session` call returned) and return
the same `WorkingMemoryBuilderResultRead` shape. Pure deterministic
transformations - no AI invocation, no persistence. The path's
`project_id` is authoritative; a supplied conversation naming a
different project is rejected with `422`.

### Errors

Every `WorkingMemoryError` subtype (invalid project id, a project id
mismatch between the supplied conversation and session, a conversation
naming a different session than the supplied `EngineeringSession`) maps
to `422 Unprocessable Entity`.

## Determinism

Identical `(Conversation, EngineeringSession)` inputs, given the same
`now`, always produce an identical `WorkingMemory` - proven at the
domain level
(`tests/domain/test_working_memory_builder.py::test_rebuild_produces_an_identical_result_to_build`,
`::test_working_memory_id_is_deterministic_from_conversation_id`) and
at the API level
(`tests/api/test_working_memory_api.py::test_rebuild_matches_build`).
No mutable state, no persistence - every build is a pure recomputation.

## Performance

Building is O(n) in the number of turns/messages and gathered responses
- a small, constant number of linear passes over already-materialized
data, independent of graph size. See
[performance_baseline.md](performance_baseline.md) for the recorded
`working_memory_build` benchmark operation.

## What this milestone deliberately does not do

- No long-term memory, user preferences, or vector memory.
- No autonomous memory updates - the only way contents change is by
  rebuilding from a different `Conversation`/`EngineeringSession`.
- No semantic summarization - every entry is either verbatim or a
  small, deterministic structural label.
- No agents, no persistence, no frontend changes.

These are Milestone 22's (Engineering Intent Detection) and later EPIC
5 milestones' concern, not this one's.
