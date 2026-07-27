# SubstationOS — Product Development Plan

**Status:** Official long-term roadmap. Living document — updated as
milestones complete and as architecture understanding improves.
**Authority:** This plan is subordinate to, and must remain consistent
with, `CLAUDE.md` and Architecture Freeze v1.0 (`docs/architecture/`,
including all ADRs under `docs/architecture/adr/`). Where this plan and
those documents appear to disagree, the architecture documents win — this
plan should be corrected, not the other way around.
**Companion documents:** `PRODUCT_VISION.md` (mission and long-range
product narrative), `CLAUDE.md` (engineering manual), `docs/architecture/`
(binding architecture and ADRs).

---

## Vision

SubstationOS is a Project Intelligence Platform for high-voltage and
medium-voltage substations: it turns any engineering documentation a
project produces — PDFs, DWG/DXF drawings, images, technical
specifications, functional and wiring diagrams — into a traceable,
queryable record of one real installation, built on a proprietary,
versioned Canonical Domain (the electrical vocabulary of what *can*
exist) and, for every project, a reviewed Project Knowledge Graph (what
*does* exist there, per that project's own documents). Every fact the
platform surfaces is evidence-based and traceable to a document, a page,
and a revision; AI is used only to translate natural language into
structured queries and to compose answers from facts the graph has
already returned — never to assert engineering knowledge on its own. The
product's value is the domain model and the discipline behind it, not
the underlying AI model.

---

## Current Status

SubstationOS has completed its foundation and its project-management
platform. Architecture Freeze v1.0 has been produced and is now the
binding reference for all further work; it is not, by its own explicit
verdict, a declaration that the system is production-ready — it is the
authoritative map of what is `READY`, `PARTIAL`, or open, so that every
future milestone builds on a documented, agreed foundation rather than on
assumption.

### Foundation — completed

- `CLAUDE.md` established as the binding engineering manual: Domain
  Driven Design, Ports & Adapters, the dependency rule, Python/YAML/
  testing/git conventions.
- The Canonical Domain bounded context (`app/domain/ontology/**`) is
  implemented: `AttributeDefinition` and `EquipmentDefinition` value
  objects, factories, validators, catalogs, engines, and repository
  ports, each with a full domain test suite.
- The Equipment Library exists as real, human-authored YAML data: 68
  equipment definitions across 8 categories plus a full set of shared
  attribute definitions, all discovered recursively and validated.
- The Canonical Knowledge Protocol (`knowledge/protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`)
  defines the methodology by which any raw documentation becomes trusted
  engineering knowledge: Extraction Levels 0–8, Confidence Policy, the
  `RAW`/`UNDER_REVIEW`/`APPROVED`/`REJECTED`/`SUPERSEDED` review-state
  machine, conflict resolution, and versioning rules.
- The Knowledge Extraction infrastructure (`knowledge/extraction/`) and
  the PDF processing environment (Poppler/Ghostscript tooling,
  `tools/pdf_tools/`) are designed and operational.
- A Power Transformer Knowledge Base exists as reference domain content,
  extracted under the Protocol's no-inference discipline.

### Project Platform — completed

- The Project Lifecycle foundation is implemented: `Project` now carries
  an explicit record lifecycle (`app.domain.project.project_lifecycle.ProjectLifecycleState`:
  `DRAFT` → `ACTIVE` → `ARCHIVED` → `DELETED`, soft delete only, strict
  one-step transitions), distinct from the pre-existing delivery-phase
  `ProjectStatus`.
- A `ProjectRepository` port, a SQLAlchemy adapter, and application
  services (`CreateProject`, `ActivateProject`, `ArchiveProject`,
  `RestoreProject`, `DeleteProject`, `UpdateMetadata`, `GetProject`,
  `ListProjects`) exist, following the ontology bounded context's
  reference pattern.
- ADR-0005 (explicit `PROJECT`/`CANONICAL_LIBRARY` document scope) is
  accepted and implemented: `documents.scope` is a first-class,
  enforced field, closing the ambiguity a nullable `project_id` could
  not express.
- `Project.canonical_domain_version` exists as the documented extension
  point for binding a Project to a Canonical Domain version, defaulting
  to an explicit `"unversioned"` sentinel until a real versioning scheme
  is designed.
- REST endpoints for the full lifecycle exist and are covered by 178
  passing tests across domain, infrastructure, service, and API layers.

### Architecture Freeze v1.0 — completed (as documentation, not as a
readiness declaration)

- `docs/architecture/project_intelligence_architecture.md` defines the
  full Project Intelligence pipeline: Canonical Domain → Create Project
  → Upload Documents → Document Classification → Document Indexing →
  Knowledge Extraction → Project Knowledge Graph → Semantic Query Engine
  → AI Assistant.
- Six ADRs are accepted and binding: project-centric architecture
  (0001), Engineering Index / Project Knowledge Graph separation (0002),
  Canonical Domain / Project Knowledge separation (0003), reviewed-facts-
  only in the queryable graph (0004), explicit document scope (0005,
  now implemented), and AI as an interpretation/presentation layer only
  (0006).
- `docs/architecture/ARCHITECTURE_FREEZE_V1_CHECKLIST.md` records the
  honest, verifiable state of every architectural requirement against
  the repository. Its own verdict, as of this plan: **NOT READY for
  Architecture Freeze v1.0** as a production declaration — no checklist
  item is `BLOCKED` any longer, but most remain `PARTIAL`, with the
  mandatory review gate violation (checklist item 5) the single
  highest-priority open gap.

### Current implementation maturity

| Layer | Maturity |
|---|---|
| Canonical Domain (ontology) | Mature — implemented, tested, versioned by git |
| Project Platform (lifecycle, scope) | Mature — implemented, tested |
| Document Repository | Functional — upload/storage/scope work; classification unpopulated |
| Engineering Index | Implemented — idempotent, project-scoped, document-traceable (Milestones 9, 9.1) |
| Review Workflow | Implemented — `ProposedClaim`/`ReviewCandidate` state machine; the ADR-0004 mandatory review gate is closed for this pipeline (Milestone 10) |
| Canonicalization | Implemented — deterministic normalization of `APPROVED` claims into `CanonicalFact`s (Milestone 11) |
| Project Knowledge Graph | Implemented — Graph Builder translates facts into operations, Graph Persistence executes them atomically and idempotently against a project-scoped SQL-backed store (Milestones 11.1, 11.2, ADR-0007); schema lifecycle is now Alembic-managed rather than `create_all()` (Milestone 12, ADR-0008); the legacy `ingest_document`/`ProjectEntity`/`EntityRelation` path is retained, isolated, and marked deprecated rather than merged or deleted (Milestone 12, ADR-0009) |
| Graph Query | Implemented — deterministic, read-only queries (by id, by type, by attribute presence, 1-hop adjacency, statistics, orphan detection) over current graph state through its own read port (Milestone 11.3); NL interpretation, semantic ranking, and answer generation are not yet built (see [knowledge_pipeline_overview.md](../architecture/knowledge_pipeline_overview.md)) |
| Structured Retrieval | Implemented — deterministic, explainable `KnowledgeCandidate` ranking from structured criteria (entity lookup, entity type, attribute, relationship, lexical, combined) over Graph Query's read model, with fixed scoring weights and deterministic candidate identity (Milestone 13, ADR-0010); no embeddings, vector search, or NL interpretation |
| Context Builder | Implemented — deterministic, bounded, provenance-aware `ContextPackage` assembly (selection, aggregation, coverage, budget enforcement, warnings, statistics, metadata) from a `KnowledgeCandidateCollection` (Milestone 14, ADR-0011); no persistence, no AI, no prompt generation |
| Prompt Builder | Implemented — deterministic, provider-independent `PromptPackage` composition (nine fixed-order sections, versioned constraints/instructions, approximate token estimates, statistics, self-validation) from a `ContextPackage` (Milestone 15, ADR-0012); no persistence, no AI, no provider serialization |
| LLM Provider Abstraction Layer | Implemented — provider-neutral `LLMProviderPort`/`LLMRequest` contract, deterministic `PromptPackage` → `LLMRequest` mapping, an Anthropic adapter (zero SDK dependency) and a fake test adapter, an explicit provider registry, runtime-configured provider/model selection (Milestone 16, ADR-0013); no invocation, no network call, no persistence |
| LLM Invocation Runtime | Implemented — attempt/retry/deadline/cancellation-governed execution of a real Anthropic call, provider-neutral `LLMResponseEnvelope` normalization, disabled by default (Milestone 17, ADR-0014); no automated test calls a real provider; no persistence, no streaming, no conversation memory |
| AI Assistant | Does not exist |
| Web frontend | Early — project listing/detail pages exist (`apps/frontend`), no auth, no review UI |
| Enterprise capabilities (RBAC, audit, monitoring, backup) | Do not exist |

---

## Product Principles

These restate, for planning purposes, the binding principles already
established in `CLAUDE.md` and Architecture Freeze v1.0's ADRs. They are
not re-decided here; see the cited source for the authoritative
statement of each.

- **Project-centric.** Every fact, document, index entry, and graph node
  belongs to exactly one Project, identified by its stable `code`; no
  component may hardcode a specific project's identity (ADR-0001).
- **Canonical Domain is immutable from project scope.** Project-level
  extraction may only reference existing Canonical Domain concepts by
  `id`; extending the vocabulary is a separate, deliberate,
  human-governed process (ADR-0003, `CLAUDE.md` §7).
- **Engineering knowledge before AI.** AI produces candidates and
  translations, never asserted facts; a fact becomes knowledge only
  through the Canonical Knowledge Protocol's methodology (ADR-0006).
- **Review before approval.** Nothing unreviewed may reach the queryable
  Project Knowledge Graph (ADR-0004); the Engineering Index exists
  precisely so browsability does not require bypassing this rule
  (ADR-0002).
- **Evidence-based answers.** An answer with no supporting graph data
  states that no record exists — it is never a plausible guess
  (ADR-0006).
- **Traceability.** Every fact must be able to answer Project, Document,
  Drawing, Page, Revision, and Confidence on demand, or it is not
  eligible to be surfaced (architecture doc §9).
- **AI replaceability.** Every AI touchpoint sits behind the
  `AIProvider` port (`app/services/ai/base.py`); the model or provider
  is a swappable adapter, never a hard dependency (`CLAUDE.md` §3).
- **Scalability without redesign.** Thousands of projects, millions of
  facts, future document types, future AI models, and future
  disciplines must be absorbed as new *content*, never new *shape*
  (architecture doc §10).
- **Enterprise-first.** Built for utilities, TSOs, DSOs, and EPC
  contractors over a multi-year lifespan: auditability, data integrity,
  reproducibility, and long-term clarity outrank short-term speed
  (`CLAUDE.md` §16).

---

## Product Architecture

The current and target architecture are fully specified in
`docs/architecture/project_intelligence_architecture.md` (the pipeline,
component responsibilities, and architecture diagram) and in the ADRs
under `docs/architecture/adr/`. This plan does not restate that content
— it is referenced, not duplicated, so that architecture always has one
source of truth. In summary, the architecture is layered as:

```
Canonical Domain  →  Project  →  Document Repository  →
Document Classification  →  Document Indexing (Engineering Index)  →
Knowledge Extraction (Canonical Knowledge Protocol)  →
Project Knowledge Graph  →  Semantic Query Engine  →  AI Assistant
```

with Domain Driven Design and Ports & Adapters (`CLAUDE.md` §3–§4)
governing every layer's internal structure, and the ontology bounded
context (`app/domain/ontology/**`) — now joined by the project bounded
context (`app/domain/project/**`) — serving as the reference pattern
every future bounded context must imitate.

---

## Development Strategy

SubstationOS is organized into EPICs rather than a flat feature list
because the architecture itself is layered, and building out of order
produces exactly the kind of accidental complexity `CLAUDE.md` forbids —
an AI Assistant with no reviewed graph to query, or a review UI with no
review-state field to render, is work that would have to be redone. Each
EPIC corresponds to one layer of the architecture becoming real:

- **Foundation** (EPIC 1). The Canonical Domain, the engineering manual,
  and the methodology (Canonical Knowledge Protocol) that governs every
  later layer. Nothing else can be built correctly before this exists,
  because every later layer either instantiates this vocabulary or is
  governed by this methodology.
- **Core Platform** (EPICs 2–4). The project-scoped backbone: the
  Project itself as a boundary and lifecycle, then the pipeline that
  turns a project's documents into reviewed, traceable, queryable
  knowledge (Engineering Index, Review Workflow, Knowledge Graph,
  Traceability), then the engine that answers questions against that
  knowledge. This is the platform's actual value — everything above it
  is presentation, and everything below it is vocabulary.
- **Application Layer** (EPICs 5–6). The user-facing and AI-facing
  surfaces built on top of the Core Platform: the AI Assistant and its
  prompt/model infrastructure, and the web platform (authentication,
  workspace, document viewer, review UI, dashboard) that makes the
  platform usable by engineers day to day.
- **Enterprise Layer** (EPIC 7). What turns a working platform into
  software a utility, TSO, DSO, or EPC contractor can actually deploy
  and depend on for years: access control, audit, monitoring, backup,
  and performance validation, per `CLAUDE.md` §16's enterprise
  guidelines.

Multi-domain expansion (EPIC 8) is deliberately not part of this
layering — it is an orthogonal axis (new Canonical Domain content for a
new discipline) that can begin once the Core Platform has proven itself
on HV/MV substations, without waiting for the full Application or
Enterprise layers to complete first.

---

## Official Roadmap

### EPIC 1 — Foundation

**Status:** Completed

- **Goal:** Establish the engineering manual, the Canonical Domain
  bounded context, the Equipment Library, and the methodology
  (Canonical Knowledge Protocol) that every later layer depends on.
- **Dependencies:** None — this is the root of the dependency graph.
- **Completion criteria:** `CLAUDE.md` binding and followed; Canonical
  Domain implemented with full domain test coverage; Equipment Library
  populated and validated; Canonical Knowledge Protocol fully specified.
- **Expected deliverables:** `CLAUDE.md`; `app/domain/ontology/**`;
  `app/domain/ontology/equipment_definitions/**` (68 definitions);
  `knowledge/protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`;
  `knowledge/extraction/**`; PDF processing tooling.
- **Implementation maturity:** Mature. All delivered, tested, and in
  active use by later work.

### EPIC 2 — Project Platform

**Status:** Completed

- **Goal:** Make the Project a real, governed boundary with an explicit
  record lifecycle, and make document ownership (`PROJECT` versus
  `CANONICAL_LIBRARY`) explicit rather than inferred.
- **Dependencies:** EPIC 1 (the Canonical Domain a Project will
  eventually bind a version of).
- **Completion criteria:** Project Lifecycle state machine implemented
  and enforced; ADR-0005 accepted and implemented; Project application
  services and REST API in place; full test coverage across domain,
  infrastructure, service, and API layers.
- **Expected deliverables:** `app/domain/project/**`;
  `app/infrastructure/project/**`; `app/services/project_service.py`;
  lifecycle-aware `app/routers/projects.py` and `app/routers/documents.py`;
  `tests/domain`, `tests/infrastructure`, `tests/services`, `tests/api`
  coverage for the Project bounded context.
- **Implementation maturity:** Mature. Delivered and tested this
  milestone; the one deliberate gap (no schema migration tooling — new
  columns need `create_all()` against a fresh database) is tracked under
  Technical Debt.

### EPIC 3 — Project Intelligence

**Scope:** Engineering Index, Review Workflow, Knowledge Graph,
Traceability Engine.

**Status:** In Progress

- **Goal:** Close the architecture's single most important open gap —
  today, AI-extracted facts are written directly into queryable storage
  with no review gate (a live violation of ADR-0004) — by building the
  Engineering Index as the landing zone for unreviewed extraction, a
  real review workflow, a properly versioned Project Knowledge Graph
  fed only by approved facts, and the full Traceability metadata the
  architecture requires.
- **Dependencies:** EPIC 1 (Canonical Domain, Canonical Knowledge
  Protocol), EPIC 2 (Project as the scoping boundary every index entry,
  fact, and graph node belongs to).
- **Completion criteria:** `ingest_document` no longer writes directly
  into `ProjectEntity`/`EntityRelation`; the Engineering Index exists
  and is populated on upload; every graph node/edge carries a review
  state, reviewer, and review date; every fact can answer all six
  Traceability fields (architecture doc §9) on demand; Architecture
  Freeze Checklist items 4, 5, and 6 move to `READY`.
- **Delivered so far:** `app/domain/engineering_index/**` (Engineering
  Index, with idempotent replace/clear hardening); `app/domain/proposed_claims/**`
  and `app/domain/review_workflow/**` (the mandatory review gate —
  `ProposedClaim`s reviewed via `ReviewCandidate`s through a
  `PENDING`/`APPROVED`/`REJECTED`/`NEEDS_CHANGES` state machine, closing
  the ADR-0004 violation this EPIC's Goal names); `app/domain/canonicalization/**`
  (deterministic entity/predicate/attribute normalization of `APPROVED`
  claims into `CanonicalFact`s, idempotent by review candidate);
  `app/domain/graph_builder/**` (translates `CanonicalFact`s into a
  deterministic, deduplicated `GraphOperationBatch` — no persistence,
  no database); `app/domain/project_knowledge_graph/**` (executes a
  batch atomically against a project-scoped graph, idempotent by a
  deterministic content fingerprint, via a database-agnostic
  `GraphStore` port with a SQL reference adapter — ADR-0007).
- **Not yet delivered:** Document Classification (nothing populates
  `Document.category` yet, so indexing still runs unclassified); the
  remaining Mandatory Metadata fields (Drawing Number, Discipline,
  per-fact Page, Extraction Session, Canonical Version); the Canonical
  Domain versioning *scheme* itself (`Project.canonical_domain_version`
  is a real field, still holding only the `"unversioned"` sentinel);
  deterministic graph queries and inspection (Milestone 11.3).
- **Implementation maturity:** Substantially built. Every stage from
  "engineer approves a claim" through "that fact exists as queryable
  graph state" now works end-to-end, backed by a SQL reference store;
  the review gate itself has been fully closed. What remains is
  Traceability metadata completeness, Canonical Domain versioning, and
  the query layer on top of the graph this EPIC now actually has.

### EPIC 4 — Engineering Query Engine

**Scope:** Semantic Queries, Evidence Collection, Structured Query
Services.

**Status:** Planned

- **Goal:** Answer natural-language questions about one project by
  querying the (by then review-gated) Project Knowledge Graph, never by
  asking an LLM to recall or guess, and expose the same capability as a
  structured API for programmatic/enterprise consumers.
- **Dependencies:** EPIC 3 (a trustworthy, versioned, traceable graph to
  query — this EPIC has nothing to query correctly before EPIC 3
  completes).
- **Completion criteria:** The interpret → identify project → query
  graph → collect documents → generate answer workflow
  (architecture doc §8) is implemented end to end; every answer carries
  its full Traceability record; a query with no supporting graph data
  returns an explicit "no such record" result, never a guess.
- **Expected deliverables:** Query-interpretation and answer-generation
  AI adapters (behind `AIProvider`); a Semantic Query Engine service;
  a structured query API for tools other than the conversational
  Assistant.
- **Implementation maturity:** Not started. The query/read layer
  (`app/routers/knowledge_graph.py`) exists as a foundation to build on;
  interpretation and generation do not exist.

### EPIC 5 — AI Platform

**Scope:** AI Assistant, Prompt Orchestration, Multi-model, Reasoning.

**Status:** Planned

- **Goal:** Provide the conversational, user-facing surface over the
  Query Engine, with a prompt infrastructure disciplined enough to
  enforce ADR-0006 (translate or compose, never assert) by construction,
  and support for more than one underlying AI model/provider.
- **Dependencies:** EPIC 4 (a working Query Engine to sit in front of).
- **Completion criteria:** AI Assistant answers are indistinguishable in
  trust guarantees from a direct graph query — same Traceability record,
  same "no data" behavior; at least a second `AIProvider` adapter exists
  alongside the current Claude adapter, proving replaceability rather
  than merely designing for it.
- **Expected deliverables:** AI Assistant conversational service;
  versioned, testable prompt templates; a second `AIProvider`
  implementation; a model-selection/fallback mechanism.
- **Implementation maturity:** Not started. The `AIProvider` port and
  one adapter (`app/services/ai/claude_provider.py`) already exist and
  are the foundation this EPIC extends, not replaces.

### EPIC 6 — Web Platform

**Scope:** Authentication, Workspace, Document Viewer, Review UI,
Dashboard.

**Status:** Planned

- **Goal:** Make the platform directly usable by engineers: sign in,
  work within a Project's workspace, view uploaded documents alongside
  extracted facts, review and approve/reject candidate facts, and see a
  project's health/readiness at a glance.
- **Dependencies:** EPIC 2 (Project as the workspace boundary), EPIC 3
  (a Review Workflow for the Review UI to operate), EPIC 4/5 (a Query
  Engine/Assistant for the workspace to surface answers from).
- **Completion criteria:** An engineer can authenticate, select a
  project, upload and view a document, review and act on candidate
  facts, and ask a question — all without touching the API directly.
- **Expected deliverables:** Authentication and session management;
  workspace/project navigation (extending the existing
  `apps/frontend/app/projects/**` pages); a document viewer; a Review
  UI backed by EPIC 3's review-state fields; a project dashboard
  building on `app/services/project_intelligence.py`.
- **Implementation maturity:** Early. `apps/frontend` already has
  project listing/creation/detail pages with no authentication and no
  review capability — a real starting point, not a greenfield build.

### EPIC 7 — Enterprise

**Scope:** RBAC, Audit, Monitoring, Backup, Performance.

**Status:** Planned

- **Goal:** Meet `CLAUDE.md` §16's enterprise guidelines in practice —
  least-privilege access, a reconstructable audit trail, observable
  failure modes, tested recovery, and validated scalability — so the
  platform is something a utility or TSO can actually deploy and depend
  on for years, not just a working demo.
- **Dependencies:** EPICs 2–6 (there is nothing meaningful to control
  access to, audit, monitor, or back up until the platform they secure
  exists).
- **Completion criteria:** Role-based access control enforced on every
  endpoint; every state-changing action is reconstructable from an audit
  log; key metrics (query latency, extraction throughput, review
  backlog) are observable; backup/restore is tested, not assumed;
  the five Scalability requirements (architecture doc §10) are
  load-tested, not just designed.
- **Expected deliverables:** RBAC middleware/policy layer; audit log
  storage and query; monitoring/alerting integration; backup/restore
  runbooks and automation; a formal schema migration tool (replacing
  today's `create_all()`-only bootstrap); a load-test suite.
- **Implementation maturity:** Not started. No authentication,
  authorization, audit, monitoring, or backup mechanism exists in the
  repository today.

### EPIC 8 — Multi-domain Expansion

**Scope:** Industrial Plants, Transmission, Rail, Renewables.

**Status:** Future

- **Goal:** Prove the Canonical Domain's discipline-neutral design
  (architecture doc §2, §10) by extending it with a second engineering
  discipline's `EquipmentDefinition`/`AttributeDefinition` concepts,
  without modifying Document Classification, the Engineering Index, the
  Knowledge Graph's shape, or the Query Engine.
- **Dependencies:** EPICs 1–4 at minimum (a Core Platform mature enough
  that a second discipline is genuinely a content change, not an
  architecture change — this EPIC is the test of that claim, not a
  precondition for it).
- **Completion criteria:** A second discipline's Canonical Domain
  content exists, is used by at least one real or representative
  project, and required zero changes to any component above the
  Canonical Domain layer.
- **Expected deliverables:** New `EquipmentDefinition`/
  `AttributeDefinition` YAML sets per discipline; discipline-specific
  extraction prompts where needed; a written record (ADR or note) of
  any Project-level field found to be discipline-specific (see
  `voltage_level`, already flagged in
  `project_intelligence_architecture.md` §2) and how it was resolved.
- **Implementation maturity:** Not started, and deliberately not
  scheduled until the Core Platform (EPICs 3–4) is proven on the
  current discipline.

---

## Milestone Planning

Numbering continues from the existing milestone references in
`project_intelligence_architecture.md` (Project Creation Workflow was
already tracked there as "Milestone 8," now complete as EPIC 2).
Milestones are grouped by EPIC; within an EPIC, order reflects real
dependency, not just narrative convenience. Duration estimates assume
one focused engineering effort at a time, not calendar time with
interruptions, and are ranges, not commitments.

### EPIC 3 — Project Intelligence

**Milestone 9 — Engineering Index** — *Completed*
- Objective: build the fast, unreviewed, per-document inventory of
  candidate mentions (ADR-0002) as a new bounded context.
- Delivered: `app/domain/engineering_index/**` +
  `app/infrastructure/engineering_index/**`; entries registered per
  document/project, `PROJECT`-scope-only (ADR-0005), lifecycle-mutability
  guarded.
- Architecture impact: none — implemented ADR-0002 and architecture doc
  §5 as designed.
- Deferred out of this milestone (unchanged): Document Classification
  still does not populate `Document.category`; indexing still runs
  unclassified.

**Milestone 9.1 — Engineering Index Hardening** — *Completed*
- Objective: make the Index actually satisfy ADR-0002's "freely
  rebuildable, idempotent" properties in practice, not just in
  principle.
- Delivered: atomic per-document replace/clear operations, a
  database-enforced idempotency/uniqueness safety net, and a typed
  source-locator abstraction (page, sheet, cell range, drawing layout,
  ...) so indexing is not conceptually restricted to PDF pages.
- Architecture impact: none — hardening of Milestone 9's own contract.

**Milestone 10 — Mandatory Review Gate Closure** — *Completed*
- Objective: stop unreviewed extraction output from reaching queryable
  graph storage; route it through a real review-state machine first.
  Closes the ADR-0004 violation.
- Delivered: `app/domain/proposed_claims/**` (a `ProposedClaim` —
  subject/predicate/object, cited evidence from the Engineering Index)
  and `app/domain/review_workflow/**` (a `ReviewCandidate` per claim,
  moving through `PENDING`/`APPROVED`/`REJECTED`/`NEEDS_CHANGES`, with
  an append-only review history ledger). Nothing reaches the Project
  Knowledge Graph without first being an `APPROVED` `ReviewCandidate`.
- Architecture impact: none — implements an already-accepted decision
  (ADR-0004), reshaped once (Milestone 10.1) so Review Workflow reviews
  Proposed Claims rather than raw Engineering Index entries directly,
  since one claim can be built from more than one entry.

**Milestone 11 — Canonicalization Pipeline** — *Completed*
- Objective: convert `APPROVED` Proposed Claims into canonical
  engineering facts — deterministic entity/predicate/attribute
  normalization, no AI, no fuzzy matching.
- Delivered: `app/domain/canonicalization/**` — `CanonicalEntityReference`/
  `CanonicalPredicate`/`CanonicalAttribute`/`CanonicalValue` built from
  small, explicit, documented normalization tables; a `CanonicalFact`
  per approved candidate, idempotent by review candidate id (re-running
  never duplicates a fact).
- Architecture impact: none — implements ADR-0002's second layer.
  Canonicalization does not yet reference the real Canonical Domain
  (`app/domain/ontology/**`) for entity-type recognition; its
  vocabulary is self-contained and provisional (see Technical Debt).
- Implementation impact: `CanonicalFact` persists no graph identifier
  and no graph edge — it is an intermediate object the next milestone
  consumes, not the graph itself.

**Milestone 11.1 — Graph Builder** — *Completed*
- Objective: translate `CanonicalFact`s into deterministic graph
  mutation instructions, with no persistence and no database of any
  kind.
- Delivered: `app/domain/graph_builder/**` — `GraphEntityId`/
  `GraphRelationshipType` built exclusively from Canonicalization's own
  types; `CREATE_NODE`/`UPDATE_NODE`/`CREATE_RELATIONSHIP` operations
  assembled into a deterministically ordered, deduplicated
  `GraphOperationBatch`, itself persisted as Graph Builder's own output
  artifact (not graph persistence).
- Architecture impact: none.

**Milestone 11.2 — Project Knowledge Graph Persistence** — *Completed*
- Objective: execute a persisted `GraphOperationBatch` against an
  actual project-scoped graph, atomically and idempotently, behind a
  database-agnostic port.
- Delivered: `app/domain/project_knowledge_graph/**` — a `GraphStore`
  port with a SQL reference adapter (`project_graph_nodes`/
  `project_graph_relationships`; natural-key identity, no surrogate-id
  dependence); atomic batch execution via a `GraphUnitOfWork` seam;
  idempotent retries via a deterministic batch content fingerprint
  (`ADR-0007`). Neo4j and every other native graph technology are
  deliberately deferred — see ADR-0007.
- Architecture impact: **new ADR (0007)** — Graph Builder vs. Graph
  Persistence separation, project-scoped graph identity, the
  database-agnostic `GraphStore` port, and why Neo4j is deferred.
- Contract defect found and fixed in Milestone 11.1's own service (not
  its domain semantics): a project-scoped `GraphOperationBatch` built
  for a project with zero Canonical Facts lost its `project_id`
  (`GraphOperationBatchFactory.build` can only infer a project from its
  facts), making a freshly created project's batch permanently
  un-executable. Fixed by having `build_batch_for_project` supply its
  already-known, already-validated `project_id` when the factory
  cannot infer one — not a change to the factory's tested logic.

**Milestone 11.3 — Knowledge Graph Query Foundation** — *Completed*
- Objective: deterministic project graph queries and inspection
  semantics on top of the now-real graph state — still no LLM, no
  semantic/vector search.
- Delivered: `app/domain/graph_query/**` — a `GraphQueryRepository`
  read port (never `GraphStore`, the write-side port) with a
  SQLAlchemy adapter; node/relationship lookups by id and by type,
  attribute-presence filtering, 1-hop neighborhood queries
  (`GraphQueryValidator` hard-rejects any other depth), orphan
  detection, and project-wide statistics — every query deterministic
  and exact, no ranking or NL interpretation of any kind.
- Architecture impact: none — implements the read side of ADR-0007's
  already-accepted design.
- Dependencies: Milestone 11.2 (a persisted, queryable graph to build
  on).

**Milestone 12 — Knowledge Platform Hardening** — *Completed*
- Objective: harden the completed deterministic pipeline (Documents →
  Engineering Index → Proposed Claims → Review Workflow →
  Canonicalization → Graph Builder → Project Knowledge Graph → Graph
  Query) — database lifecycle, bounded-context governance, legacy-path
  isolation, transaction consistency, API consistency, performance
  visibility, operational reliability — with no new product
  functionality. Not part of the original plan below; inserted as an
  unplanned hardening pass once EPIC 3's pipeline reached its first
  fully-queryable state (Milestone 11.3).
- Delivered: Alembic-managed schema lifecycle replacing
  `create_all()` (ADR-0008); the legacy Knowledge Graph path marked
  deprecated, isolated, and proven never imported by the governed
  graph path (ADR-0009); a documented repository transaction
  convention (`repository_transaction_conventions.md`) plus a
  real-database regression test proving Project Knowledge Graph
  execution atomicity; an OpenAPI integrity test suite; a lightweight,
  `ast`-based bounded-context dependency architecture test; a
  synthetic-data performance baseline for the graph write/read paths
  (`performance_baseline.md`); an `.env.example` and an operational
  reliability review (`operational_reliability.md`); this document's
  own knowledge-pipeline overview
  (`knowledge_pipeline_overview.md`).
- Architecture impact: **two new ADRs** (0008, 0009). No existing ADR
  superseded, no bounded context renamed or merged, no new product
  behavior.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 12" for
  Traceability Metadata Completion. That entry's number is left
  unchanged here rather than cascading a renumber through every
  subsequent milestone (13–17) — a large, purely cosmetic rewrite this
  hardening pass deliberately avoided. Whoever schedules Traceability
  Metadata Completion next should assign it the next free number at
  that time.
- Dependencies: Milestone 11.3 (a complete, queryable pipeline to
  harden).

**Milestone 12 — Traceability Metadata Completion**
- Objective: make every graph fact able to answer all six Traceability
  fields (Project, Document, Drawing, Page, Revision, Confidence) on
  demand.
- Expected duration: 1–2 weeks.
- Dependencies: Milestone 11.2 (a graph structure to attach the
  remaining fields to).
- Architecture impact: none — implements architecture doc §9 and
  Protocol §4's Mandatory Metadata, already fully specified.
- Implementation impact: add Drawing Number, Discipline, per-fact Page,
  Extraction Session, Reviewer, and Review Date fields wherever the
  Mandatory Metadata schema requires them.

**Milestone 13 — Canonical Domain Versioning Scheme**
- Objective: decide and implement how `app/domain/ontology/**` itself is
  versioned, so `Project.canonical_domain_version` (already a field,
  currently only a sentinel) can hold real, meaningful values.
- Expected duration: 1 week design (ADR) + 1 week implementation.
- Dependencies: none technically, but should precede or accompany
  Milestone 11 so newly canonicalized facts can cite a real version.
- Architecture impact: **requires a new ADR** — this is a genuinely
  open decision (semantic version, git tag, dated release, or another
  scheme), not yet resolved by any existing ADR.
- Implementation impact: a version-stamping mechanism for
  `app/domain/ontology/**`; `Project` creation begins recording real
  values instead of the `"unversioned"` sentinel.

### EPIC 4 — Engineering Query Engine

**Milestone 13 — Structured Retrieval Foundation** — *Completed*
- Objective: the first retrieval capability over the governed knowledge
  pipeline — deterministic, explainable `KnowledgeCandidate`s from
  structured (non-NL) criteria, consumable by a future frontend and a
  future Context Builder. No LLM, no embeddings, no vector database,
  no natural-language interpretation.
- Delivered: `app/domain/structured_retrieval/**` — six retrieval
  modes (`ENTITY_LOOKUP`, `ENTITY_TYPE_SEARCH`, `ATTRIBUTE_SEARCH`,
  `RELATIONSHIP_SEARCH`, `LEXICAL_SEARCH`, `COMBINED`); deterministic
  query planning, candidate construction, deduplication/aggregation,
  and a fixed, documented scoring policy; deterministic candidate
  identity (no random UUIDs); `POST /projects/{id}/structured-retrieval/plan`
  and `.../search`. Consumes Graph Query exclusively (`GraphQueryRepository`/
  `graph_query_service`) — never `GraphStore`, never the legacy
  Knowledge Graph path. Graph Query's own read model was extended with
  `created_by_execution_id`/`updated_by_execution_id` (previously
  persisted but not projected) so candidates can carry honest
  execution-provenance identifiers.
- Architecture impact: **new ADR (0010)** — why retrieval operates on
  governed graph state rather than raw chunks, why the first
  implementation is deterministic, why embeddings are deferred, and
  the Graph Query → Structured Retrieval → Context Builder → AI
  Assistant layering.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 13" for Canonical
  Domain Versioning Scheme (EPIC 3). That entry's number is left
  unchanged here, for the same reason Milestone 12's numbering
  collision was left unchanged rather than cascade-renumbering
  subsequent milestones — see that milestone's own numbering note.
- Dependencies: Milestone 12 (a hardened, tested Graph Query read
  model to build on).

**Milestone 14 — Context Builder Foundation** — *Completed*
- Objective: the official, AI-independent contract between the
  deterministic knowledge platform and every future AI capability —
  transform a `KnowledgeCandidateCollection` into a bounded,
  structured, explainable `ContextPackage`. No LLM, no prompt
  generation, no embeddings, no semantic ranking.
- Delivered: `app/domain/context_builder/**` — deterministic Selection
  (re-derives Structured Retrieval's own documented ordering convention
  from public `KnowledgeCandidate` fields, since `sort_key` itself is
  never exposed on the wire), Aggregation into per-kind
  `ContextSection`s, Coverage Analysis (`CoverageReport`: entity/
  relationship/attribute coverage, candidate utilization, an overall
  completeness figure — selection completeness, never an invented
  engineering-confidence score), and Budget Enforcement across six
  independently tracked dimensions (candidates, entities,
  relationships, attributes, metadata entries, warnings), each reported
  as `requested`/`accepted`/`discarded`/`utilization`; a fixed-priority,
  budget-capped structured warning generator (budget exceeded, missing
  provenance, missing attributes/relationships, partial coverage,
  candidate discarded); versioned `ContextStatistics`/`ContextMetadata`;
  `POST /projects/{id}/context-builder/build`. Consumes Structured
  Retrieval's own `KnowledgeCandidateCollection`/`KnowledgeCandidate`
  types exclusively — never calls Graph Query, Structured Retrieval,
  a database, or an AI provider itself (enforced by dedicated
  architecture tests, the same discipline Milestone 13 established for
  its own boundaries).
- Architecture impact: **new ADR (0011)** — why Context Builder is a
  dedicated bounded context rather than logic folded into Structured
  Retrieval or a future Prompt Builder, why it owns budget and
  coverage, and why a future Prompt Builder must consume
  `ContextPackage` rather than duplicate this logic.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 14" for Semantic
  Query Engine (EPIC 4). That entry's number is left unchanged here,
  for the same reason Milestone 12's and 13's numbering collisions were
  left unchanged rather than cascade-renumbering subsequent milestones
  — see those milestones' own numbering notes.
- Dependencies: Milestone 13 (a ranked, explainable
  `KnowledgeCandidateCollection` to assemble into a package).

**Milestone 15 — Prompt Builder Foundation** — *Completed*
- Objective: the official, provider-independent contract every future
  LLM adapter consumes — transform a `ContextPackage` into a bounded,
  deterministic, explainable `PromptPackage`. No LLM invocation, no
  provider SDK, no provider-specific message serialization. Distinct
  from the later-planned "Milestone 18 — Prompt Orchestration
  Framework" (EPIC 5): that milestone governs and versions *every*
  prompt in the system (extraction, classification, interpretation,
  generation); this one is the single, specific, deterministic
  ContextPackage → PromptPackage transform for the engineering-Q&A
  path this EPIC's own pipeline builds toward.
- Delivered: `app/domain/prompt_builder/**` — nine fixed-order
  `PromptSection`s (`SYSTEM_CONTEXT`, `ENGINEERING_CONTEXT`,
  `SELECTED_KNOWLEDGE`, `EVIDENCE_REFERENCES`, `CONSTRAINTS`,
  `FORMATTING_RULES`, `EXPECTED_OUTPUT`, `WARNINGS`, `METADATA`), each
  built by exactly one small, named, pure composition function - never
  free-form string concatenation; a fixed, versioned policy of five
  `PromptConstraint`s (truthfulness) and three `PromptInstruction`s
  (formatting), always present regardless of package content; a
  documented, deliberately approximate, provider-independent token
  estimate (~4 characters per token - never a real, provider-specific
  tokenizer); versioned `PromptStatistics`/`PromptMetadata`/
  `PromptVersion`; a self-validating `PromptValidationResult` proving
  every assembled package's structural invariants hold;
  `POST /projects/{id}/prompt-builder/build`. Consumes Context
  Builder's own `ContextPackage` exclusively — never calls Graph
  Query, Structured Retrieval, Context Builder, a database, or an AI
  provider itself (enforced by dedicated architecture tests, the same
  discipline Milestones 13-14 established for their own boundaries).
- Architecture impact: **new ADR (0012)** — why `PromptPackage` exists
  as a dedicated, provider-independent artifact, why provider
  serialization is explicitly excluded from this milestone, why Prompt
  Builder owns composition, and why the future LLM Provider
  Abstraction Layer must consume `PromptPackage` rather than duplicate
  this logic.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 15" for Evidence
  Collection & Answer Composition (EPIC 4). That entry's number is left
  unchanged here, for the same reason Milestones 12-14's numbering
  collisions were left unchanged rather than cascade-renumbering
  subsequent milestones — see those milestones' own numbering notes.
- Dependencies: Milestone 14 (a bounded, provenance-aware
  `ContextPackage` to compose into a prompt).

**Milestone 16 — LLM Provider Abstraction Layer** — *Completed*
- Objective: a stable, provider-neutral seam between `PromptPackage`
  and external AI providers - no invocation, no network call, request
  preparation only. Anthropic Claude is the first production-oriented
  adapter (this project's intended first deployment choice), never the
  platform's architectural identity. Distinct from the later-planned
  "Milestone 19 — Multi-model & Reasoning" (EPIC 5): that milestone adds
  a second adapter to the pre-existing *legacy* `AIProvider` port
  (`app/services/ai/base.py`, used by the unreviewed `ingest_document`
  extraction path); this milestone builds an entirely new,
  provider-neutral contract for the *governed* EPIC 4 pipeline, with no
  relationship to that legacy port.
- Delivered: `app/application/**` (provider-neutral, not a new
  `app/domain/**` bounded context, per this milestone's own
  instruction) — `LLMProviderPort` (`prepare_request`/
  `validate_configuration`/`provider_capabilities`, deliberately no
  `generate`/`invoke` method yet); a provider-neutral `LLMRequest`
  contract (`LLMMessageRole`: instruction/context/user/assistant/tool;
  `LLMContentType`: text/structured_data/reference;
  `LLMGenerationParameters`; opaque, runtime-configured
  `LLMProviderSelection`/`LLMModelSelection` - no hardcoded model
  version anywhere, no static model-name list); a deterministic
  `PromptPackage` → `LLMRequest` mapper preserving section
  ordering/enabled-disabled semantics/evidence references/every
  upstream version string; a `provider_id`-keyed `LLMProviderRegistry`
  with no business logic and no automatic fallback;
  `LLMRequestPreparationService` (validates, maps, resolves the
  adapter, validates required capabilities, prepares the provider-native
  request - raises typed errors for missing/unknown/mismatched
  providers and unsupported *required* capabilities, downgrades merely
  *optional* unsupported parameters to warnings only).
  `app/infrastructure/llm/anthropic/**` — the first adapter,
  `AnthropicPreparedRequest` (a local, immutable stand-in for an
  Anthropic Messages API request - never an SDK object, never
  serialized, never sent), mapping `INSTRUCTION`-role content into
  `system` and every other role into one synthetic `role="user"`
  message (Anthropic requires at least one message; today's
  `PromptPackage` models no real end-user turn yet - a documented,
  provisional choice). Imports nothing from the `anthropic` package.
  `app/infrastructure/llm/base/fake_llm_provider_adapter.py` —
  `FakeLLMProviderAdapter`, proving genuine provider neutrality in
  tests. `POST /projects/{id}/llm/prepare-request` — inspection only,
  never calls a provider.
- Architecture impact: **new ADR (0013)** — why this is an
  application/infrastructure capability rather than a new bounded
  context, why Anthropic is an adapter and not a domain dependency, why
  `PromptPackage` != `LLMRequest` != `AnthropicPreparedRequest` != an
  SDK object != an HTTP payload, why model identifiers are runtime
  configuration, and why no provider fallback is ever automatic.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 16" for
  Structured Query Services (EPIC 4). That entry's number is left
  unchanged here, for the same reason Milestones 12-15's numbering
  collisions were left unchanged rather than cascade-renumbering
  subsequent milestones — see those milestones' own numbering notes.
- Dependencies: Milestone 15 (a deterministic, provider-independent
  `PromptPackage` to translate).

**Milestone 17 — LLM Invocation Runtime** — *Completed*
- Objective: the first milestone in this governed EPIC 4 pipeline
  allowed to perform a real external network call - evolve
  `LLMProviderPort` with an `invoke()` method and build the runtime
  that owns the full invocation lifecycle (attempt sequencing, total
  deadline, retry policy, cancellation, error normalization, response
  normalization) over exactly one real provider call per attempt.
  Distinct from the later-planned "Milestone 17 — AI Assistant"
  (EPIC 5): that milestone is the conversational, user-facing surface
  over the future Query Engine; this one is the governed execution
  path a future AI Assistant would eventually call through, alongside
  Milestone 16's own request-preparation contract - neither milestone
  builds the other.
- Delivered: `app/application/models/llm_invocation.py` — the full
  invocation domain model (`LLMInvocationRequest`/`Context`/`Policy`/
  `Result`/`Status`, `LLMResponseEnvelope`/`Content`/`Metadata`,
  `LLMProviderError`/`Category`/`Details`, `LLMRetryDecision`/`Policy`,
  `LLMTimeoutPolicy`, `LLMRuntimeConfiguration`/`Version`,
  `LLMResponseValidationResult`); `app/application/policies/llm_retry_policy.py`
  (fixed, version-stamped retryable/non-retryable classification,
  bounded exponential backoff with injectable jitter) and
  `llm_timeout_policy.py` (pure deadline-arithmetic helpers);
  `app/application/validation/llm_response_validator.py` (structural
  + secret-leak-pattern validation of every envelope);
  `app/application/services/llm_runtime.py` (`run_invocation` — the
  attempt/retry/deadline loop, the only place a retry is ever
  decided) and `llm_invocation_service.py` (`invoke_llm` —
  enablement/credential/preparation/adapter orchestration, never
  touching a real credential value, only a boolean presence flag);
  `app/application/services/llm_runtime_metrics.py` (a small,
  thread-safe, in-process, non-persisted counter set);
  `app/infrastructure/llm/anthropic/{anthropic_client,anthropic_invoker,
  anthropic_error_mapper,anthropic_response_mapper}.py` — `max_retries=0`
  on the SDK client (the runtime is the only retry authority), one
  provider call per `invoke()`, full error-category and
  content/finish-reason/usage normalization, no SDK type ever crossing
  into `app/application/**`; `FakeLLMProviderAdapter` extended with
  scripted `FakeInvocationOutcome` sequences (success, every error
  category, retry-after hints, cancellable delays) so the runtime's
  retry/timeout/cancellation behavior is fully provable with zero
  Anthropic dependency; `POST /projects/{id}/llm/invoke` — may perform
  a real call; Milestone 16's own `/prepare-request` endpoint is
  untouched and still performs zero invocation.
- Architecture impact: **new ADR (0014)** — why invocation stays an
  application/infrastructure capability rather than becoming a new
  bounded context, why the runtime (not the SDK, not the adapter) owns
  every retry decision, why SDK retries are disabled entirely, why the
  total invocation deadline is tracked separately from per-call
  connect/read timeouts, why cancellation is real `asyncio` cancellation
  never disguised as a retryable provider error, and why expected
  provider failures are returned as data rather than raised as
  exceptions.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 17" for the AI
  Assistant (EPIC 5). That entry's number is left unchanged here, for
  the same reason Milestones 12-16's numbering collisions were left
  unchanged rather than cascade-renumbering subsequent milestones —
  see those milestones' own numbering notes.
- Dependencies: Milestone 16 (a provider-neutral `LLMRequest` and a
  request-preparing Anthropic adapter to invoke).

**Milestone 14 — Semantic Query Engine**
- Objective: implement the interpret → identify project → query graph
  step of the workflow (architecture doc §8).
- Expected duration: 3–4 weeks.
- Dependencies: EPIC 3 complete (a trustworthy graph to query).
- Architecture impact: none — implements an already-designed worked
  example.
- Implementation impact: a query-interpretation `AIProvider` use
  (translate only, per ADR-0006); a structured graph query builder.

**Milestone 15 — Evidence Collection & Answer Composition**
- Objective: implement collect documents → generate answer, with the
  full Traceability record attached to every answer.
- Expected duration: 2–3 weeks.
- Dependencies: Milestone 14.
- Architecture impact: none — implements ADR-0006's "compose" role.
- Implementation impact: an answer-composition `AIProvider` use; a
  "no data found" path that is structurally forced, not a prompt
  instruction.

**Milestone 16 — Structured Query Services**
- Objective: expose the same query capability as a versioned,
  documented API for programmatic consumers (e.g. reporting tools,
  external integrations), not only the conversational Assistant.
- Expected duration: 2 weeks.
- Dependencies: Milestones 14–15.
- Architecture impact: none.
- Implementation impact: a new `app/routers/query.py`-style surface
  returning structured (not prose) results with the same Traceability
  guarantees.

### EPIC 5 — AI Platform

**Milestone 17 — AI Assistant**
- Objective: build the conversational, user-facing surface over the
  Query Engine.
- Expected duration: 3–4 weeks.
- Dependencies: EPIC 4.
- Architecture impact: none.
- Implementation impact: a conversation/session service; a chat-style
  API and (paired with EPIC 6) UI.

**Milestone 18 — Prompt Orchestration Framework**
- Objective: version, test, and govern every prompt in the system
  (extraction, classification, interpretation, generation) under one
  discipline, so ADR-0006 is enforced structurally, not by convention.
- Expected duration: 2–3 weeks.
- Dependencies: can begin alongside Milestone 17; benefits from
  Milestones 9–15 existing so real prompts exist to bring under
  governance.
- Architecture impact: none.
- Implementation impact: a prompt registry/versioning mechanism; tests
  that assert prompts never ask a model to "infer" or "estimate."

**Milestone 19 — Multi-model & Reasoning**
- Objective: add a second `AIProvider` adapter and a model-
  selection/fallback mechanism, proving replaceability rather than
  merely designing for it.
- Expected duration: 2 weeks.
- Dependencies: Milestone 18 (a governed prompt layer that is itself
  provider-agnostic).
- Architecture impact: none — implements `CLAUDE.md` §3 and ADR-0006's
  existing replaceability guarantee.
- Implementation impact: a second concrete `AIProvider`; selection
  logic (cost, latency, or task-based).

### EPIC 6 — Web Platform

**Milestone 20 — Authentication & Workspace**
- Objective: add sign-in and a project-scoped workspace shell.
- Expected duration: 2–3 weeks.
- Dependencies: EPIC 2 (Project as the workspace boundary).
- Architecture impact: none directly, but establishes the identity
  concept (`created_by`, already a `Project` field) that EPIC 7's RBAC
  and audit work will build on.
- Implementation impact: auth provider integration; session handling;
  workspace navigation extending `apps/frontend/app/projects/**`.

**Milestone 21 — Document Viewer**
- Objective: view an uploaded document (PDF at minimum) alongside its
  extracted facts and Engineering Index entries.
- Expected duration: 2–3 weeks.
- Dependencies: Milestone 20; EPIC 3 (facts/index entries to display).
- Architecture impact: none.
- Implementation impact: a document rendering component; a fact/index
  overlay keyed by page.

**Milestone 22 — Review UI**
- Objective: let an engineer review and approve/reject candidate facts
  from the Engineering Index/extraction output.
- Expected duration: 3 weeks.
- Dependencies: Milestone 10 (review-state fields to act on),
  Milestone 21 (document context for review).
- Architecture impact: none.
- Implementation impact: a review queue view; approve/reject actions
  calling Milestone 10's review service.

**Milestone 23 — Dashboard**
- Objective: surface a project's health, readiness, and review backlog
  at a glance, replacing today's document-count-only heuristic.
- Expected duration: 2 weeks.
- Dependencies: EPIC 3 (real review/graph data to summarize, not just
  document counts).
- Architecture impact: none.
- Implementation impact: rework `app/services/project_intelligence.py`
  to read from the (by then real) review and graph state.

### EPIC 7 — Enterprise

**Milestone 24 — RBAC**
- Objective: enforce role-based access control on every endpoint.
- Expected duration: 3 weeks.
- Dependencies: Milestone 20 (authenticated identity to authorize).
- Architecture impact: none — additive, sits behind existing routers.
- Implementation impact: a policy/permission layer; role assignment per
  Project or organization.

**Milestone 25 — Audit Logging**
- Objective: make every state-changing action reconstructable.
- Expected duration: 2 weeks.
- Dependencies: Milestone 24 (identity to attribute actions to).
- Architecture impact: none.
- Implementation impact: an audit log store; write hooks on every
  application service (the existing `project_service.py` functions are
  a template for where these hooks attach).

**Milestone 26 — Monitoring & Observability**
- Objective: make query latency, extraction throughput, and review
  backlog observable in production.
- Expected duration: 2 weeks.
- Dependencies: none blocking; most valuable once EPICs 3–4 exist.
- Architecture impact: none.
- Implementation impact: metrics/logging integration; dashboards
  (operational, distinct from Milestone 23's product dashboard).

**Milestone 27 — Backup & Disaster Recovery**
- Objective: tested, not assumed, backup and restore.
- Expected duration: 1–2 weeks.
- Dependencies: none blocking.
- Architecture impact: none.
- Implementation impact: backup automation; a documented, exercised
  restore runbook.

**Milestone 28 — Migration Infrastructure & Performance Hardening**
- Objective: replace `Base.metadata.create_all()`-only schema management
  with a real migration tool; load-test the five Scalability
  requirements (architecture doc §10).
- Expected duration: 2–3 weeks.
- Dependencies: none blocking, but should land before EPIC 7 is
  considered complete — see Technical Debt.
- Architecture impact: none.
- Implementation impact: adopt a migration tool (e.g. Alembic); a
  migration for every schema change made since the project began,
  including the Project Lifecycle columns added without one; a
  load-test suite exercising thousands-of-projects/millions-of-facts
  scenarios.

### EPIC 8 — Multi-domain Expansion

**Milestone 29+ — one milestone per discipline** (Industrial Plants,
Transmission, Rail, Renewables, and any future discipline)
- Objective: extend the Canonical Domain with that discipline's
  `EquipmentDefinition`/`AttributeDefinition` concepts and validate the
  Core Platform requires no shape changes to support it.
- Expected duration: 2–4 weeks per discipline, largely content
  authoring rather than engineering.
- Dependencies: EPICs 1–4 mature and proven on the current discipline.
- Architecture impact: none expected — a change here that *does*
  require architecture impact is itself the signal that EPIC 8 was
  started too early.
- Implementation impact: new YAML content under
  `app/domain/ontology/equipment_definitions/`; discipline-specific
  extraction prompts; a written note if any Project-level field turns
  out to be discipline-specific (see `voltage_level`).

---

## Technical Debt

- **Migration infrastructure.** ~~Schema changes rely entirely on
  `Base.metadata.create_all()`...~~ **Resolved in Milestone 12** —
  Alembic now manages schema lifecycle (ADR-0008); `create_all()`
  remains only for the isolated, disposable, per-test in-memory
  database. See `database_migrations.md`.
- **Engineering Index.** Does not exist. Its absence is why extraction
  currently has nowhere ungoverned to land except the graph itself —
  the root cause behind the next item. Addressed in Milestone 9.
- **Mandatory review gate (ADR-0004 violation) — legacy path only.**
  Milestone 10 closed this gap for the governed pipeline (Proposed
  Claims → Review Workflow). It remains open for the original,
  pre-existing `ingest_document` path: every document upload still
  writes AI-extracted entities and relationships directly into
  queryable graph storage (`ProjectEntity`/`EntityRelation`), with no
  review state of any kind. Milestone 12 isolated and documented this
  (ADR-0009) — marked deprecated, proven not to leak into the governed
  path — but did not remediate it; still the single highest-priority
  functional gap in the roadmap.
- **Canonical Domain versioning.** No scheme exists for versioning
  `app/domain/ontology/**` itself; `Project.canonical_domain_version`
  exists only as a documented extension point holding a sentinel value.
  Addressed in Milestone 13, and requires a new ADR.
- **Document Classification unpopulated.** `Document.category` exists
  as a field but nothing assigns it on upload — Document Classification
  (architecture doc §4) is designed but not implemented. Blocks
  Milestone 9 from being fully governed (indexing should follow
  classification, not run against an unclassified document).
- **Relationship Vocabulary and Domain Constraints.** Designed
  (architecture doc §1, ADR-0003) but not implemented as Canonical
  Domain concepts; today's `EntityRelation` rows are project-scoped
  data, not a canonical, governed vocabulary of relationship types.
- **Hardcoded topology template.** `app/services/topology/transformer_bay.py`
  encodes one specific equipment topology (a transformer bay plus three
  protection relays) as a hardcoded pattern rather than data-driven
  matching. Not project-specific hardcoding (ADR-0001 is not violated),
  but it will not generalize across EPIC 8 disciplines without rework.
- **Naive datetimes.** Domain and persistence code uses
  `datetime.utcnow()` (deprecated since Python 3.12) throughout,
  including in the Project Lifecycle's own transition methods, for
  consistency with all pre-existing timestamp columns. A deliberate,
  documented trade-off, not an oversight — but a real cleanup item once
  a natural break point exists to touch every timestamp column at once.
- **No authentication or authorization exists today.** Not "debt" in
  the rework sense — it was never built — but recorded here because
  every EPIC 3–6 milestone that writes state currently does so with no
  access control of any kind, which the Web Platform and Enterprise
  EPICs must close, not merely add to.
- **No dependency manifest.** Neither `requirements.txt` nor
  `pyproject.toml` exists anywhere in `apps/backend` — dependencies are
  installed ad hoc into `.venv`. Predates Milestone 12; noted, not
  reconstructed, during that milestone's own Alembic setup (out of
  scope: risk of mis-pinning versions not personally installed).
- **`DATABASE_URL` is not environment-driven for the running
  application.** `app/database/database.py`'s `DATABASE_URL` is a
  fixed value; only Alembic invocations can be pointed elsewhere (via
  `SUBSTATIONOS_DATABASE_URL`, Milestone 12). Making the application's
  own connection string configurable is reasonable future work but was
  not made in Milestone 12 — no defect in current single-environment
  behavior was demonstrated. See `operational_reliability.md`.
- **Graph write path has no bulk/batch upsert.** Every operation in a
  `GraphOperationBatch`, however large, costs one Python-level call and
  1–3 SQL round-trips in `SqlAlchemyGraphStore` — the dominant cost in
  Milestone 12's performance baseline (`performance_baseline.md`).
  Acceptable at current dataset sizes; the clearest candidate for a
  future, dedicated performance milestone.
- **Two Graph Query operations filter in Python after an unfiltered
  fetch.** `list_nodes_with_attribute` (attribute filtering) and
  `list_orphan_nodes` (orphan detection, also used by `get_statistics`)
  both fetch broader data than needed and filter/aggregate in Python —
  O(all nodes/relationships in project) per call. Documented as an
  algorithmic risk area in `performance_baseline.md`, not fixed, since
  no real performance problem has been demonstrated at current scale.
- **Graph Query cannot distinguish a syntactically valid but
  nonexistent entity type from a real one.** `GraphQueryValidator`
  validates entity-type strings syntactically only — Canonicalization's
  entity-type registry is private and Graph Query has no public port
  onto it. A query for a made-up type returns an empty result rather
  than an explicit error. Deliberately not fixed in Milestone 12 (see
  "Public vocabulary boundary" in `knowledge_pipeline_overview.md`) —
  low severity, no shared-vocabulary contract introduced without a
  demonstrated need.
- **Structured Retrieval's `source_fact_ids` is always empty.** A
  `GraphOperationBatch`'s per-operation `source_fact_id` is ephemeral
  at execution time and is never persisted onto the node/relationship
  row itself, so `KnowledgeCandidate.source_fact_ids` has nothing to
  report today. Represented as honestly absent, not fixed this
  milestone (would require a `GraphStore`/schema change, out of scope
  for a retrieval-layer milestone) — see ADR-0010 and
  `structured_retrieval.md`'s Provenance section.
- **Structured Retrieval's lexical matching has no substring/contains
  rule.** Only exact-token, normalized-identifier, and prefix matching
  are implemented — searching `"295"` will not find `"C-295"`. A
  deliberate, documented scope boundary (not fuzzy matching), not an
  oversight — see `structured_retrieval.md`'s Matching Rules.
- **`LEXICAL_SEARCH`/`COMBINED`/value-only `ATTRIBUTE_SEARCH` require a
  full node and/or relationship scan.** No SQL-side lexical or
  attribute-value index exists, so these modes inherit Graph Query's
  own Python-side filtering costs (see `performance_baseline.md`,
  risks 1 and 6). Acceptable at current dataset sizes; a future
  performance milestone's natural starting point alongside Graph
  Query's own risks 1–3.
- **Context Builder recomputes its own candidate ranking key rather
  than trusting `KnowledgeCandidate.sort_key`.** `sort_key` is
  Structured Retrieval's own internal ranking aid and is deliberately
  never exposed by `KnowledgeCandidateRead` (Structured Retrieval's own
  API response shape), so Context Builder's Selection stage
  independently recomputes the same, publicly documented ordering
  convention from public fields. A small, deliberate duplication of a
  *documented* convention, not of Structured Retrieval's private
  scoring internals — see ADR-0011 and `context_builder.md`'s
  Selection section.
- **Context Builder's `context_completeness` is a simple, fixed,
  equally-weighted average**, not a statistically validated model of
  "how much context is enough." Adequate for Milestone 14's own
  "explain selection, don't invent confidence" requirement; a future
  milestone could weight it differently with a documented rationale and
  a version bump, the same discipline `scoring_policy.py`'s
  `SCORING_POLICY_VERSION` already establishes for Structured
  Retrieval.
- **Prompt Builder's token estimate is a rough, provider-independent
  approximation (~4 characters per token), not a real tokenizer.**
  Every real tokenizer is provider-specific (`tiktoken` for OpenAI,
  Anthropic's own tokenizer, ...); adopting one would violate this
  bounded context's "no provider SDK" boundary before an LLM Provider
  Abstraction Layer exists to justify the dependency. Deliberate and
  documented, not an oversight — see ADR-0012 and
  `prompt_builder.md`'s Token Estimation section. Precise,
  provider-specific counting is the natural responsibility of that
  future layer, not Prompt Builder.
- **Prompt Builder's sections are fixed English prose with no
  localization or per-provider style variation.** A legitimate future
  extension (e.g. XML-tag-style sections for one provider vs.
  markdown-header-style for another) once a real need is demonstrated,
  not designed speculatively this milestone (CLAUDE.md SS12, YAGNI).
- **The Anthropic adapter's system/conversational split is a
  provisional, documented choice, not a final design.** Every
  `CONTEXT`-role `PromptPackage` section is folded into one synthetic
  `role="user"` Anthropic message, since no real end-user question or
  prior conversation turn exists in a `PromptPackage` yet. Milestone 17
  (LLM Invocation Runtime) invokes this mapping unchanged rather than
  redesigning it — a genuine multi-turn conversation is the future AI
  Assistant's (Milestone 17/EPIC 5's numbering, or a later Engineering
  Response milestone's) concern, not this one's. See ADR-0013/ADR-0014
  and `llm_provider_abstraction.md`'s Anthropic adapter section.
- **The LLM Provider Abstraction Layer's API response shapes the
  prepared request specifically for Anthropic** (the only
  production-registered adapter today). A second provider reaching the
  real router will need its own discriminated response shape - a known,
  documented extension point (`llm_provider_abstraction.md`'s "Future
  providers" section), not solved speculatively in Milestone 16.
- **No API key is read anywhere in the LLM Provider Abstraction
  Layer itself.** Deliberate: pure request preparation needs no
  credential. **Resolved for invocation in Milestone 17** — the LLM
  Invocation Runtime reads `ANTHROPIC_API_KEY` (reused from the legacy
  path, not a second variable) only at the composition root
  (`app/routers/llm_provider.py`), behind this project's existing
  secret-handling convention (never logged, never in a response body,
  never seen by the application service as anything but a boolean
  presence flag).
- **This codebase's first external data boundary now exists
  (Milestone 17).** Whenever `LLM_RUNTIME_ENABLED=true` and a
  credential is configured, enabled `PromptPackage` content leaves the
  process and reaches Anthropic's servers. Disabled by default, no
  automatic fallback, no tenant consent workflow, no data-residency
  routing, and no per-project opt-out exists yet — recorded as
  explicit future product/security work, not solved speculatively in
  this milestone. See ADR-0014 and `llm_invocation_runtime.md`.
- **LLM Invocation Runtime metrics are in-process and non-persisted.**
  `llm_runtime_metrics.py`'s counters reset on every process restart
  and are never exported to an external monitoring platform (none
  exists in this repository yet) — adequate for Milestone 17's own
  "lightweight telemetry, not a framework" instruction; a real
  observability platform is Milestone 26's (Monitoring & Observability)
  concern, not this one's.
- **Legacy scratch tooling retained, not cleaned up.**
  `migrate_project_documents.py` (a pre-Alembic, ad hoc `sqlite3`
  migration script) and `test_claude.py`/`test_ingest.py` (manual,
  non-pytest-discovered smoke scripts for the legacy extraction path)
  remain at the repository root. None are proven dead by Milestone 12's
  inventory (see ADR-0009), so none were removed — candidates for
  deletion once the legacy Knowledge Graph path itself is remediated or
  retired.

---

## Long-term Vision

In five years, SubstationOS should be the system of record an EPC
contractor or utility opens first when a question about an installation
comes up — not a chatbot layered over PDFs, but a queryable model of the
installation itself, built from a proprietary electrical ontology that
is versioned, auditable, and shared across every project the
organization runs. A project's knowledge should be assembled once, from
its own documents, under continuous engineering review, and then remain
queryable in seconds for the life of the installation — through design,
construction, commissioning, and decades of operation and maintenance —
without re-reading a single PDF by hand.

The Canonical Domain should by then cover several engineering
disciplines beyond HV/MV substations — transmission, industrial plants,
rail, renewables — added as vocabulary, never as architecture rework,
proving the discipline-neutral design decided in EPIC 1–2 was correct
under real, not hypothetical, pressure. The Project Knowledge Graph
should hold millions of reviewed, versioned facts across thousands of
projects, every one traceable to a specific document, page, and
revision, with no fact ever having reached the graph without engineering
review — a guarantee enforced structurally by the pipeline's shape, not
by policy or discipline alone. AI should remain exactly what ADR-0006
already commits it to: a replaceable translation and composition layer
over a domain model that does not depend on it, swappable across
providers and models as the underlying technology changes, without ever
becoming the thing engineers have to trust instead of the graph.

Enterprise-grade operational maturity — RBAC, audit, monitoring, tested
backup and recovery, validated scalability — should be as unremarkable
by then as the domain modeling is deliberate today: table stakes for
software that utilities, TSOs, DSOs, and EPC contractors run their
engineering process on for years, not a differentiator to still be
proving.

---

## Success Criteria

SubstationOS has reached production maturity when all of the following
hold simultaneously, verifiably, not aspirationally:

1. **Zero mandatory-review-gate exceptions.** No code path exists that
   can write an unreviewed fact into the queryable Project Knowledge
   Graph (ADR-0004 fully closed, not merely designed).
2. **100% Traceability compliance.** Every fact returned by any query or
   AI Assistant answer carries all six Traceability fields (Project,
   Document, Drawing, Page, Revision, Confidence).
3. **Formal schema migrations.** Every schema change since inception is
   represented as a runnable, reversible migration; no schema change
   ships as `create_all()`-only.
4. **Proven AI replaceability.** At least two working `AIProvider`
   adapters exist and are used in production, not just designed as a
   port.
5. **Access control and audit in force.** Every state-changing endpoint
   enforces RBAC; every state-changing action is reconstructable from an
   audit log.
6. **Tested disaster recovery.** Backup/restore has been exercised
   end-to-end, not merely automated and assumed to work.
7. **Validated scalability.** The five requirements in architecture doc
   §10 (thousands of projects, millions of facts, future document
   types, future AI models, future disciplines) are demonstrated under
   load, not just satisfied by design.
8. **A second discipline, demonstrated.** At least one EPIC 8 discipline
   beyond HV/MV substations is live on a real or representative project,
   with zero architecture changes required above the Canonical Domain
   layer.
9. **Full-suite green.** `python -m pytest` from `apps/backend/` remains
   green at every commit, across a test suite that covers every
   bounded context added since this plan (`CLAUDE.md` §9, §13).

---

## Out of Scope

Explicitly excluded from this roadmap's EPICs 1–8, not because they lack
value, but because building them now would either duplicate a tool
SubstationOS is not meant to replace, or reach far beyond what the
current Core Platform can support without the trust guarantees this
architecture exists to provide:

- **Replacing AutoCAD, SCADA, or engineering calculation software.**
  `PRODUCT_VISION.md`'s Non-Goals already establish this: SubstationOS
  makes these tools more intelligent by understanding their outputs; it
  does not reimplement them.
- **Native DWG/DXF authoring or editing.** Reading and extracting from
  drawings is in scope (Document Repository, Knowledge Extraction);
  producing or modifying them is not.
- **Autonomous "Engineering Agents"** (Designer, Reviewer, Commissioning,
  Protection, Documentation agents from `PRODUCT_VISION.md`'s Core
  Modules) that generate or modify engineering deliverables
  automatically. These require a mature, review-gated Project
  Knowledge Graph (EPIC 3) and a proven Query Engine/AI Platform
  (EPICs 4–5) as prerequisites this roadmap does not yet claim to
  deliver, and each would warrant its own ADR and roadmap revision
  before being scheduled.
- **Real-time SCADA integration or live telemetry.** SubstationOS
  reasons over documentation and reviewed engineering knowledge, not
  live operational data streams — a different trust model and a
  different architecture entirely.
- **Mobile applications and offline mode.** Not precluded long-term, but
  no milestone in EPICs 1–8 targets them.
- **On-premises / air-gapped deployment and formal SaaS multi-tenant
  billing infrastructure.** Multi-tenancy at the data-model level
  (Project as a boundary, ADR-0001) is already core to the architecture;
  packaging, deployment topology, and billing are commercial/operational
  concerns not addressed by this technical roadmap.
- **Disciplines beyond the four named in EPIC 8.** Any discipline not
  listed (Industrial Plants, Transmission, Rail, Renewables) is neither
  planned nor precluded — EPIC 8's own completion criteria require
  proving generalization on these four before treating "add any
  discipline" as a solved, repeatable process.
- **Formal regulatory/compliance certification workstreams** (e.g.
  IEC 61850 conformance tooling, region-specific grid-code compliance
  checking). The Canonical Domain can model the vocabulary such work
  would need, but building certification/compliance tooling itself is
  not part of this roadmap.

---

*Understanding Electrical Infrastructure.*
