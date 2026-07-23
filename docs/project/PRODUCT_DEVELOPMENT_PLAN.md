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
| Engineering Index | Does not exist |
| Knowledge Extraction | Functional but ungoverned — writes directly into graph storage, bypassing the mandatory review gate (ADR-0004 violation, tracked and accepted, not yet remediated) |
| Project Knowledge Graph | Storage/query exist; review-state, canonicalization, and versioning fields are missing |
| Semantic Query Engine | Query layer exists; NL interpretation and answer generation are not built |
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

**Status:** Next

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
- **Expected deliverables:** `app/domain/engineering_index/**` (new
  bounded context); review-state fields on `ProjectEntity`/
  `EntityRelation` or their replacements; a canonicalization service
  that promotes `APPROVED` facts into the graph; Mandatory Metadata
  fields (Drawing Number, Discipline, Page, Extraction Session,
  Reviewer, Review Date, Canonical Version).
- **Implementation maturity:** Not started. Fully designed
  (`project_intelligence_architecture.md` §§4–7, ADR-0002/0004,
  `CANONICAL_KNOWLEDGE_PROTOCOL.md` §§4–6), zero percent built.

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

**Milestone 9 — Engineering Index**
- Objective: build the fast, unreviewed, per-document inventory of
  candidate mentions (ADR-0002) as a new bounded context.
- Expected duration: 2–3 weeks.
- Dependencies: EPIC 2 (Project boundary); Document Classification
  populating `Document.category` (currently an unused field).
- Architecture impact: none — this is designed, not decided, by
  ADR-0002 and architecture doc §5; implementation must not
  reinterpret the design.
- Implementation impact: new `app/domain/engineering_index/**` and
  `app/infrastructure/engineering_index/**`; a new indexing step
  triggered on upload, separate from and prior to extraction.

**Milestone 10 — Mandatory Review Gate Closure**
- Objective: stop `ingest_document` from writing directly into
  queryable graph storage; route all extraction output through the
  Canonical Knowledge Protocol's review-state machine before anything
  reaches the graph. Closes the ADR-0004 violation.
- Expected duration: 3–4 weeks.
- Dependencies: Milestone 9 (the Index is where unreviewed output goes
  instead).
- Architecture impact: none — implements an already-accepted, not-yet-
  implemented decision (ADR-0004).
- Implementation impact: review-state, reviewer, and review-date fields
  on the extraction output model; a review action (approve/reject) as a
  first-class application service; `ingest_document` rewritten to write
  to the Index, not the Graph.

**Milestone 11 — Project Knowledge Graph Canonicalization & Versioning**
- Objective: populate the Project Knowledge Graph only from `APPROVED`,
  canonicalized facts; add per-entity versioning and supersession links
  (Canonical Knowledge Protocol §9).
- Expected duration: 3–4 weeks.
- Dependencies: Milestone 10 (a review gate producing `APPROVED` facts
  to canonicalize).
- Architecture impact: none — implements ADR-0002's second layer and
  the Protocol's existing versioning design.
- Implementation impact: a canonicalization service; `canonical_version`
  and `Supersedes`/`Superseded by` fields on graph entities; graph
  writes become append-only.

**Milestone 12 — Traceability Metadata Completion**
- Objective: make every graph fact able to answer all six Traceability
  fields (Project, Document, Drawing, Page, Revision, Confidence) on
  demand.
- Expected duration: 1–2 weeks.
- Dependencies: Milestone 11 (a graph structure to attach the remaining
  fields to).
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

- **Migration infrastructure.** Schema changes rely entirely on
  `Base.metadata.create_all()`, which only creates missing tables and
  never alters existing ones. The Project Lifecycle columns added in
  EPIC 2 do not appear on any pre-existing on-disk database until it is
  recreated from empty. No rollback path exists for any schema change
  made so far. Addressed in Milestone 28, but every EPIC 3–7 milestone
  that changes the schema will accumulate more of this debt until then.
- **Engineering Index.** Does not exist. Its absence is why extraction
  currently has nowhere ungoverned to land except the graph itself —
  the root cause behind the next item. Addressed in Milestone 9.
- **Mandatory review gate (ADR-0004 violation).** `ingest_document`
  currently writes AI-extracted entities and relationships directly
  into queryable graph storage, with no review state of any kind. This
  is the single highest-priority gap in the entire roadmap — every
  traceability and versioning guarantee elsewhere in the system is
  moot while it stands. Addressed in Milestone 10.
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
