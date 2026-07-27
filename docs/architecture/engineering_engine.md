# Engineering Engine

**Status:** As-built reference, Milestone 23A (Engineering Engine
Foundation). For the decision record (why the engine is an application
coordinator, why planning and execution are separate, why registration
replaces intent branching, why aggregate updates are explicit, why
planning determinism differs from runtime nondeterminism), see
[ADR-0020](adr/0020-engineering-engine-foundation.md). For where this
sits in the pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

> **Only `KNOWLEDGE_QUERY` is implemented in Milestone 23A.** Every
> other intent type returns an explicit `UNSUPPORTED` result and runs
> nothing at all.

## What the engine is - and is not

The Engineering Engine is the **application-level coordination
mechanism** that selects, plans and executes engineering workflows. It
is **not** an autonomous agent, an LLM brain, a reasoning engine, a
chatbot, or a multi-agent orchestrator. It coordinates deterministic
workflow structure; the LLM Runtime is one execution dependency inside
one workflow step.

An `EngineeringIntent` tells it *which* workflow to run. The engine
never re-classifies, never invents retrieval criteria, and never
interprets the request text.

## Pipeline

```
Conversation
   → WorkingMemory
   → EngineeringIntent
   → Engineering Engine
        → Workflow Selection    (registry-driven)
        → Workflow Plan          (explicit, immutable, deterministic)
        → Plan Validation
        → Workflow Execution     (step handlers, first-failure stop)
   → EngineeringResponse
```

## Boundary

| Layer | Location | Holds |
|---|---|---|
| Domain | `app/domain/engineering_engine/**` | Immutable plan/step/execution/failure/timeline models, the declarative workflow definition, the planner, structural validators |
| Application | `app/services/engineering_engine/**` | Workflow registry, step handler registry, typed execution context, step handlers (adapters), plan executor, engine service, composition root |
| API | `app/routers/engineering_engine.py`, `app/schemas/engineering_engine.py` | HTTP surface and the per-request composition root |

The domain imports no router, schema, FastAPI, persistence adapter,
provider SDK, or application service, and depends on exactly two other
domain contexts (`engineering_intent`, `engineering_response`).

## Domain model

`engineering_engine_models.py`: `EngineeringEngineExecutionId/Request/
Result/Status/Metadata`, `EngineeringEngineFailure/FailureCode`,
`WorkflowId/Type/Definition/StepDefinition`, `WorkflowPlan/PlanId/
PlanVersion/PlanMetadata/PlanStatistics`, `WorkflowStep/StepId/StepType/
StepStatus/StepResult/StepFailure`, `WorkflowExecution/ExecutionEvent/
ExecutionTimeline/ExecutionStatistics`, `WorkflowSelection/
SelectionResult`, `WorkflowArtifactKey`, `WorkflowCapability`,
`ConversationUpdateProposal`, `SessionUpdateProposal`,
`PreparedAggregateUpdates`, `AggregateUpdateDisposition`,
`EngineeringEngineValidationResult`. All frozen, slotted.

## Execution request

Carries **identifiers plus configuration**, never whole aggregates:

- Provenance: `project_id`, `engineering_session_id`,
  `conversation_id`, `turn_id`, `request_text`.
- Classification: `engineering_intent_id`, `intent_type` (exactly what
  `/engineering-intents/classify` returned).
- `executed_at` - caller-supplied; the domain never reads the clock.
- Retrieval configuration mirroring `StructuredRetrievalRequestFactory`
  (`retrieval_limit`, `retrieval_entity_type`,
  `retrieval_canonical_entity_id`, `retrieval_attribute_name`,
  `retrieval_lexical_terms`, neighborhood settings).
- Runtime configuration mirroring the provider-neutral runtime
  (`provider_id`, `model_identifier`, `request_correlation_id`).
- Two structural Working Memory signals.

**Neither the `Conversation` nor the `EngineeringSession` aggregate is
required**, because Milestone 23A only *prepares* updates for them and
therefore never reads their state.

## Workflow registry

`WorkflowRegistry` owns the one `EngineeringIntentType →
WorkflowDefinition` map. It rejects duplicate registrations, reports
missing ones as a typed `UNSUPPORTED_INTENT` failure, exposes
registered metadata in deterministic order, and freezes after
composition.

**There is no intent branching in the engine core** - verified by an
AST-level architecture test
(`test_engine_core_never_branches_over_intent_types`), not a text
search.

## Workflow definition and the real plan

`KNOWLEDGE_QUERY_WORKFLOW` (`workflow_definitions.py`) is purely
declarative. Its ten steps are the *real* pipeline:

| # | Step | Capability | Requires → Produces |
|---:|---|---|---|
| 0 | `VALIDATE_EXECUTION_REQUEST` | request validation | execution request → – |
| 1 | `BUILD_RETRIEVAL_REQUEST` | structured retrieval | execution request → retrieval request |
| 2 | `EXECUTE_RETRIEVAL` | structured retrieval | retrieval request → retrieval result |
| 3 | `BUILD_CONTEXT` | context building | retrieval result → context package |
| 4 | `BUILD_PROMPT` | prompt building | context package → prompt package |
| 5 | `INVOKE_LLM_RUNTIME` | runtime invocation | prompt package → response envelope |
| 6 | `BUILD_ENGINEERING_RESPONSE` | response building | context + prompt + envelope → response + validation |
| 7 | `VALIDATE_ENGINEERING_RESPONSE` | response building | response + validation → – |
| 8 | `PREPARE_CONVERSATION_UPDATE` | update preparation | response → conversation proposal |
| 9 | `PREPARE_SESSION_UPDATE` | update preparation | response → session proposal |

**There is deliberately no separate graph-query step**: Graph Query is
already an internal dependency of Structured Retrieval (which reads
through `GraphQueryRepository`), so modelling it here would duplicate
it artificially.

## Deterministic identity

```
WorkflowPlanId = project_id:conversation_id:turn_id
                 :engineering_intent_id:workflow_id:workflow_version
WorkflowStepId = {plan_id}#{ordinal}:{step_type}
ExecutionId    = exec:{plan_id}
```

No random UUIDs. `planned_at` comes from the request's `executed_at`.

## Step handlers and execution context

Handlers implement `supports(step_type)` / `async execute(step,
context)`. Each **delegates to an existing service** - none
re-implements retrieval, context, prompt, runtime, or response logic.
The engine core knows only the `WorkflowStepHandler` protocol.

`WorkflowExecutionContext` is a **frozen dataclass with explicitly
typed optional artifact fields** - not an untyped dict and not one
giant mutable object. `with_artifact` returns a new context;
`missing_artifacts` reports exactly what a step needs and lacks.

Execution semantics: strictly ordinal order, no parallelism, no
retries; required artifacts checked before a step and produced
artifacts checked after; **execution stops at the first failure** with
all remaining steps recorded `SKIPPED`; no raw exception escapes.

## Failure model

Fourteen provider-neutral codes: `INVALID_EXECUTION_REQUEST`,
`UNSUPPORTED_INTENT`, `WORKFLOW_NOT_REGISTERED`,
`INVALID_WORKFLOW_PLAN`, `STEP_HANDLER_NOT_REGISTERED`,
`MISSING_REQUIRED_ARTIFACT`, `RETRIEVAL_FAILURE`,
`CONTEXT_BUILD_FAILURE`, `PROMPT_BUILD_FAILURE`, `RUNTIME_FAILURE`,
`RESPONSE_BUILD_FAILURE`, `RESPONSE_VALIDATION_FAILURE`,
`AGGREGATE_UPDATE_FAILURE`, `INTERNAL_EXECUTION_ERROR`.

## Aggregate update policy

**Policy B - explicit proposals.** The engine returns
`ConversationUpdateProposal`/`SessionUpdateProposal`, each with
`disposition = PREPARED`, and never mutates either aggregate. The
validator rejects any Milestone 23A result claiming `APPLIED`, so the
result can never imply an update occurred when only a proposal was
returned.

## API

```
POST /projects/{project_id}/engineering-engine/execute
```

The body never accepts a workflow plan (enforced by an OpenAPI
integrity test) - the server selects and constructs it. Returns
execution id, status, selection, plan, step results, timeline,
`EngineeringResponse` on success, prepared updates, typed failure on
failure, statistics, and the validation result.

**An unsupported intent returns HTTP 200 with `status="unsupported"`**,
not a client error: the request was well-formed and answered
correctly. `422` is reserved for structurally invalid requests (e.g. a
non-positive path project id).

## Determinism

**Planning determinism** is guaranteed: identical inputs under the same
registry and definition versions always yield the same plan id, step
ids, and execution id. **Runtime output determinism is not claimed** -
a language model is not a deterministic function. Tests hold the
runtime constant with the existing `FakeLLMProviderAdapter` and mocked
SDK clients, never a real provider.

## Transaction boundary (future, not implemented)

Nothing is persisted today. The *intended future* transaction would
atomically persist the `EngineeringResponse`, the Conversation update,
the EngineeringSession update, and (if ever persisted) the execution
record together. **That transaction does not exist** - Milestone 23A
neither implements it nor depends on it.

## Adding a workflow in Milestone 23B

1. Add a `WorkflowDefinition` to `workflow_definitions.py`.
2. Add any new step handlers to `step_handlers.py`.
3. Register both in `composition.py`.

**No change to the engine core is required** -
`engineering_engine_service.py` does not import concrete workflow
definitions, which is itself an architecture test.

## Non-goals

No other workflow, no fallback workflow, no agents, no tool execution,
no task decomposition, no retries, no parallel steps, no persistence,
no background execution, no cancellation, no provider selection logic,
no direct provider SDK calls, no frontend integration.
