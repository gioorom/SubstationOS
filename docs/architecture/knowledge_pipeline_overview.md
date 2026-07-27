# Knowledge Pipeline Overview

**Status:** As-built reference, established by Milestone 12 (Knowledge
Platform Hardening), extended by Milestone 13 (Structured Retrieval
Foundation), Milestone 14 (Context Builder Foundation), Milestone 15
(Prompt Builder Foundation), Milestone 16 (LLM Provider
Abstraction Layer), Milestone 17 (LLM Invocation Runtime),
Milestone 18 (Engineering Response Foundation, EPIC 5), Milestone
19 (Engineering Session Foundation, EPIC 5), and Milestone 20
(Conversation Foundation, EPIC 5).
Describes the governed knowledge pipeline as it
exists today — not the product vision
(`project_intelligence_architecture.md` describes vision and roadmap;
this document describes what is actually implemented, tested, and
running). Update this document when a stage's real behavior changes;
it is not an ADR and carries no historical Context/Decision record of
its own.

## The pipeline, stage by stage

```
Documents → Engineering Index → Proposed Claims → Review Workflow →
Canonicalization → Graph Builder → Project Knowledge Graph → Graph Query →
Structured Retrieval → Context Builder → Prompt Builder →
LLM Provider Abstraction Layer → LLM Invocation Runtime →
Engineering Response → Engineering Session → Conversation
```

The LLM Provider Abstraction Layer and LLM Invocation Runtime stages
are deliberately not another `app/domain/**` bounded context - see the
note below the pipeline table. Engineering Response, one stage further,
*is* a genuine `app/domain/**` bounded context again, despite consuming
the LLM Invocation Runtime's own application-layer output - see
[ADR-0015](adr/0015-engineering-response-foundation.md) for how that
Dependency Rule boundary is resolved.

Each stage trusts the stage before it completely and adds exactly one
new responsibility — no stage re-derives or second-guesses a decision
an earlier stage already made (this is the same discipline
[ADR-0007](adr/0007-project-knowledge-graph-persistence.md) names
explicitly for Graph Builder → Project Knowledge Graph, extended here
across the whole pipeline).

| Stage | Bounded context | Owns | Domain package |
|---|---|---|---|
| Documents | Document Repository | Uploaded files, scope (`PROJECT` vs `CANONICAL_LIBRARY`), classification | `app/models/document.py`, `app/routers/documents.py` |
| Engineering Index | Engineering Index | A structured, per-document index of extracted content — not yet a claim about the installation | `app/domain/engineering_index/**` |
| Proposed Claims | Proposed Claims | Candidate assertions derived from the index, not yet reviewed | `app/domain/proposed_claims/**` |
| Review Workflow | Review Workflow | Human review/approval state for a Proposed Claim | `app/domain/review_workflow/**` |
| Canonicalization | Canonicalization | Normalizes an **approved** claim into a `CanonicalFact` against the Canonical Domain vocabulary | `app/domain/canonicalization/**` |
| Graph Builder | Graph Builder | Translates a `CanonicalFact` into a deterministic `GraphOperationBatch` — a mutation *plan*, not yet applied | `app/domain/graph_builder/**` |
| Project Knowledge Graph | Project Knowledge Graph | Executes a `GraphOperationBatch` atomically and holds current graph state | `app/domain/project_knowledge_graph/**` |
| Graph Query | Graph Query | Deterministic, read-only queries over current graph state, through its own read port | `app/domain/graph_query/**` |
| Structured Retrieval | Structured Retrieval | Ranked, explainable `KnowledgeCandidate`s from structured (non-NL) criteria, built exclusively from Graph Query's read model | `app/domain/structured_retrieval/**` |
| Context Builder | Context Builder | A bounded, provenance-aware, budget-enforced `ContextPackage` assembled from a `KnowledgeCandidateCollection` - selection, aggregation, coverage, budget, warnings, statistics, metadata | `app/domain/context_builder/**` |
| Prompt Builder | Prompt Builder | A deterministic, provider-independent `PromptPackage` composed from a `ContextPackage` - fixed-order sections, versioned constraints/instructions, token estimates, statistics, self-validation | `app/domain/prompt_builder/**` |
| LLM Provider Abstraction Layer | *(application/infrastructure capability, not a bounded context)* | A provider-neutral `LLMRequest` mapped from a `PromptPackage`, translated by a provider adapter (Anthropic first) into a local, never-sent prepared request - no invocation, no provider SDK dependency in the application layer | `app/application/**` (contracts, mapper, registry, service), `app/infrastructure/llm/**` (adapters) |
| LLM Invocation Runtime | *(application/infrastructure capability, not a bounded context)* | Attempt sequencing, total-deadline enforcement, retry decisions, cancellation, and provider-neutral response normalization for exactly one real provider call per invocation | `app/application/services/llm_runtime.py`, `app/application/policies/**`, `app/application/validation/**` (runtime), `app/infrastructure/llm/anthropic/**` (invoker, error mapper, response mapper) |
| Engineering Response | Engineering Response | A structured, traceable `EngineeringResponse` - typed sections, structured warnings, uncertainty declarations, preserved evidence/version provenance - deterministically normalized from an `LLMResponseEnvelope`, never AI-interpreted | `app/domain/engineering_response/**` (domain), `app/services/engineering_response_service.py` (the one translation seam) |
| Engineering Session | Engineering Session | The root aggregate for one engineering work session - project identity, session state, an ordered history of `EngineeringResponse`s, an append-only timeline, statistics, version metadata; owns no conversation/chat/memory/tools/agents yet | `app/domain/engineering_session/**` (domain), `app/services/engineering_session_service.py` |
| Conversation | Conversation | Structured engineering dialogue belonging to an `EngineeringSession` (referenced, never embedded) - ordered Turns owning ordered Messages and `EngineeringResponse` references; Turn, not Message, is the primary conversational unit; no memory/tools/agents yet | `app/domain/conversation/**` (domain), `app/services/conversation_service.py` |

**Note on the last two rows:** unlike every other stage in this table,
the LLM Provider Abstraction Layer and the LLM Invocation Runtime are
intentionally not implemented as new `app/domain/**` bounded contexts
(Milestone 16's own instruction, reaffirmed unchanged by Milestone 17:
"do not create a new engineering bounded context merely to hold
external provider details"). Provider selection, request shaping, and
now invocation lifecycle management are an application/infrastructure
concern, not new engineering domain knowledge about substations - see
[ADR-0013](adr/0013-llm-provider-abstraction-layer.md),
[llm_provider_abstraction.md](llm_provider_abstraction.md),
[ADR-0014](adr/0014-llm-invocation-runtime.md), and
[llm_invocation_runtime.md](llm_invocation_runtime.md).

## Required conceptual distinction

```
CanonicalFact = normalized approved engineering assertion
GraphOperationBatch = deterministic mutation plan
GraphExecution = audited application of a mutation plan
Project Knowledge Graph = current project-scoped graph state
Graph Query = deterministic read model
Structured Retrieval = deterministic, structured-criteria ranking layer over Graph Query
Context Builder = bounded, provenance-aware context assembly layer over Structured Retrieval's output
Prompt Builder = deterministic, provider-independent prompt-composition layer over a ContextPackage
LLM Provider Abstraction Layer = provider-neutral request contract + first (Anthropic) adapter over a PromptPackage - request preparation only, no invocation
LLM Invocation Runtime = attempt/retry/deadline/cancellation-governed execution of exactly one real provider call, behind the same LLMProviderPort - implemented, disabled by default, never exercised with a real provider in the automated test suite
Engineering Response = the canonical, domain-owned, provider-neutral representation of an AI answer - typed sections, structured warnings, uncertainty, preserved evidence - deterministically normalized from an LLMResponseEnvelope, never AI-interpreted
Engineering Session = the root aggregate for one engineering work session - owns project identity, session state, an ordered history of EngineeringResponses, a timeline, statistics, and version metadata; not a chat, owns no conversation/memory/tools/agents yet
Conversation = structured engineering dialogue belonging to an EngineeringSession - ordered Turns (the primary conversational unit, not Messages) owning ordered Messages and EngineeringResponse references; no memory/tools/agents yet
Semantic Retrieval = future retrieval and ranking layer
AI Assistant = future consumer, not owner, of engineering truth
```

Semantic Retrieval and the AI Assistant are **not implemented**. No
code in this repository performs embedding, vector search, semantic
ranking, or natural-language query interpretation today — every read
in Graph Query is a deterministic, exact query (by id, by type, by
attribute presence, by 1-hop adjacency); Structured Retrieval
(Milestone 13) adds only deterministic, structured-criteria matching
and a fixed, documented scoring policy on top of it; Context Builder
(Milestone 14) adds only deterministic selection, budget enforcement,
and coverage/warning reporting on top of that; Prompt Builder
(Milestone 15) adds only deterministic section composition, a fixed
constraint/instruction policy, and an approximate, provider-independent
token estimate on top of that; the LLM Provider Abstraction Layer
(Milestone 16) adds only deterministic request translation and a
capability-declaring provider adapter on top of that; and the LLM
Invocation Runtime (Milestone 17) adds a governed execution path
(attempt sequencing, total-deadline enforcement, retry policy,
cancellation, response normalization) capable of a real Anthropic call
— but that path is **disabled by default**
(`LLM_RUNTIME_ENABLED=false`), and no automated test in this repository
ever calls a real provider: every test exercises either the fake
adapter or a mocked/monkeypatched Anthropic client; Engineering
Response (Milestone 18) adds only a deterministic normalization of an
already-produced `LLMResponseEnvelope` into a structured
`EngineeringResponse` (typed sections, structured warnings, uncertainty
declarations derived from structural signals) on top of that - still no
AI usage of its own, no semantic parsing of the provider's own prose;
Engineering Session (Milestone 19) adds only a deterministic root
aggregate owning a session's state, its ordered `EngineeringResponse`
history, and an append-only timeline on top of that; and Conversation
(Milestone 20) adds only a deterministic Turn/Message hierarchy
referencing `EngineeringResponse`s produced during a session on top of
that - still no memory, tool execution, agents, or assistant reasoning
of any kind (see
[structured_retrieval.md](structured_retrieval.md),
[context_builder.md](context_builder.md),
[prompt_builder.md](prompt_builder.md),
[llm_provider_abstraction.md](llm_provider_abstraction.md),
[llm_invocation_runtime.md](llm_invocation_runtime.md),
[engineering_response.md](engineering_response.md),
[engineering_session.md](engineering_session.md),
[conversation.md](conversation.md),
[ADR-0010](adr/0010-structured-retrieval-foundation.md),
[ADR-0011](adr/0011-context-builder-foundation.md),
[ADR-0012](adr/0012-prompt-builder-foundation.md),
[ADR-0013](adr/0013-llm-provider-abstraction-layer.md),
[ADR-0014](adr/0014-llm-invocation-runtime.md),
[ADR-0015](adr/0015-engineering-response-foundation.md),
[ADR-0016](adr/0016-engineering-session-foundation.md),
[ADR-0017](adr/0017-conversation-foundation.md)). Describing
Semantic Retrieval or the AI Assistant as existing would misrepresent
the system; they are named here only to mark where a future milestone
(the AI Assistant, per the Product Development Plan) will attach, and
to make clear that when it arrives, it consumes Conversation's own
structured Turn/Message history — it does not gain its own path to
engineering truth, and Anthropic remains one configurable adapter
rather than the platform's identity.

## Bounded-context dependency direction

Enforced by `tests/architecture/test_bounded_context_dependencies.py`,
a lightweight, repository-native check (Python's `ast` module — no
framework dependency added) that parses every file under
`app/domain/**` and asserts it imports only from the domain contexts
its own position in the pipeline is allowed to depend on:

```
project               (foundation - depends on nothing)
engineering_index      -> project
proposed_claims        -> project, engineering_index
review_workflow        -> project, proposed_claims
canonicalization        -> project, proposed_claims, review_workflow
graph_builder           -> project, canonicalization, proposed_claims
project_knowledge_graph -> project, graph_builder
graph_query             -> project, graph_builder
structured_retrieval    -> project, graph_builder, graph_query
context_builder         -> project, structured_retrieval
prompt_builder          -> project, context_builder, structured_retrieval
```

`app/application/**` (the LLM Provider Abstraction Layer, Milestone 16)
is not part of this table at all - it sits outside `app/domain/**` by
design (see the pipeline table's note above) and is governed by its
own, separate architecture tests
(`tests/architecture/test_llm_provider_boundaries.py`) rather than the
domain dependency-order table below.

`graph_builder`'s dependency on `proposed_claims` (in addition to
`canonicalization`, which is already downstream of `proposed_claims`)
is not a backward dependency: it is legitimate reuse of the single
shared `ClaimType` vocabulary type. `ClaimType` is defined once in
Proposed Claims, carried unchanged onto `CanonicalFact.claim_type` by
Canonicalization, and inspected again by Graph Builder's
`GraphOperationFactory.from_canonical_fact` to decide whether a fact
produces an EXISTENCE, ATTRIBUTE, or RELATIONSHIP operation — the same
"shared, stable type reused across contexts" pattern
`GraphEntityId`/`GraphRelationshipType` already use across Graph
Builder, Project Knowledge Graph, and Graph Query. The dependency-graph
test's own table documents this reasoning inline.

Two further architecture tests guard the two boundaries most at risk
of erosion:

- `test_graph_query_never_imports_graph_store` — Graph Query reads the
  Project Knowledge Graph through its **own** read port
  (`GraphQueryRepository`), never through `GraphStore` (the write-side
  port only Graph Persistence's execution service uses). A downstream
  read context reaching backward into an upstream context's private
  write infrastructure would be exactly the kind of boundary violation
  ADR-0002 and ADR-0007 both guard against.
- `test_governed_graph_path_does_not_import_legacy_knowledge_graph_code`
  — no file under Graph Builder, Project Knowledge Graph, or Graph
  Query imports anything from the legacy Knowledge Graph modules (see
  [ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md)). The
  governed and legacy graph paths must never merge.

Two more, added in Milestone 13, guard Structured Retrieval's own
boundaries: `test_structured_retrieval_domain_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no legacy Knowledge Graph modules, no
Proposed Claims/Review Workflow) and
`test_structured_retrieval_surface_has_no_ai_or_vector_dependency` (no
`anthropic`, `openai`, or `app.services.ai` import anywhere in the
domain, service, or router files) — the codified form of ADR-0010's
"deterministic first, no AI provider" decision.

Two more, added in Milestone 14, guard Context Builder's own
boundaries the same way: `test_context_builder_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no Graph Query read port/service/router,
no Structured Retrieval *service or router* - its domain models are the
one allowed, shared-vocabulary exception - no legacy Knowledge Graph
modules, no Proposed Claims/Review Workflow) and
`test_context_builder_surface_has_no_ai_or_vector_dependency` (no
`anthropic`, `openai`, or `app.services.ai` import anywhere in the
domain, service, or router files) — the codified form of ADR-0011's
"assembly only, no retrieval, no AI" decision.

Two more, added in Milestone 15, guard Prompt Builder's own boundaries
the same way: `test_prompt_builder_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no Graph Query read port/service/router,
no Structured Retrieval *or* Context Builder service/router - their
domain models are the one allowed, shared-vocabulary exception - no
legacy Knowledge Graph modules, no Proposed Claims/Review Workflow) and
`test_prompt_builder_surface_has_no_ai_or_provider_dependency` (no
`anthropic`, `openai`, `app.services.ai`, `ollama`, or `azure` import
anywhere in the domain, service, or router files) — the codified form
of ADR-0012's "composition only, no serialization, no provider SDK"
decision.

Milestone 16 adds a dedicated file,
`tests/architecture/test_llm_provider_boundaries.py`, rather than
extending the bounded-context dependency table above (the LLM Provider
Abstraction Layer is not a domain bounded context - see the pipeline
table's note). It enforces: the provider-neutral contract surface
(`app/application/ports/**` + `app/application/models/**`) and the
whole `app/application/**` tree import no provider SDK (`anthropic`,
`openai`, `azure`, `ollama`), no HTTP client (`requests`, `httpx`), no
SQLAlchemy, and no Graph Query/Structured Retrieval/Context
Builder/Prompt Builder *service or router* (`test_application_contracts_do_not_import_forbidden_modules`,
`test_application_llm_layer_does_not_import_forbidden_modules`); the
Anthropic adapter (`app/infrastructure/llm/anthropic/**`) imports
nothing from the `anthropic` package itself, no knowledge-graph/
retrieval/canonicalization internals, no engineering domain service, no
persistence repository, and no HTTP router
(`test_anthropic_adapter_does_not_import_forbidden_modules`,
`test_anthropic_adapter_module_never_imports_the_anthropic_sdk`); and
the fake test adapter carries no provider or network dependency of its
own (`test_fake_adapter_has_no_provider_or_network_dependency`) - the
codified form of ADR-0013's "Anthropic is an adapter, never a domain
dependency" decision.

Milestone 17 extends the same file rather than adding a new one, since
invocation is the same non-bounded-context capability, not a new
architectural surface. Milestone 16's narrow
`test_anthropic_adapter_module_never_imports_the_anthropic_sdk` is
replaced by a positive-confinement test,
`test_anthropic_sdk_is_confined_to_the_anthropic_adapter_package`,
because invocation legitimately requires the `anthropic`/`httpx`
imports Milestone 16 had forbidden: it scans every file under `app/`
and asserts that only `app/infrastructure/llm/anthropic/**` (plus the
already-isolated legacy `app/services/ai/**`, per
[ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md)) may import
`anthropic` or `httpx` — everything else in the tree, including
`app/application/**` itself, must not. This is the codified form of
ADR-0014's "the SDK is confined to the Anthropic adapter package, and
the runtime owns retry, not the SDK" decision.

Milestone 18 adds `engineering_response` to `ALLOWED_DOMAIN_DEPENDENCIES`
above (`{"project", "context_builder", "prompt_builder",
"structured_retrieval"}`) and a dedicated boundary section in the same
file: `test_engineering_response_domain_does_not_import_forbidden_modules`
(no SQLAlchemy, no graph ports, no legacy Knowledge Graph path, no
Proposed Claims/Review Workflow, no Structured Retrieval/Context
Builder/Prompt Builder *service or router*, and - this milestone's own
new guarantee - no `app.application.**` of any kind, no provider SDK,
no LLM Invocation Runtime module),
`test_engineering_response_surface_has_no_ai_or_provider_dependency`
(no `anthropic`/`openai`/`app.services.ai`/`ollama`/`azure`), and the
explicit, narrowly-scoped
`test_engineering_response_domain_never_imports_the_application_layer` -
the codified form of ADR-0015's central architectural claim: this
domain context consumes an application-layer artifact's *content*
(via its own domain-owned restatement, built once in
`app/services/engineering_response_service.py`) without ever importing
the application layer itself.

Milestone 19 adds `engineering_session` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"engineering_response"}` - the smallest dependency set of any
context in this pipeline) and its own dedicated boundary section:
`test_engineering_session_does_not_import_forbidden_modules` (no
SQLAlchemy, no graph ports, no legacy Knowledge Graph path, no Proposed
Claims/Review Workflow, no sibling *service or router* modules
including Engineering Response's own, no `app.application.**`, no
provider SDK, no LLM Invocation Runtime module),
`test_engineering_session_surface_has_no_ai_or_provider_dependency`,
and `test_engineering_session_domain_never_imports_the_application_layer`
- the last with **no exceptions anywhere**, unlike Engineering
Response's own equivalent test, since Engineering Session has no
application-layer input to translate in the first place (see
ADR-0016).

Milestone 20 adds `conversation` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"engineering_session", "engineering_response"}`) and its own
dedicated boundary section: `test_conversation_does_not_import_forbidden_modules`,
`test_conversation_surface_has_no_ai_or_provider_dependency`, and
`test_conversation_domain_never_imports_the_application_layer` - again
with no exceptions anywhere, the same guarantee Engineering Session's
own equivalent test establishes (see ADR-0017).

## Public vocabulary boundary: entity types (Graph Query ↔ Canonicalization)

`GraphQueryValidator.validate_entity_type` can confirm an entity-type
string is *syntactically* well-formed, but cannot confirm it is a
*real, registered* entity type — Canonicalization's entity-type
registry (`_ENTITY_TYPE_REGISTRY`) is a private, underscore-prefixed
module constant, and Graph Query has no port onto it. In practice this
means a query for a syntactically valid but nonexistent entity type
(e.g. `"WIDGET"`) returns an empty result rather than a "not a real
entity type" error.

**Decision (Milestone 12, Workstream 5): retain the current syntactic
validation and document this boundary, rather than introduce a new
shared public vocabulary contract.** Two options were considered:

- **Option A — retain + document (chosen).** No new export from
  Canonicalization, no new shared module. The limitation is real but
  low-severity (an empty result set, not a wrong or misleading one),
  and no concrete defect has been demonstrated — only a documented
  gap. This matches Milestone 12's own Change Discipline ("before
  changing existing domain behavior: identify the concrete defect")
  and its general hardening-minimalism bias: the more conservative,
  lower-risk choice is preferred when no defect forces a bigger one.
- **Option B — introduce a genuinely shared public canonical
  vocabulary contract.** Rejected for this milestone: this would mean
  designing a new public export surface from Canonicalization (e.g. a
  `KnownEntityTypes` port both Canonicalization and Graph Query depend
  on) — real design work with real coupling consequences, not a
  hardening-sized change, and explicitly the kind of "expand/redesign
  the ontology this milestone" Workstream 5 forbids. It remains
  available as clearly-scoped future work if a real need (not just a
  theoretical gap) ever appears — e.g. if Graph Query needs to reject
  invalid entity-type queries with a specific error rather than an
  empty result.

## What still bypasses this pipeline

The legacy Knowledge Graph path
(`app/services/knowledge_graph.py::ingest_document`, called from every
document upload) writes directly to `ProjectEntity`/`EntityRelation`
with no review gate — a known, tracked, unremediated violation of
[ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md). See
[ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md) for the full
inventory, isolation guarantees, and why it was not removed or merged
into the governed pipeline this milestone.

## Where to look for more detail

- **Vision and roadmap:** `project_intelligence_architecture.md`.
- **Persistence/execution semantics:** [ADR-0007](adr/0007-project-knowledge-graph-persistence.md).
- **Transaction ownership:** [repository_transaction_conventions.md](repository_transaction_conventions.md).
- **Migrations:** [ADR-0008](adr/0008-database-migration-governance.md), [database_migrations.md](database_migrations.md).
- **Legacy isolation:** [ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md).
- **Performance baseline:** [performance_baseline.md](performance_baseline.md).
- **Startup/health/config:** [operational_reliability.md](operational_reliability.md).
- **Structured Retrieval:** [structured_retrieval.md](structured_retrieval.md), [ADR-0010](adr/0010-structured-retrieval-foundation.md).
- **Context Builder:** [context_builder.md](context_builder.md), [ADR-0011](adr/0011-context-builder-foundation.md).
- **Prompt Builder:** [prompt_builder.md](prompt_builder.md), [ADR-0012](adr/0012-prompt-builder-foundation.md).
- **LLM Provider Abstraction Layer:** [llm_provider_abstraction.md](llm_provider_abstraction.md), [ADR-0013](adr/0013-llm-provider-abstraction-layer.md).
- **LLM Invocation Runtime:** [llm_invocation_runtime.md](llm_invocation_runtime.md), [ADR-0014](adr/0014-llm-invocation-runtime.md).
- **Engineering Response:** [engineering_response.md](engineering_response.md), [ADR-0015](adr/0015-engineering-response-foundation.md).
- **Engineering Session:** [engineering_session.md](engineering_session.md), [ADR-0016](adr/0016-engineering-session-foundation.md).
- **Conversation:** [conversation.md](conversation.md), [ADR-0017](adr/0017-conversation-foundation.md).
