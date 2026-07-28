# Engineering Engine

**Status:** As-built reference, Milestone 23A (Engineering Engine
Foundation), Milestone 23B.1 (Document Lookup workflow), Milestone
23B.2 (Engineering Explanation workflow), Milestone 24.1
(Engineering Verification workflow) and Milestone 24.2
(Engineering Comparison workflow). For the
decision record (why the engine is an application coordinator, why
planning and execution are separate, why registration replaces intent
branching, why aggregate updates are explicit, why planning determinism
differs from runtime nondeterminism), see
[ADR-0020](adr/0020-engineering-engine-foundation.md). For where this
sits in the pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

> **Five workflows are registered:** `KNOWLEDGE_QUERY` (23A),
> `DOCUMENT_LOOKUP` (23B.1), `ENGINEERING_EXPLANATION` (23B.2),
> `ENGINEERING_VERIFICATION` (24.1) and `ENGINEERING_COMPARISON`
> (24.2). Every other intent type returns an explicit `UNSUPPORTED`
> result and runs nothing at all.

> **`DOCUMENT_LOOKUP` is the first workflow that invokes no LLM.** It
> answers entirely from governed repository state.
> **`ENGINEERING_EXPLANATION` is the second LLM-powered workflow**, and
> reuses the knowledge-query pipeline end to end.
> **`ENGINEERING_VERIFICATION` is the first *reasoning* workflow**: it
> evaluates whether a statement is supported by the project's evidence
> rather than presenting that evidence. None changed any engine decision
> **`ENGINEERING_COMPARISON` is the first workflow with two subjects**,
> two independent retrievals, and a pipeline that genuinely differs
> rather than only a prompt. None changed any engine decision logic -
> see [Adding a workflow](#adding-a-workflow-four-worked-examples).

## What the engine is - and is not

The Engineering Engine is the **application-level coordination
mechanism** that selects, plans and executes engineering workflows. It
is **not** an autonomous agent, an LLM brain, a reasoning engine, a
chatbot, or a multi-agent orchestrator. It coordinates deterministic
workflow structure; the LLM Runtime is one execution dependency inside
one workflow step.

An `EngineeringIntent` tells it *which* workflow to run. The engine
never re-classifies, never invents retrieval criteria, and never
interprets the request text. That last point is now enforced rather than
asserted: architecture tests forbid the engine from importing the
classifier service, the classification rule table, the request
normalizer, or the retrieval bridge itself
(`test_the_engine_never_imports_the_classifier_service_or_normalizer`,
`test_the_engine_never_imports_the_bridge`). **The engine cannot parse
natural language, by construction.**

## Pipeline

```
Conversation
   → WorkingMemory
   → EngineeringIntent
   → Retrieval Bridge          (derives the retrieval criteria - 23B.3)
   → Engineering Engine
        → Workflow Selection    (registry-driven)
        → Workflow Plan          (explicit, immutable, deterministic)
        → Plan Validation
        → Workflow Execution     (step handlers, first-failure stop)
   → EngineeringResponse
```

Since Milestone 23B.3 a caller no longer has to write retrieval criteria
by hand: the **Classification-to-Retrieval Bridge** derives them from the
classified request, and its output *is* this engine's execution request
body. **Nothing about the engine changed to accommodate it** - the bridge
is a stage before the engine, and the engine still receives an explicit,
fully-formed execution request. See
[retrieval_bridge.md](retrieval_bridge.md).

## Boundary

| Layer | Location | Holds |
|---|---|---|
| Domain | `app/domain/engineering_engine/**` | Immutable plan/step/execution/failure/timeline models, the declarative workflow definitions, the planner, structural validators |
| Application | `app/services/engineering_engine/**` | Workflow registry, step handler registry, the step-handler contract (`step_handler.py`), typed execution context, per-workflow step handlers (adapters), plan executor, engine service, composition root |
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
  `retrieval_lexical_terms`, neighborhood settings). Supplied by the
  caller, or - since Milestone 23B.3 - derived from the classified
  request by the Retrieval Bridge. The engine cannot tell the difference,
  and deliberately does not need to.
- Runtime configuration mirroring the provider-neutral runtime
  (`provider_id`, `model_identifier`, `request_correlation_id`).
- Two structural Working Memory signals.

**Neither the `Conversation` nor the `EngineeringSession` aggregate is
required**, because the engine only *prepares* updates for them and
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

## Workflow definitions and the real plans

All five definitions live in `workflow_definitions.py` and are purely
declarative data - no executable logic, no service call.

### `KNOWLEDGE_QUERY_WORKFLOW`

Its ten steps are the *real* pipeline:

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

### `DOCUMENT_LOOKUP_WORKFLOW`

Answers *"trova il documento del montante T2"*, *"quali documenti parlano
della protezione 87T?"* - by reading the project's Engineering Index for
documents whose recorded mentions match the requested engineering
designations. Seven steps, **no LLM**:

| # | Step | Capability | Requires → Produces |
|---:|---|---|---|
| 0 | `VALIDATE_EXECUTION_REQUEST` | request validation | execution request → – |
| 1 | `BUILD_DOCUMENT_RETRIEVAL_REQUEST` | document retrieval | execution request → document retrieval request |
| 2 | `EXECUTE_DOCUMENT_RETRIEVAL` | document retrieval | document retrieval request → document retrieval result |
| 3 | `BUILD_DOCUMENT_LOOKUP_RESPONSE` | response building | document retrieval result → response + validation |
| 4 | `VALIDATE_ENGINEERING_RESPONSE` | response building | response + validation → – |
| 5 | `PREPARE_CONVERSATION_UPDATE` | update preparation | response → conversation proposal |
| 6 | `PREPARE_SESSION_UPDATE` | update preparation | response → session proposal |

**The workflow stops where the retrieved data already answers the
question.** There is deliberately no Context Builder step, no Prompt
Builder step and no runtime step: "which documents mention 87T?" is
answered by the documents themselves. Summarizing them would be a
different question, and answering it would require reading their
contents - which this workflow does not do.

Steps 4-6 are the *same step types*, served by the *same registered
handlers*, as the knowledge-query workflow's - reused, not duplicated.

Steps 1-2 are deliberately **not** a reuse of
`BUILD_RETRIEVAL_REQUEST`/`EXECUTE_RETRIEVAL`: exactly one handler is
registered per step type, and these steps read the Engineering Index,
whereas those read the project knowledge graph through Structured
Retrieval. Sharing the names would make one step type mean two different
things depending on which workflow happened to be running.

The engineering designations come from the execution request's existing
`retrieval_lexical_terms`. The engine invents none of them and never
parses them out of the request text - that would be exactly the free-text
interpretation the classifier deliberately does not perform.

#### The response it produces

An ordinary `EngineeringResponse`, with the same fixed nine-section
shape, held to the same structural validation - carrying
`document_references` instead of graph `references`, and declaring
`origin = DETERMINISTIC_RETRIEVAL`. Its `provider_id`,
`configured_model_identifier` and `runtime_version` are `null`, and
validation **rejects** a deterministic response that claims any of them:
a response nothing generated must never look like one a model generated.

Each `DocumentReference` exposes only fields a repository already holds -
document id, title (the stored filename), format, category, revision,
recorded mentions with their locators, derived page references - plus a
`relevance` score that is the sum of named, weighted components drawn
from a fixed documented table (`document_relevance_policy.py`), never an
opaque number. Metadata fields are nullable: an Engineering Index entry
may outlive the document row it points at (ADR-0002), and an unknown
title is reported as unknown rather than filled in.

**Finding nothing is a success, not a failure.** No matching document
yields a `COMPLETED` execution carrying an `EMPTY` response that says so,
with an `INSUFFICIENT_EVIDENCE` warning and `HIGH` uncertainty.

### `ENGINEERING_EXPLANATION_WORKFLOW`

Answers *"spiegami il funzionamento della protezione 87T"*, *"descrivi
lo schema funzionale del trasformatore T1"*, *"spiegami il ruolo del
sezionatore Q52"*. The second LLM-powered workflow.

Its pipeline is **the knowledge-query pipeline**, step for step, with
exactly one difference:

| # | Step | Same as `KNOWLEDGE_QUERY`? |
|---:|---|---|
| 0 | `VALIDATE_EXECUTION_REQUEST` | yes |
| 1 | `BUILD_RETRIEVAL_REQUEST` | yes |
| 2 | `EXECUTE_RETRIEVAL` | yes |
| 3 | `BUILD_CONTEXT` | yes |
| 4 | **`BUILD_EXPLANATION_PROMPT`** | **the one difference** |
| 5 | `INVOKE_LLM_RUNTIME` | yes |
| 6 | `BUILD_ENGINEERING_RESPONSE` | yes |
| 7 | `VALIDATE_ENGINEERING_RESPONSE` | yes |
| 8 | `PREPARE_CONVERSATION_UPDATE` | yes |
| 9 | `PREPARE_SESSION_UPDATE` | yes |

That is the whole difference, and it is deliberate. *"Spiegami il
funzionamento della protezione 87T"* and *"quale TA è installato sul
montante T2?"* need the same governed graph evidence; what differs is
what the engineer wants done with it. Modelling that as a different
retrieval strategy, a different context budget or a second response
builder would invent distinctions the domain does not have.

#### Why a distinct step type, and why not a distinct handler

Exactly one handler is registered per `WorkflowStepType`, so a step that
must behave differently needs its own type. But it does **not** need its
own handler: `BuildPromptStepHandler` takes its step type and its
`PromptObjective` at construction, and the composition root registers the
*same class* twice -

```python
registry.register(WorkflowStepType.BUILD_PROMPT, BuildPromptStepHandler())
registry.register(
    WorkflowStepType.BUILD_EXPLANATION_PROMPT,
    BuildPromptStepHandler(
        step_type=WorkflowStepType.BUILD_EXPLANATION_PROMPT,
        objective=PromptObjective.ENGINEERING_EXPLANATION,
    ),
)
```

The objective is stated declaratively, once, next to the workflow that
wants it - never derived inside the handler from an intent or workflow
type, which would reintroduce the branching the registry exists to
remove. An architecture test
(`test_no_handler_derives_its_behaviour_from_an_intent_or_workflow_type`)
enforces that.

`BUILD_EXPLANATION_PROMPT` produces the same `PROMPT_PACKAGE` artifact
from the same `CONTEXT_PACKAGE`, which is why every downstream step is
reused unchanged.

#### What differs in the prompt

Only the `FORMATTING_RULES` and `EXPECTED_OUTPUT` sections - see
[prompt_builder.md](prompt_builder.md#objective). The **truthfulness
constraints are identical**: an explanation is held to the same "never
invent an engineering fact" rule as a direct answer, because a longer
answer is a larger opportunity to invent one, not a licence to. The
explanation set adds two rules this objective specifically needs -
describe only what the evidence covers, and say which aspects it does
not - because *"how does an 87T work"* has a plausible textbook answer
that owes nothing to **this** substation.

#### Retrieval scope

The workflow invents **no** retrieval criteria. It uses the same
`BUILD_RETRIEVAL_REQUEST` step and handler as knowledge query, which
derives its mode purely from the caller-supplied configuration on the
execution request. Explaining one relay by retrieving everything about
the project would be exactly the unrelated context this milestone
forbids; a caller explains `87T` by naming it
(`retrieval_canonical_entity_id`), optionally with neighborhood
expansion, as it already can.

#### Response

An ordinary `EngineeringResponse` with `origin = LLM_INVOCATION` and
normal, fully populated provider metadata. **No new response type, no new
metadata field, and no new failure code** - a prompt failure is the
existing `PROMPT_BUILD_FAILURE`, attributed to
`BUILD_EXPLANATION_PROMPT`.

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
The engine core knows only the `WorkflowStepHandler` protocol, which
lives in `step_handler.py` alongside `StepHandlerError` and
`BaseStepHandler` so the core never imports a concrete handler module.
Handlers are grouped per workflow: `step_handlers.py` (KNOWLEDGE_QUERY),
`document_lookup_step_handlers.py` (DOCUMENT_LOOKUP).

One `WorkflowExecutionContext` serves every workflow; a workflow simply
leaves the artifacts it never produces as `None`.

`WorkflowExecutionContext` is a **frozen dataclass with explicitly
typed optional artifact fields** - not an untyped dict and not one
giant mutable object. `with_artifact` returns a new context;
`missing_artifacts` reports exactly what a step needs and lacks.

Execution semantics: strictly ordinal order, no parallelism, no
retries; required artifacts checked before a step and produced
artifacts checked after; **execution stops at the first failure** with
all remaining steps recorded `SKIPPED`; no raw exception escapes.

## Failure model

Fourteen provider-neutral codes - **unchanged by Milestone 23B.1**,
which introduced no new failure code: a document retrieval failure is
the existing `RETRIEVAL_FAILURE`, a lookup naming no identifier the
existing `INVALID_EXECUTION_REQUEST`, an unwired capability the existing
`STEP_HANDLER_NOT_REGISTERED`.

`INVALID_EXECUTION_REQUEST`,
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
validator rejects any result claiming `APPLIED`, so the
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
record together. **That transaction does not exist** - the engine
neither implements it nor depends on it.

### `ENGINEERING_VERIFICATION_WORKFLOW`

Answers *"verify that protection 87T is present"*, *"check whether cable
C-295 is connected to TA-12"*, *"verify that breaker Q52 exists"*. The
first workflow that **evaluates** rather than presents.

Its pipeline is the knowledge-query pipeline again, differing in exactly
one step - step 4 is `BUILD_VERIFICATION_PROMPT` instead of
`BUILD_PROMPT`. Everything else, including `BUILD_ENGINEERING_RESPONSE`,
is reused unchanged.

That is the finding, not a shortcut. *"Verify that transformer T1 has
differential protection"* needs exactly the same governed graph evidence
as asking what T1 is protected by. What differs is what the engineer
wants done with it, and **that belongs in the prompt and in reading the
result back** - not in a second retrieval strategy, a second context
budget, or engine logic.

#### Where the reasoning lives

| Concern | Owner |
|---|---|
| Asking for a verdict, and the rules that govern it | Prompt Builder (`VERIFICATION_INSTRUCTIONS`) |
| Reading the verdict back | Engineering Response (`engineering_response_verification.py`) |
| Coordinating the steps | The engine - which evaluates **nothing** |

An architecture test
(`test_no_verification_logic_lives_inside_the_engine`) asserts that no
engine module names a verification outcome, the assessment type, or any
verdict literal - matched on whole words, since the engine legitimately
has its own unrelated `UNSUPPORTED_INTENT`.

#### The verdict, and what is *not* interpreted

The prompt asks the model to open its answer with exactly one of four
declared tokens on its own first line. Engineering Response matches that
first line against those four literals - imported from Prompt Builder,
never restated - and:

- examines **nothing** beyond the first line;
- performs no keyword search, no negation handling, no scoring;
- yields **no verdict** when the line matches none of them, rather than
  inferring one from the prose.

`"probably SUPPORTED"` and `"NOT_SUPPORTED, though SUPPORTED in part"`
are therefore both read as *no verdict*, which is the honest reading of
both. This is reading a declared protocol - the same kind of operation as
reading `finish_reason` off the envelope - not interpreting prose, and it
is the single narrow exception to Milestone 18's "no semantic parsing of
provider text" rule.

#### The structural bound

**When no evidence was retrieved, the outcome is
`INSUFFICIENT_EVIDENCE` whatever the model wrote.** With an empty context
there was, by construction, nothing to support or contradict the
statement, so a `SUPPORTED` verdict could only have come from the model's
general knowledge - exactly what a verification must never rest on.

The assessment still records that the model *did* state a verdict and was
overruled (`stated_by_model=True`, `evidence_bounded=True`), because that
is a different situation from a model that said nothing. Validation
enforces the override rather than trusting it.

#### Response

An ordinary `EngineeringResponse` with `origin = LLM_INVOCATION` and
normal provider metadata, carrying a new optional
`verification: VerificationAssessment`. That field is **new rather than a
reuse of `status`** deliberately: `EngineeringResponseStatus.UNSUPPORTED`
already means "the provider returned no usable text", and overloading it
to also mean "the evidence does not support the statement" would make two
entirely different findings indistinguishable. Warnings and uncertainty
declarations cannot express `SUPPORTED` at all.

**No new failure code**: a prompt failure is the existing
`PROMPT_BUILD_FAILURE`, attributed to `BUILD_VERIFICATION_PROMPT`.

### `ENGINEERING_COMPARISON_WORKFLOW`

Answers *"confronta il trasformatore T1 con T2"*, *"quali differenze ci
sono tra il montante M1 e M2?"*. The first workflow with **two subjects**,
and the first whose pipeline genuinely differs rather than only its
prompt.

| # | Step | Requires → Produces |
|---:|---|---|
| 0 | `VALIDATE_EXECUTION_REQUEST` | execution request → – |
| 1 | `BUILD_COMPARISON_RETRIEVAL_REQUESTS` | execution request → left + right retrieval requests |
| 2 | `EXECUTE_LEFT_RETRIEVAL` | left request → left result |
| 3 | `EXECUTE_RIGHT_RETRIEVAL` | right request → right result |
| 4 | `BUILD_COMPARISON_CONTEXT` | left + right results → comparison context |
| 5 | `BUILD_COMPARISON_PROMPT` | comparison context → prompt package |
| 6 | `INVOKE_LLM_RUNTIME` | prompt package → response envelope |
| 7 | `BUILD_COMPARISON_RESPONSE` | context + prompt + envelope → response + validation |
| 8-10 | `VALIDATE_ENGINEERING_RESPONSE`, `PREPARE_CONVERSATION_UPDATE`, `PREPARE_SESSION_UPDATE` | reused unchanged |

#### Why retrieval is two steps and request-building is one

Building both operands' requests is **pure**, and an operand set that
cannot produce a valid request is an invalid *request* whichever side it
came from - attributing that to "the left retrieval" would mislead. So
that is one step.

Executing is where the sides genuinely diverge, so that is two. **A left
retrieval failure and a right retrieval failure are different facts an
engineer needs told apart**, and one combined step would report them
identically. With two steps the attribution is free: the failing
`step_type` names the side.

#### Provenance: the two sides never merge

`LEFT_RETRIEVAL_RESULT` and `RIGHT_RETRIEVAL_RESULT` stay distinct
artifacts, and the context that follows holds **two whole
`ContextPackage`s** rather than a merged candidate list (see
[context_builder](#) - `ComparisonContextPackage`). Each side keeps its
own coverage, budget and warnings rather than an averaged story that
would describe neither.

Left and right are **named fields everywhere** - on the execution
request, in the execution context, in the context package, in the prompt
sections. There is no index to transpose and no role tag to mislabel, so
"compare A with B" cannot silently become "compare B with A". That
matters because additions, removals and every directional finding invert.

#### The structural bound

**When either side retrieved no evidence, the outcome is
`INSUFFICIENT_EVIDENCE` whatever the model wrote.**

This is the safety property of the whole workflow. Given evidence for T1
and none for T2, a fluent model will happily produce *"T2 lacks the
differential protection that T1 has"* - which reads as an engineering
finding but is really a statement about what the project's reviewed
knowledge happens to cover. An engineer acting on it would be
commissioning a change on the strength of a gap in an index. Absence of
retrieved evidence is not evidence of absence, and this is where the
system enforces that rather than merely instructing it.

The prompt also renders an evidence-less side as an explicit statement
that the project holds no evidence for it, rather than as an empty
section - an empty section would leave the model to infer *why*, and the
likeliest wrong inference is the one this workflow must prevent.

#### Outcome vocabulary

`COMPARABLE`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE` - read from
the same declared first-line protocol a verification verdict uses.

Deliberately **not** "same" versus "different": a real comparison of two
montanti almost always contains both changed and unchanged aspects, so a
top-level same/different verdict would force a false choice. The prompt
asks for the findings to be grouped under ADDED / REMOVED / MODIFIED /
UNCHANGED, and those groupings stay **prose in the response body** -
extracting them into typed findings would mean parsing free text to
manufacture engineering structure. See
[Technical debt](#) and `ComparisonAssessment`'s own docstring.

## Adding a workflow: four worked examples

The recipe:

1. Declare a `WorkflowDefinition` in `workflow_definitions.py`.
2. Add the step types, artifact keys, capability and workflow type it
   needs as **enum members** in `engineering_engine_models.py`.
3. Add any new typed artifact fields to `WorkflowExecutionContext`.
4. Write any new handlers in their own module, implementing the shared
   `WorkflowStepHandler` contract from `step_handler.py` - or, if an
   existing handler already does the work, parameterize it.
5. Register the workflow and its handlers in `composition.py`, and wire
   any concrete adapters in the router.

**`DOCUMENT_LOOKUP` (23B.1)** needed all five: a new capability, two new
artifact keys, three new step types, a new handler module, two new
adapters in the router.

**`ENGINEERING_EXPLANATION` (23B.2)** needed far less - two enum members
(one workflow type, one step type), a workflow definition, and two lines
in the composition root registering an **already-existing handler class**
with a different Prompt Builder objective. No new capability, no new
artifact key, no new handler, no execution-context change, no router
change. The genuinely new behaviour (an explanation-shaped prompt) landed
where it belongs: inside Prompt Builder, as a `PromptObjective`.

**`ENGINEERING_VERIFICATION` (24.1)** cost the engine exactly the same as
23B.2 - two enum members, a definition, two registrations - even though it
is a materially different *kind* of workflow. Its new behaviour landed in
the two contexts that own it: a `PromptObjective` in Prompt Builder, and a
`VerificationAssessment` in Engineering Response. That a reasoning
workflow required no more of the engine than a rephrased prompt did is the
strongest evidence so far that the coordinator is in the right place.

**`ENGINEERING_COMPARISON` (24.2)** cost the most of the four, and all
of it declarative: a workflow type, six step types, five artifact keys, a
typed `ComparisonOperandCriteria` on the execution request, five
execution-context fields, a handler module and six registrations. The
engine still selects, plans and executes exactly as before - what grew
was its *vocabulary*, not its logic.

**No engine decision logic changed by any of them.** `engineering_engine_service.py`,
`plan_executor.py`, `workflow_registry.py`, `step_handler_registry.py`,
`workflow_planner.py` and `engineering_engine_validation.py` were not
modified. That is enforced, not asserted, by
`tests/architecture/test_engineering_engine_boundaries.py`:

- the core imports no workflow definition, no concrete handler module,
  and no bounded context a single workflow happens to need;
- no core module mentions `knowledge_query` or `document_lookup` by
  name - not in a branch, not in a message, not in a comment;
- `composition.py` is the only place that registers a workflow;
- the executor and handler registry depend on `step_handler.py` (the
  contract) and never on a concrete handler module;
- the document-lookup handler module can reach no provider SDK, provider
  registry, runtime, prompt builder or context builder;
- no handler derives its behaviour from an intent type or a workflow
  type - a workflow that needs a step to behave differently says so
  declaratively in the composition root;
- no engine module names a verification or comparison outcome, an
  assessment type, or any verdict or finding literal - matched on whole
  words, since the engine legitimately has its own unrelated
  `UNSUPPORTED_INTENT`;
- provider adapters and the runtime remain unaware of comparison
  semantics: they map sections to messages and know nothing of left,
  right, or what a comparison is.

### Registered but not wired

Workflow registration is static; handler availability is
per-composition. A composition that registers the workflow without its
ports fails a document lookup with the existing typed
`STEP_HANDLER_NOT_REGISTERED` **before any step runs** - never
`UNSUPPORTED_INTENT`, and never a silent reroute through another
workflow. Conflating the two would make an unwired deployment look like
an unimplemented feature.

## Non-goals

No other workflow, no fallback workflow, no agents, no tool execution,
no task decomposition, no retries, no parallel steps, no persistence,
no background execution, no cancellation, no provider selection logic,
no direct provider SDK calls, no frontend integration. Document lookup
specifically does **not** read, parse, summarize, rank by contents, or
render any document - it reports which documents mention what, and where.
Engineering explanation specifically does **not** introduce a
free-form, caller-supplied or per-request prompt: `PromptObjective`
selects between fixed, versioned, reviewable sets, and nothing else
about a prompt can be varied from outside Prompt Builder.
