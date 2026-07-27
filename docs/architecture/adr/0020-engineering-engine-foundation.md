# ADR-0020: Engineering Engine Foundation

## Status

Accepted.

## Context

By Milestone 22 (ADR-0019), an explicit engineering request is
deterministically classified into an `EngineeringIntent`. Every
component needed to *answer* a knowledge question already exists -
Structured Retrieval, Context Builder, Prompt Builder, the
provider-neutral LLM Runtime, Engineering Response - but nothing
coordinates them. A caller must currently chain six endpoints by hand,
and there is no artifact recording *what was planned*, *what ran*, or
*why it stopped*.

Milestone 23A introduces that coordination. It implements exactly one
workflow (`KNOWLEDGE_QUERY`) to prove the architecture end to end
before Milestone 23B expands the catalogue.

## Decision

### 1. The Engineering Engine is an application coordinator, not a knowledge bounded context

It coordinates deterministic workflow *structure*: selection, planning,
execution, and result assembly. It is **not** an autonomous agent, an
LLM brain, a reasoning engine, a chatbot, or a multi-agent
orchestrator - and this vocabulary is used consistently in every
docstring and document. The LLM Runtime is one execution dependency
inside one workflow step, nothing more.

The split follows the repository's existing domain/application
separation:

- `app/domain/engineering_engine/**` - immutable planning and
  execution-result models, the declarative workflow definition, the
  planner, and structural validators. It imports no router, schema,
  FastAPI, persistence adapter, provider SDK, or application service,
  and reaches into exactly two other domain contexts
  (`engineering_intent` for the type it selects on,
  `engineering_response` for the result it carries).
- `app/services/engineering_engine/**` - the registries, the typed
  execution context, the step handlers that adapt to existing services,
  the executor, the engine service, and the composition root.

The entire engine is deliberately *not* one domain service.

### 2. Planning and execution are separate operations

`select_workflow`, `build_plan`, `validate_plan`, and `execute_plan`
are independently callable and independently tested. A caller can build
and inspect a plan without running anything - and the tests prove it
(`test_build_plan_is_independently_callable_without_executing` asserts
the graph repository was never touched). Nothing is constructed and
executed invisibly inside one opaque function.

### 3. Plans are explicit, immutable, and deterministically identified

```
WorkflowPlanId = project_id:conversation_id:turn_id
                 :engineering_intent_id:workflow_id:workflow_version
WorkflowStepId = {plan_id}#{ordinal}:{step_type}
ExecutionId    = exec:{plan_id}
```

No random UUIDs anywhere. `planned_at` comes from the request's own
caller-supplied `executed_at`, never the wall clock. Identical inputs
under the same registry and definition versions produce a byte-for-byte
identical plan. Changing the workflow version deliberately changes the
plan identity, so plans from different definitions are never conflated.

### 4. Workflow registration replaces core intent branching

The engine core contains no `if intent is KNOWLEDGE_QUERY ... elif
intent is DOCUMENT_LOOKUP`. `WorkflowRegistry` owns the one
`EngineeringIntentType -> WorkflowDefinition` map; the core asks it to
resolve a workflow and gets either a definition or a typed
`UNSUPPORTED_INTENT` failure. This is enforced by an architecture test
that parses the actual AST for comparisons and `match` statements
against `EngineeringIntentType` members in the core files - not by
grepping for the word "if".

**This is what lets Milestone 23B add workflows without changing the
engine core**: a new workflow is a new `WorkflowDefinition` plus its
handlers, registered in `composition.py`. `engineering_engine_service.py`
does not even import concrete workflow definitions - also enforced by
test.

### 5. Only KNOWLEDGE_QUERY is supported, and unsupported means nothing runs

All nine other intent types return `status=UNSUPPORTED` with a typed
failure. No retrieval, no context, no prompt, no runtime invocation -
verified by asserting the fake graph repository recorded zero calls.
There is deliberately **no fallback workflow and no "just ask the LLM"
path**: silently answering a drawing request through the knowledge
workflow would produce a confidently wrong result, which this codebase
has rejected since ADR-0006.

### 6. The engine knows no provider details

The only LLM entry point in the whole engine is the existing
provider-neutral `invoke_llm`. No provider SDK, HTTP client, or model
name appears anywhere in engine code - enforced by architecture test.
The runtime already normalizes every provider failure into a typed
`LLMProviderError`; the engine maps that to `RUNTIME_FAILURE` and never
lets a raw provider exception into its domain.

### 7. Aggregate updates are explicit proposals, never silent mutations

**Policy B was chosen**: the engine returns explicit, immutable
`ConversationUpdateProposal` and `SessionUpdateProposal` objects, each
carrying `disposition = PREPARED`. It never mutates `Conversation` or
`EngineeringSession`.

This is why the execution request carries *identifiers* rather than
those aggregates: preparing a proposal needs only the target ids, so
requiring whole aggregates would be duplicated information the engine
does not use. A higher application service that wants the updates
applied does so itself, via the existing
`conversation_service.attach_response` and
`engineering_session_service.append_response`.

`AggregateUpdateDisposition.APPLIED` exists in the enum so a future
milestone that genuinely applies updates can say so honestly - and the
validator actively rejects any Milestone 23A result claiming it, so the
execution result can never imply an update occurred when only a
proposal was returned.

### 8. Planning determinism is not runtime determinism

Given the same request, intent, registry version, and definition
version, the **plan** is always identical - same plan id, same step
ids, same order. The **runtime output** is not: a language model is not
a deterministic function, and this document does not claim otherwise.
Tests use the existing `FakeLLMProviderAdapter` and mocked SDK clients
precisely so the parts that *are* deterministic can be asserted
exactly, and the part that is not is held constant rather than
pretended away.

### 9. Failures and execution timelines are first-class

Fourteen typed, stage-specific failure codes; a `WorkflowStepResult`
per step; an append-only timeline of `EXECUTION_CREATED`,
`WORKFLOW_SELECTED`, `PLAN_BUILT`, `PLAN_VALIDATED`, `STEP_STARTED`,
`STEP_COMPLETED`, `STEP_FAILED`, and `EXECUTION_COMPLETED`/`FAILED`.
Execution **stops at the first failure** and every remaining step is
recorded as `SKIPPED`, never executed - so "how far did this get, and
why did it stop" is answerable from the result alone. The timeline is
domain execution evidence, not production tracing; no telemetry
infrastructure is introduced.

## Consequences

**Easier:**

- Milestone 23B adds workflows by registration alone.
- Every execution is auditable end to end without correlating logs.
- Existing components are reused rather than re-implemented: the engine
  contains no retrieval, prompt, or response-building logic of its own.

**Harder / deferred:**

- **No persistence and no transaction.** Nothing is stored: not the
  response, not the aggregate updates, not the execution record. The
  *intended future* transaction boundary would atomically persist the
  `EngineeringResponse`, the Conversation update, the
  EngineeringSession update, and (if it is ever persisted) the
  execution record together. **That transaction does not exist today**
  - this milestone neither implements it nor implies it does.
- No retries, no parallel steps, no cancellation, no background
  execution - all explicit non-goals.
- The engine's retrieval configuration is caller-supplied. It does not
  derive retrieval criteria from the request text; that would be
  semantic interpretation, which ADR-0019 deliberately excluded.

## Rejected Alternatives

- **A single `answer_knowledge_query()` service function.** Rejected:
  it would work for one workflow and collapse at two, offering no plan
  to inspect, no per-step failure attribution, and no extension point.
- **Intent branching in the engine core.** Rejected: it makes every new
  workflow a core edit, exactly what "adding a workflow in 23B must not
  require modifying the engine core" forbids.
- **Have the engine apply Conversation and Session updates directly.**
  Rejected: it would require the engine to accept and return whole
  aggregates, and would perform a multi-aggregate mutation with no
  transaction to make it atomic - a silent partial-update risk.
  Returning proposals is honest about what actually happened.
- **An untyped `dict` execution context.** Rejected: it would make
  "which step produced what" unverifiable and turn a missing artifact
  into an `AttributeError` deep inside a handler instead of a
  deterministic `MISSING_REQUIRED_ARTIFACT` failure.
- **A separate `EXECUTE_GRAPH_QUERY` step.** Rejected: Graph Query is
  already an internal dependency of Structured Retrieval, so a separate
  step would duplicate it artificially and misrepresent the real
  pipeline.
- **Returning HTTP 4xx for an unsupported intent.** Rejected: the
  request was well-formed and the engine answered it correctly. A 200
  carrying `status="unsupported"` keeps `422` meaning exactly one thing
  across this codebase - a structurally invalid request - matching how
  ADR-0014 already reports expected provider failures as data.
