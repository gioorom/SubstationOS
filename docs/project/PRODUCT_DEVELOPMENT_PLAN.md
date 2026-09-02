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
| Public API (Projects, Documents) | Hardened — every public endpoint exposes a governed application schema (Milestone 30.1.3): typed document summary/detail/list/upload responses, a document detail endpoint, a governed streaming download, server-side pagination (`page`/`page_size`, max 100, refused not clamped), server-side filtering and search over documented closed vocabularies, and governed sorting with an `id` tie-breaker. **Storage location is private backend state** - no public value object has a field for it, and a test walking the whole OpenAPI document found and removed the one that had leaked (`DocumentContentIdentityRead.storage_reference`). Routers construct no queries and the projects router imports no ORM module at all, both asserted on the AST |
| Document Registry | Implemented — the first Document bounded context (Milestone 30.1.3): `DocumentSummary` / `DocumentDetail` value objects with no storage field, a closed governed query vocabulary (`DocumentQuery`, `DocumentSortField`, `DocumentSearchTerm`), a `DocumentRegistryRepository` port whose list returns one page plus a total, and a `DocumentDownload` value object that sanitises the filename by allow-list. Content is reached only through Milestone 25.2's two ports, so the download's only input is an integer id and traversal is unrepresentable rather than blocked |
| Document Repository | Functional — upload/storage/scope work, and since Milestone 25.2 the upload endpoint classifies `file_format` from the file's own leading bytes rather than defaulting every document to `other`. `DXF` and `IMAGE` joined the vocabulary in the same milestone. Documents uploaded earlier remain readable as `other` (*unclassified*) until the deterministic backfill command is run against them |
| Document Identity | Implemented — deterministic content identity and format classification (Milestone 25.2): SHA-256 streamed in chunks with the algorithm recorded beside it, size and accessibility, and a format decided from evidence ranked content signature > declared MIME type > filename extension. **One rule source** (`format_signatures.py`, asserted by architecture test) used by upload, ingestion and the backfill alike, so they cannot disagree about what a document is. Unknown and contradictory evidence produce explicit typed outcomes, never an arbitrary classification. Bytes reach the domain only through the read-only `DocumentContentPort` (`describe`/`read_prefix`/`iter_chunks`, abstract-method set asserted). Identity is **not** deduplication - identical checksums are recorded and nothing is concluded from them |
| PDF consumption | Consolidated — since Milestone 26.2 there is exactly **one** supported PDF path (`upload → ingestion → identity → canonical representation → canonical text → downstream consumer`) and exactly **one** module permitted to import a PDF library. The four pre-canonical decoders (`pdf_text_extractor`, `pdf_renderer`, `document_analyzer`, `services/intelligence/`) are deleted; the upload endpoint's Knowledge Graph path consumes text assembled from the segmentation. Enforced by architecture tests asserting the single decoder, the shrinking closed list of raw-content consumers, and the absence of the retired files |
| Engineering Semantic Interpretation | Implemented — deterministic assignment of engineering meaning to constructed facts (Milestone 30.1): `EngineeringSemanticSet → EngineeringSemanticStatement`, from a versioned rule catalogue that is the **only** place an executable engineering rule may live (asserted by architecture test). One statement type, `HAS_RATED_POWER`, from one rule (`rated_power_from_associated_power_quantity` 1.0): a designation associated with **exactly one** power quantity has that quantity as its rated power. Voltage, current and cable section are deliberately left uninterpreted — an associated voltage may be rated, test, insulation or busbar voltage, and the association does not say which. Two candidate powers produce **no statement** and a diagnostic in a separate table, because a fact carries entity keys rather than values. Statements own no provenance, carry no value, unit or confidence, and cite supporting facts by key; status (`interpreted` / `ambiguous`) is inherited from the fact, never invented. Idempotent on the whole upstream source identity `(document_id, content_checksum, resolution_policy_version, fact_policy_version, semantic_policy_version)`. **Meaning only** — no LLM, no embeddings, no machine learning, no probabilistic inference, no reasoning, no Knowledge Graph or Engineering Index write, all enforced by architecture test |
| Engineering Fact Construction | Implemented — deterministic structured associations between resolved entities (Milestone 29.2): `EngineeringFactSet → EngineeringFact`, under one construction rule (`same_line_association`) and one closed predicate (`HAS_ASSOCIATED_QUANTITY`) that deliberately asserts no property role. Declared cardinality policy: one designation may associate with many quantities on a line; two or more designations produce **no fact** and a diagnostic stored in a separate table. Facts aggregate support from subject entity, object entity and contributing evidence, and reference entities by deterministic key so fact history survives a newer entity set. **Associations only** — no classification, no topology, no LLM, no proximity scoring, no fuzzy matching, no Knowledge Graph or Engineering Index write, all enforced by architecture test |
| Engineering Entity Resolution | Implemented — deterministic grouping of evidence into entities (Milestone 29.1): `EngineeringEntitySet → EngineeringEntity`, covering `EQUIPMENT_DESIGNATION` and `ENGINEERING_QUANTITY` under a versioned rule catalogue with no fuzzy matching of any kind. Identity is a SHA-256 over document, evidence source, rule and version, so the same evidence always resolves the same way and a rule bump creates a new set rather than a rewrite. Entities **aggregate** their evidence's provenance and can enumerate the observations that created them; none exists without at least one. Idempotent on `(document_id, content_checksum, resolution_policy_version)`. **Groupings only** — no relationship, no topology, no equipment classification, no LLM, no Knowledge Graph or Engineering Index write, and no column in which any of them could be recorded, all enforced by architecture test |
| Engineering Evidence Evaluation | Implemented — the permanent framework that measures extraction quality (Milestone 28.2): a version-controlled `ReferenceCorpus` in `app/domain/evidence_evaluation/corpora/*.yaml`, exact-match classification into `TRUE_POSITIVE` / `FALSE_POSITIVE` / `FALSE_NEGATIVE` with **provenance as part of the match**, exact `Decimal` precision/recall/F1 per corpus, document, evidence type and rule, and regression detection naming the exact items that changed. Reports are insert-only and corpora immutable at runtime; evaluation writes no engineering evidence and reaches no document. Measured baseline against `substation_reference` 3.1: precision 0.916667, recall 0.970588, F1 0.942857 (33 TP / 3 FP / 1 FN) |
| Engineering Evidence Extraction | Implemented — deterministic engineering observation over canonical text (Milestone 28.1): `EngineeringEvidenceSet → EngineeringEvidence` for designations, voltages, currents, powers and cable sections, under a versioned rule catalogue with **one** pattern source and **one** unit catalogue. Quantities held as exact `Decimal` (`Numeric` in the schema, never `Float`); every item carries provenance to the characters, tokens, line, paragraph and page that produced it, plus rule id and version. Idempotent on `(document_id, content_checksum, extraction_policy_version)`. **Observations only** — no entity, no relationship, no equipment type, no LLM, no Engineering Index or Knowledge Graph write, and no column in which any of them could be recorded, all enforced by architecture test |
| Canonical Text Segmentation | Implemented — semantic-neutral textual structure over the canonical representation (Milestone 27.1): `CanonicalTextDocument → Section → Paragraph → Line → Token`, where a section **is a page**, a paragraph **is a PDF block** and a line **is a PDF line** - only boundaries the parser observed, never an inferred chapter, heading, table or list. Tokens carry original text, a deterministic NFKC normalisation, position in the line, and the full provenance chain `document → page → block → span → character range`, stored as columns so locating a term costs no joins. **The structure every future extractor consumes**, behind `CanonicalTextRepository`, which exposes no PDF structure. Idempotent on `(document_id, content_checksum, segmentation_version)`; no timestamp participates in value equality. Assigns no engineering meaning: no entities, no equipment, no cables, no relationships, no LLM, no ontology lookup, all enforced by architecture test |
| Canonical PDF Representation | Implemented — deterministic, reproducible textual representation of a PDF (Milestone 26.1): `CanonicalPdfDocument → Page → Block → Span`, preserving page number, the parser's own reading order, verbatim text, bounding boxes, font family and size, and bold/italic, bound to one content checksum, one parser version and one representation version. **The single source of truth for every future semantic extraction**, consumed through `CanonicalRepresentationRepository` - which exposes no route to the original PDF, so the rule is structural. Idempotent (identical bytes re-use the stored representation; changed bytes produce a new one beside it, never over it), and the original PDF is never modified. Records what the parser observed and interprets nothing: no merged paragraphs, no inferred tables, lists, headings or sections, no entities, no OCR, no LLM, no embeddings, all enforced by architecture test |
| Document Ingestion | Implemented — deterministic ingestion lifecycle (Milestone 25.1): explicit `UPLOADED → QUEUED → PROCESSING → PROCESSED/FAILED` state machine with validated transitions and an illegal move raising, one typed immutable `IngestionJob` per attempt with retry on the same record, one job in flight per document, a document-metadata snapshot taken at ingestion time, and a persisted `READY_FOR_EXTRACTION`/`FAILED` outcome for a future extractor. Milestone 25.2 extended the snapshot with content identity and classified format, each failure named rather than collapsed into a generic one, while the pipeline itself stayed pure - the service resolves bytes through the ports and hands the result in. **Orchestration only** - no document contents interpreted, no LLM, no embeddings, and no write to the Engineering Index or the Knowledge Graph, all enforced by architecture test |
| Engineering Index | Implemented — idempotent, project-scoped, document-traceable (Milestones 9, 9.1); **read side** (Document Retrieval, Milestone 23B.1) answers "which documents mention X?" as ranked `DocumentReference`s scored from a fixed documented weight table, with a batch document-metadata port; reads no document contents |
| Review Workflow | Implemented — `ProposedClaim`/`ReviewCandidate` state machine; the ADR-0004 mandatory review gate is closed for this pipeline (Milestone 10) |
| Canonicalization | Implemented — deterministic normalization of `APPROVED` claims into `CanonicalFact`s (Milestone 11) |
| Project Knowledge Graph (Canonical Facts) | **Retired (EPIC 31.4, ADR-0028).** Graph Builder, Graph Persistence and their execution model are deleted; `project_graph_nodes`, `project_graph_relationships`, `graph_executions`, `graph_execution_operation_results`, `graph_execution_fingerprints`, `graph_operation_batches` and `graph_operations` are dropped by migration `f4a90c27b615`. ADR-0007 is superseded. The Alembic governance it introduced (Milestone 12, ADR-0008) survives and now carries the retirement |
| Graph Query | **Retired (EPIC 31.4, ADR-0028).** Its only purpose was reading the Canonical Facts projection; seven of its routes are withdrawn. Listing and lookup are answered over governed knowledge by `GET /knowledge-graph/nodes` and `/knowledge-graph/edges`; **orphan detection has no successor** - the governed graph retires a node whose every edge retired, so an orphan is not a state it can be in |
| Structured Retrieval (Canonical Facts) | **Retired (EPIC 31.4, ADR-0028).** Implementation deleted, both endpoints withdrawn; ADR-0010 is superseded by ADR-0026. Its deterministic-first principle survives in Governed Structured Retrieval; two capabilities do not, and are recorded as removals rather than migrations: **property-bag attribute search** (the governed graph has no property bag, ADR-0024) and **broad lexical matching** across attribute keys and values. `structured_retrieval.md` is retained, marked RETIRED, as the record of what the capability was |
| Governed Structured Retrieval | Implemented — the Engineering Engine's retrieval since EPIC 31.2, and it consumes the Governed Knowledge Graph **exclusively** (ADR-0026). Five typed queries (asset by designation, quantity for an asset, relationships, document knowledge, governed identity) with explicit fields and no free text, no filter object and no query language. Matching is against typed governed fields only — the governed graph has no property bag, and none was carried forward in either direction — through three documented deterministic folds; **ranking is by match strategy, never by a score**, because a weight attached to engineering knowledge is the ungoverned trust signal ADR-0004 rejected. Every result names exactly one match strategy, the governed field that carried it, and mandatory provenance (statement, review, reviewer, rule and policy versions, support fingerprint, document). Ambiguity is preserved rather than resolved: `NO_MATCH`/`UNIQUE_MATCH`/`MULTIPLE_MATCHES` is computed before any limit, and two documents designating the same thing stay two answers. Historical knowledge never answers a current question unless a caller asks for it explicitly. Retrieval implements no governance of its own — it reads `state`, and the promotion contract is the only definition — and it reads through a port with **no write method**. Quality was measured against a nine-scenario baseline and a classified shadow comparison before the substrate moved |
| Governed Context Assembly | Implemented — deterministic, bounded, provenance-aware `ContextPackage` assembly (selection, aggregation, coverage, budget enforcement, warnings, statistics, metadata) from `GovernedRetrievalResult`s (Milestone 14 / ADR-0011, migrated onto governed knowledge by EPIC 31.3 / ADR-0027). A `ContextItem` **wraps** a governed retrieval item rather than copying it, so provenance (statement, review, reviewer, support fingerprint, document) is structurally impossible to drop, ambiguity survives per query (`NO_MATCH`/`UNIQUE_MATCH`/`MULTIPLE_MATCHES`), and **ordering carries no score** — it is the governed match-strategy precedence and nothing else. Deduplication is by governed identity, never by label, so two documents designating the same thing stay two items. Truncation is always diagnosable: matched-before-limit, retrieved and selected counts are all reported. Performs no I/O and issues no query of its own, which is what keeps retrieval's project/document scope and authorization from being widened downstream; no persistence, no AI, no prompt generation; also a `ComparisonContextPackage` - two whole `ContextPackage`s, each assembled from its own governed results, paired under named left/right fields and never merged |
| Prompt Builder | Implemented — deterministic, provider-independent `PromptPackage` composition (nine fixed-order sections, versioned constraints/instructions, approximate token estimates, statistics, self-validation) from a `ContextPackage` (Milestone 15, ADR-0012); a `PromptObjective` (Milestones 23B.2, 24.1, 24.2) selects between fixed, versioned instruction and expected-output sets (`DIRECT_ANSWER` / `ENGINEERING_EXPLANATION` / `ENGINEERING_VERIFICATION` / `ENGINEERING_COMPARISON`) - never free-form or caller-supplied prompt text - and truthfulness constraints never vary by objective; owns the closed verdict and comparison-outcome vocabularies an answer must declare, and the `LEFT_KNOWLEDGE`/`RIGHT_KNOWLEDGE` sections that keep a comparison's two evidence groups typed apart; no persistence, no AI, no provider serialization |
| LLM Provider Abstraction Layer | Implemented — provider-neutral `LLMProviderPort`/`LLMRequest` contract, deterministic `PromptPackage` → `LLMRequest` mapping, an Anthropic adapter (zero SDK dependency) and a fake test adapter, an explicit provider registry, runtime-configured provider/model selection (Milestone 16, ADR-0013); no invocation, no network call, no persistence |
| LLM Invocation Runtime | Implemented — attempt/retry/deadline/cancellation-governed execution of a real Anthropic call, provider-neutral `LLMResponseEnvelope` normalization, disabled by default (Milestone 17, ADR-0014); no automated test calls a real provider; no persistence, no streaming, no conversation memory |
| Engineering Response | Implemented — deterministic, domain-owned `EngineeringResponse` (typed sections, structured warnings, uncertainty declarations, preserved evidence/version provenance) normalized from an `LLMResponseEnvelope`, no AI usage of its own (Milestone 18, ADR-0015); `SUMMARY`/`TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`NEXT_ACTIONS` sections always empty (no semantic parsing of provider prose); since Milestone 23B.1 also composes `DETERMINISTIC_RETRIEVAL` responses (`EngineeringResponseOrigin`) built entirely from repository state, with validation rejecting any such response that names a provider, model or runtime version; since Milestone 24.1 carries a `VerificationAssessment` for verification responses, read from a declared first-line verdict protocol (never inferred from prose) and structurally bounded to `INSUFFICIENT_EVIDENCE` when no evidence was retrieved; since 24.2 a `ComparisonAssessment` on the same device, bounded when **either** side retrieved nothing so a missing side can never become a difference; no conversation, no persistence |
| Engineering Session | Implemented — the root aggregate for one engineering work session: project identity, a validated state machine (`CREATED`/`ACTIVE`/`PAUSED`/`COMPLETED`/`ARCHIVED`), an ordered `EngineeringResponse` history, an append-only timeline, statistics, version metadata (Milestone 19, ADR-0016); smallest dependency surface of any context in this pipeline (only `engineering_response`); no conversation/chat/memory/tools/agents yet; no persistence - each API call accepts and returns the full session, nothing is held server-side |
| Conversation | Implemented — structured engineering dialogue belonging to an `EngineeringSession` (referenced, never embedded): ordered `ConversationTurn`s (the primary conversational unit, not `ConversationMessage`) owning ordered messages and `EngineeringResponse` references (held directly, never copied), a validated Conversation/Turn state machine, an append-only timeline, statistics, version metadata (Milestone 20, ADR-0017); no memory, tool execution, agents, or assistant reasoning yet; no persistence |
| Working Memory | Implemented — deterministic, structurally-derived temporary engineering context for continued reasoning: open questions, recent `EngineeringResponse`s, their evidence references, and their already-computed assumptions/constraints (Milestone 21, ADR-0018); not conversation history, not project knowledge, never AI-edited, never persisted; `CURRENT_OBJECTIVE`/`CURRENT_EQUIPMENT`/`CURRENT_ELECTRICAL_AREA`/`CURRENT_TASK` reserved but never populated (no structural signal exists yet) |
| Engineering Request Classification | Implemented — deterministic, rule-based classification of one explicit request into a small workflow taxonomy (10 types), with first-class reproducible evidence, categorical confidence, explicit precedence, and ambiguity as a valid result (Milestone 22, ADR-0019); no LLM, no embeddings, no semantic model, no provider SDK; depends on no other bounded context at all; not executable - a classification result only |
| Classification-to-Retrieval Bridge | Implemented — deterministic mapping from a classified request to the typed retrieval criteria the engine requires (Milestone 23B.3): designation extraction by fixed token shape, resolution against Canonicalization's existing public vocabulary, an immutable versioned intent→retrieval policy table, and typed unresolved outcomes (insufficient / conflicting / unsupported / invalid) instead of silently broadened retrieval; never invents an identifier; no LLM, no embeddings, no fuzzy matching; executes nothing and depends on the Engineering Engine not at all. Closes the raw-request→engine gap: `POST /engineering-requests/prepare` returns exactly the body `/engineering-engine/execute` accepts |
| Engineering Engine | Implemented (foundation) — registry-driven workflow selection, explicit deterministic `WorkflowPlan`s, step-handler execution with first-failure stop, 14 typed failure codes, an append-only execution timeline, and explicit never-applied aggregate update proposals (Milestone 23A, ADR-0020); **five workflows** - `KNOWLEDGE_QUERY` (23A), `DOCUMENT_LOOKUP` (23B.1, the first workflow that invokes no LLM at all), `ENGINEERING_EXPLANATION` (23B.2), `ENGINEERING_VERIFICATION` (24.1, the first reasoning workflow) and `ENGINEERING_COMPARISON` (24.2, the first with two subjects and two independent retrievals whose identity is preserved end to end), each added by declaration and registration alone with no change to engine decision logic; the engine evaluates and compares nothing itself; every other intent returns `UNSUPPORTED` and runs nothing; reuses Structured Retrieval, Document Retrieval, Context Builder, Prompt Builder, the provider-neutral runtime and Engineering Response rather than reimplementing them; no persistence, no transaction, no retries, no agents |
| AI Assistant | Does not exist |
| Web frontend | Integrated — one centralised API client (the only caller of `fetch`), one transcription of the API contract in `lib/contracts` asserted against the backend's own OpenAPI document, a typed error model with no generic "an error occurred", and two state primitives replacing five hand-rolled hooks. Two document surfaces answering two questions: the **Pipeline UI** (did each stage run) and, since EPIC 30.2, the **Engineering Workspace** (what does the platform claim, and what supports it). **No mock data, no placeholder counters** — `lib/demo-*.ts` and the commissioning/timeline panels are deleted. 205 frontend tests, including architecture tests asserting no fuzzy matching, no engineering rule, no direct `fetch` and no write exists in Workspace code. Still absent: authentication and any human review UI |
| Identity and access | Implemented — an `identity` bounded context (EPIC 30.3): users, scrypt password credentials in a self-describing upgradable form, server-side authentication sessions with independent idle (2h) and absolute (12h) clocks, three roles (anonymous / engineer / administrator) and capability-declaring routes. Authentication is **deny-by-default middleware**: every route requires a session unless it is on a short, deliberate public list, and a test walks every path in the live OpenAPI document to prove it. The session token leaves the server only as an `HttpOnly` cookie and is stored as a SHA-256 fingerprint, so a copy of the database is neither a set of passwords nor a set of live logins. CSRF is a session-bound token, not plain double-submit |
| Human Review | Implemented — a dedicated bounded context (EPIC 30.4) recording governed engineering judgement over deterministic pipeline artefacts. **Append-only**: reviews are immutable, the port declares no update or delete, the API exposes no `PATCH` or `DELETE`, and the current decision is a projection over the ordered history rather than a stored column. A review references a semantic statement by key and never contains one; recording it changes no engineering artefact, asserted by comparing the semantic set before and after. Survives pipeline re-runs by **artefact identity**: `statement_key` already hashes the document, the fact source and the rule versions, so a judgement is `applies`, `requires_revalidation` or `orphaned` by lookup - never discarded, and never carried onto a differently-derived statement. Three decisions, nine reasons paired to them, snapshots recording identity rather than payload |
| Governed Knowledge Graph | Implemented — the query model over approved engineering knowledge (EPIC 31), and the **first implementation to satisfy ADR-0004**. A projection and never a source of truth: it consumes only semantic statements whose current review is `APPROVED` and whose applicability is `APPLIES`, and it may always be dropped and rebuilt from the pipeline and the reviews. Rebuildability is asserted rather than promised - identities are hashes of governed keys and `created_at` comes from the authorising review, so the projection is a pure function of its sources. Every node and edge carries mandatory provenance (statement, review, reviewer, rule and policy versions, support fingerprint) and there is no confidence score anywhere. Knowledge whose authorisation stops holding becomes `historical` with a recorded reason, never silently retained and never deleted. Two node kinds and one edge kind, because that is what governed semantics produces. Resource-oriented REST; no Cypher, GraphQL or SPARQL |
| Legacy Knowledge Graph | **Retired (EPIC 31.1).** The AI-extraction path that wrote unreviewed entities into the queryable graph on every upload - the ADR-0004 violation ADR-0009 quarantined from Architecture Freeze v1.0. Service, router, schemas, models, the regex `entity_extractor`, the `topology` builder and the second LLM client in `services/ai/**` are deleted; `project_entities` and `entity_relations` are dropped by migration. Ingestion now runs **no downstream consumer at all**. One graph implementation deliberately remains - the Canonical Facts lineage the Engineering Engine reads - retained because it is proven *used*, and asserted as such by an architecture test |
| Audit trail | Implemented — an append-only `audit` bounded context (EPIC 30.3) whose port declares no update and no delete. Records login, failed login, logout, password change, user lifecycle, project creation, document upload, pipeline execution and access denials, each with actor, timestamp, action, resource and outcome. **Audit identity attaches to actions, never to artefacts** - no engineering domain module may import identity (asserted), no engineering table may carry a user column (asserted), and running the pipeline under two different logins produces byte-identical artefacts (asserted) |
| Engineering Workspace | Implemented — `/documents/{id}/workspace` (EPIC 30.2): a document-centric, **inspection-only** projection over governed artefacts. Three regions (source, engineering explorer, inspector); the full support chain `statement → fact → entity → evidence → canonical source location` navigable in both directions, composed client-side from four whole-set reads with **no support-chain endpoint added** — every join is a key the backend declared, never a text or value comparison. Highlights are drawn on an SVG map of the canonical representation at the parser's own bounding boxes, so an observation's provenance and its highlight are the same artefact and cannot drift (ADR-0021); no PDF rendering library was added. Diagnostics are first-class content, and `unrun`/`empty`/`ambiguous`/`declined`/`failed`/`reused` stay distinct, each carried by colour, glyph and word. `interpreted` is stated everywhere to mean *produced by a versioned rule*, never *approved by an engineer*. One read-only endpoint added: `GET /documents/{id}/canonical-representation/pages/{n}` |
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

**Status:** In Progress

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
- **Delivered so far:** `app/domain/engineering_response/**` (Engineering
  Response Foundation, Milestone 18, ADR-0015) — the canonical,
  deterministic, domain-owned normalization of an `LLMResponseEnvelope`
  into a structured `EngineeringResponse` every future AI-facing
  capability consumes; `app/domain/engineering_session/**` (Engineering
  Session Foundation, Milestone 19, ADR-0016) — the root aggregate
  every future conversation, tool, and agent will execute inside:
  project identity, a validated session state machine, an ordered
  `EngineeringResponse` history, an append-only timeline, statistics,
  and version metadata; `app/domain/conversation/**` (Conversation
  Foundation, Milestone 20, ADR-0017) — structured engineering dialogue
  belonging to an `EngineeringSession`: ordered `ConversationTurn`s (the
  primary conversational unit) owning ordered messages and
  `EngineeringResponse` references, with future tool execution,
  retrieval, and agent execution all reserved to live inside a Turn;
  `app/domain/working_memory/**` (Working Memory Foundation, Milestone
  21, ADR-0018) — the temporary, deterministic engineering context
  needed to continue reasoning during a session: open questions,
  recent `EngineeringResponse`s, their references, and their
  already-computed assumptions/constraints, all structurally derived
  and always rebuildable, never AI-edited;
  `app/domain/engineering_intent/**` (Engineering Request
  Classification, Milestone 22, ADR-0019) — the deterministic,
  rule-based routing decision a future orchestrator will use to select
  a workflow, with first-class evidence and ambiguity as a valid
  result; `app/domain/engineering_engine/**` +
  `app/services/engineering_engine/**` (Engineering Engine Foundation,
  Milestone 23A, ADR-0020) — the application coordinator that selects,
  plans and executes complete engineering workflows end to end, now with
  a second registered workflow (`DOCUMENT_LOOKUP`, Milestone 23B.1) that
  answers without invoking a provider at all, and a third
  (`ENGINEERING_EXPLANATION`, Milestone 23B.2) that reuses the
  knowledge-query pipeline with one differently-instructed prompt step.
- **Implementation maturity:** Early but now end-to-end for three
  workflows, one of them entirely LLM-free. The `AIProvider` port and one legacy adapter
  (`app/services/ai/claude_provider.py`) already existed and remain the
  foundation this EPIC extends, not replaces; Engineering Response,
  Engineering Session, Conversation, Working Memory, Engineering
  Request Classification, and the Engineering Engine are now delivered
  on top of the governed EPIC 4 pipeline, and a classified
  `KNOWLEDGE_QUERY` request now runs a complete coordinated workflow to
  a validated `EngineeringResponse`. No long-term memory, tool
  execution, agent, or autonomous-reasoning surface exists yet.

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
- **Implementation maturity:** Partial. EPIC 30.1.2 made the existing
  frontend a faithful client of the backend — project CRUD, document
  upload and the full deterministic Pipeline UI now work end to end
  against real endpoints, with no mock data anywhere. What EPIC 6 still
  has to build is authentication, the Review UI, and a document viewer
  (which needs a backend download endpoint that does not exist). See
  `docs/architecture/frontend_architecture.md`.

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

**Milestone 18 — Engineering Response Foundation** — *Completed*
- Objective: the first domain-oriented representation of an AI answer -
  transform a provider-neutral `LLMResponseEnvelope` into a structured,
  traceable `EngineeringResponse`, the canonical output contract every
  future AI-facing capability consumes. Explicitly not the
  conversational assistant itself.
- Delivered: `app/domain/engineering_response/**` — a genuine domain
  bounded context (unlike the LLM Runtime, ADR-0013/0014) following the
  same reference pattern every other context in this pipeline uses:
  `EngineeringResponse`/`EngineeringResponseStatus`
  (`COMPLETE`/`PARTIAL`/`UNSUPPORTED`/`EMPTY`, an engineering-native
  completeness assessment derived from structural signals, never a copy
  of `LLMInvocationStatus`); nine fixed `EngineeringSectionType`
  sections in canonical order (`SUMMARY`/`DIRECT_ANSWER`/
  `TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`WARNINGS`/`LIMITATIONS`/
  `NEXT_ACTIONS`/`REFERENCES`/`UNKNOWN`) - `DIRECT_ANSWER`/`WARNINGS`/
  `LIMITATIONS`/`REFERENCES`/`UNKNOWN` populated from structural
  signals only, `SUMMARY`/`TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/
  `NEXT_ACTIONS` always empty by deliberate design (no AI usage, no
  semantic parsing of provider prose - see ADR-0015); structured
  `EngineeringWarning`/`EngineeringWarningCategory` and
  `EngineeringUncertainty`/`EngineeringUncertaintyLevel` (never model
  confidence - derived from knowledge-coverage and response-completeness
  signals, worst-wins ranked into one `overall_uncertainty`);
  `EngineeringEvidenceReference` preserving `PromptPackage.references`
  verbatim; versioned `EngineeringResponseMetadata`/
  `EngineeringResponseVersion` echoing the full version chain from
  Context Builder through the LLM Invocation Runtime; a self-validating
  `EngineeringResponseValidator`. `app/services/engineering_response_service.py` —
  the **one** file in the codebase allowed to import both
  `LLMResponseEnvelope` (application layer) and this domain, translating
  the former into the domain's own `EngineeringResponseSourceEnvelope`
  restatement before ever calling the pure domain assembler,
  reconciling this milestone's own "Engineering Response is a domain
  concept" instruction with CLAUDE.md's Dependency Rule. `POST /projects/{id}/engineering-response/build` —
  performs no AI invocation of its own.
- Architecture impact: **new ADR (0015)** — why Engineering Response is
  a genuine domain bounded context despite consuming an application-layer
  artifact, why that Dependency Rule tension is resolved by restatement
  in one translation seam rather than by exception, why uncertainty is
  not confidence, why evidence preservation is mandatory, and why
  warnings are structured data rather than free text.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 18" for Prompt
  Orchestration Framework. That entry's number is left unchanged here,
  for the same reason Milestones 12-17's numbering collisions were left
  unchanged rather than cascade-renumbering subsequent milestones — see
  those milestones' own numbering notes.
- Dependencies: Milestone 17 (a real, normalized `LLMResponseEnvelope`
  to transform).

**Milestone 19 — Engineering Session Foundation** — *Completed*
- Objective: introduce the root aggregate representing a complete
  engineering work session on a project - project identity, session
  state, the ordered `EngineeringResponse` history, an append-only
  timeline, statistics, and version metadata. Explicitly not a chat;
  future conversations, tools, assistants, and agents will all execute
  inside an `EngineeringSession`, never stand as their own root.
- Delivered: `app/domain/engineering_session/**` — the smallest
  dependency surface of any bounded context in this pipeline (only
  `app.domain.engineering_response`, to own `EngineeringResponse`
  objects directly; no Prompt Builder, Context Builder, Structured
  Retrieval, Graph Query, provider SDK, or `app.application.**` of any
  kind). `EngineeringSessionStatus` (`CREATED`/`ACTIVE`/`PAUSED`/
  `COMPLETED`/`ARCHIVED`) with an explicit, validated transition table
  (the same convention `app.domain.project.project_lifecycle` already
  established); `EngineeringSessionTimeline` - an append-only,
  strictly-sequenced ledger of `EngineeringSessionEvent`s
  (`SESSION_CREATED`/`ENGINEERING_RESPONSE_ADDED`/`STATE_CHANGED`/
  `CONFIGURATION_UPDATED`); `EngineeringSessionBuilder`
  (`build_initial_session`/`append_engineering_response`/
  `change_session_state`/`update_session_configuration`), each a pure
  function returning a new `EngineeringSessionBuilderResult`, never
  mutating its input; a self-validating `EngineeringSessionValidator`.
  `app/services/engineering_session_service.py` - thin orchestration
  needing no application-layer translation seam at all (unlike
  Engineering Response), since its input is already a domain type.
  `POST /projects/{id}/engineering-session`
  (`+/append-response`/`/change-state`/`/update-configuration`) - no
  persistence: each endpoint accepts the current session as part of its
  own request body and returns the updated one, `session_id` generated
  only at the router (`uuid.uuid4()`), never inside the domain layer.
- Architecture impact: **new ADR (0016)** — why Session precedes
  Conversation, why Conversation will not be the aggregate root, why
  `EngineeringResponse` belongs to Session rather than the reverse, and
  why no persistence exists yet.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 19" for
  Multi-model & Reasoning. That entry's number is left unchanged here,
  for the same reason Milestones 12-18's numbering collisions were left
  unchanged rather than cascade-renumbering subsequent milestones — see
  those milestones' own numbering notes.
- Dependencies: Milestone 18 (an `EngineeringResponse` to own).

**Milestone 20 — Conversation Foundation** — *Completed*
- Objective: introduce structured engineering dialogue belonging to an
  `EngineeringSession` - explicitly not a chat log. `ConversationTurn`,
  not `ConversationMessage`, is the primary conversational unit: future
  tool execution, retrieval, agent execution, and assistant reasoning
  will all occur inside a Turn.
- Delivered: `app/domain/conversation/**` - the second-smallest
  dependency surface of any bounded context in this pipeline (only
  `app.domain.engineering_session`, to reference the owning session by
  `EngineeringSessionId`, and `app.domain.engineering_response`, to
  hold `EngineeringResponse` objects directly by reference, never
  copied - no Prompt Builder, Context Builder, Structured Retrieval,
  Graph Query, provider SDK, or `app.application.**` of any kind).
  `Conversation` -> ordered `ConversationTurn`s -> ordered
  `ConversationMessage`s, one-directional ownership only (messages
  never own turns); `ConversationStatus`
  (`ACTIVE`/`COMPLETED`/`ARCHIVED`) and `ConversationTurnStatus`
  (`STARTED`/`COMPLETED`), each with an explicit, validated transition
  table (the same convention `app.domain.project.project_lifecycle`
  established); only one Turn may be open at a time
  (`TurnAlreadyInProgressError` otherwise); `ConversationMessageRole`
  (`USER`/`ASSISTANT`/`SYSTEM`/`TOOL`/`AGENT` - the last two reserved,
  unused); deterministically-derived `ConversationMessageId`
  (`f"{turn_id}:{sequence}"`, never caller-supplied, unlike
  `ConversationId`/`ConversationTurnId`); append-only
  `ConversationTimeline`s at both the conversation and per-turn level
  (`CONVERSATION_CREATED`/`TURN_STARTED`/`TURN_COMPLETED`/
  `MESSAGE_ADDED`/`ENGINEERING_RESPONSE_ATTACHED`/`STATUS_CHANGED`);
  `ConversationBuilder` (`create_conversation`/`start_turn`/
  `append_message`/`attach_engineering_response`/`complete_turn`/
  `change_conversation_status`), each a pure function returning the
  *whole* updated `Conversation`; a self-validating
  `ConversationValidator` checking structure only, never semantics.
  `app/services/conversation_service.py` - no application-layer
  translation seam needed. `POST /projects/{id}/conversation`
  (`+/start-turn`/`/add-message`/`/attach-response`/`/complete-turn`/
  `/change-status`) - no persistence: each endpoint (except creation)
  accepts the current conversation in its own request body and returns
  the updated one.
- Architecture impact: **new ADR (0017)** — why Turn, not Message, is
  the primary conversational unit, why `EngineeringResponse` is
  referenced rather than copied, why Conversation belongs to
  `EngineeringSession` by reference rather than embedding, and why
  future tools belong to Turn.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 20" for
  Authentication & Workspace (EPIC 6). That entry's number is left
  unchanged here, for the same reason Milestones 12-19's numbering
  collisions were left unchanged rather than cascade-renumbering
  subsequent milestones — see those milestones' own numbering notes.
- Dependencies: Milestone 19 (an `EngineeringSession` to belong to) and
  Milestone 18 (an `EngineeringResponse` to reference).

**Milestone 21 — Working Memory Foundation** — *Completed*
- Objective: introduce the temporary engineering context required to
  continue reasoning during a session - explicitly not conversation
  history and not project knowledge. Fully deterministic; always
  rebuildable from its own inputs; never edited by an LLM.
- Delivered: `app/domain/working_memory/**` - depends on exactly three
  other domain contexts (`conversation`, `engineering_session`,
  `engineering_response`), no Prompt Builder, Context Builder,
  Structured Retrieval, Graph Query, provider SDK, or
  `app.application.**` of any kind. `WorkingMemory` (owned by exactly
  one `Conversation`, referenced by `ConversationId`, never embedded) ->
  ordered `WorkingMemoryEntry` objects, each typed
  (`WorkingMemoryEntryType`), sourced (`WorkingMemorySource`), and
  assigned a fixed priority/lifetime (`WorkingMemoryPriority`/
  `WorkingMemoryLifetime`) from a documented policy table, never a
  per-entry judgment. Entries populated today - `OPEN_QUESTION` (the
  last unanswered `USER` message in a still-open turn, verbatim),
  `RECENT_ENGINEERING_RESPONSE` (referenced by object, never copied),
  `ACTIVE_REFERENCE` (deduplicated evidence references from recent
  responses), `ASSUMPTION`/`CONSTRAINT` (the most recent response's own
  uncertainty reasons/warning messages, verbatim) - and entries
  deliberately reserved but never populated -
  `CURRENT_OBJECTIVE`/`CURRENT_EQUIPMENT`/`CURRENT_ELECTRICAL_AREA`/
  `CURRENT_TASK` - since identifying them from free text would require
  exactly the semantic interpretation this milestone forbids.
  `WorkingMemoryId` is deterministically derived from `ConversationId`
  (`f"{conversation_id}:working-memory"`), never caller-supplied or
  random. `WorkingMemoryBuilder` (`build_working_memory`/
  `rebuild_working_memory` - the same computation, since nothing is
  ever persisted); a self-validating `WorkingMemoryValidator` checking
  structure only, never semantics. `app/services/working_memory_service.py` -
  no application-layer translation seam needed.
  `POST /projects/{id}/working-memory/{build,rebuild}` - pure
  deterministic transformations, no AI invocation, no persistence.
- Architecture impact: **new ADR (0018)** — why Working Memory is
  neither Conversation nor Knowledge, why it must be deterministic and
  always rebuildable, why LLMs never edit it, and why entries are
  structurally derived rather than semantically interpreted.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 21" for Document
  Viewer (EPIC 6). That entry's number is left unchanged here, for the
  same reason Milestones 12-20's numbering collisions were left
  unchanged rather than cascade-renumbering subsequent milestones — see
  those milestones' own numbering notes.
- Dependencies: Milestone 20 (a `Conversation` to derive from) and
  Milestone 19 (its owning `EngineeringSession`).

**Milestone 22 — Engineering Request Classification** — *Completed*
- Objective: deterministically classify one explicit engineering
  request into a structured domain result a future orchestration
  component can use to select a workflow. Explicitly **not** generic
  chatbot intent detection, **not** semantic understanding, and
  **not** an LLM-based classifier - an explainable, replaceable rule
  engine.
- Delivered: `app/domain/engineering_intent/**` (named for roadmap
  continuity; its documented responsibility is Engineering Request
  Classification) - the **smallest dependency surface in the entire
  pipeline: no other bounded context at all**, since its input carries
  plain identifiers, the request text, and two already-extracted
  structural Working Memory signals rather than any `Conversation`/
  `WorkingMemory`/`EngineeringResponse` object. A 10-type operational
  taxonomy (`DOCUMENT_LOOKUP`, `KNOWLEDGE_QUERY`,
  `ENGINEERING_EXPLANATION`, `ENGINEERING_COMPARISON`,
  `DRAWING_REQUEST`, `VERIFICATION_REQUEST`, `NAVIGATION_REQUEST`,
  `GENERAL_ENGINEERING_REQUEST`, `UNSUPPORTED_REQUEST`,
  `AMBIGUOUS_REQUEST`); deterministic Unicode-safe normalization and
  whole-token/phrase matching (so `aprile` never fires the `apri`
  navigation rule); an explicit, immutable rule table of 12 rules
  across Italian and English signals, each independently evaluable and
  independently testable, never a large if/elif function; an explicit
  documented precedence order; ambiguity as a first-class result when
  two or more *materially distinct operations* each have strong
  evidence; categorical `HIGH`/`MEDIUM`/`LOW`/`UNRESOLVED` confidence
  from a documented policy, never a fabricated probability;
  reproducible `EngineeringIntentEvidence` (matched rule, matched
  text, token position, candidate type, strength, stable
  machine-readable description code - never hidden reasoning or
  chain-of-thought); a deterministic `EngineeringIntentId`
  (`conversation_id:turn_id:policy_version`), never random; an
  `EngineeringIntentBuilder` that constructs but never re-decides, and
  an `EngineeringIntentValidator` enforcing identity/precedence/
  confidence/ambiguity/evidence/statistics consistency structurally.
  `app/services/engineering_intent_service.py` - deliberately thin, no
  classification rule lives there.
  `POST /projects/{id}/engineering-intents/classify` - never accepts a
  caller-supplied classification result.
- Architecture impact: **new ADR (0019)** — why this is request
  classification rather than psychological intent detection, why the
  first classifier is deterministic, why LLM classification is
  excluded, why evidence is first-class, why confidence is
  categorical, why ambiguity is valid, why the result is not
  executable, how a future classifier replaces this one without
  changing the domain contract, and how the Engineering Assistant will
  consume it.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 22" for Review UI
  (EPIC 6). That entry's number is left unchanged here, for the same
  reason Milestones 12-21's numbering collisions were left unchanged
  rather than cascade-renumbering subsequent milestones — see those
  milestones' own numbering notes.
- Dependencies: none structurally (this context imports no other
  bounded context); conceptually it follows Milestone 21, since the
  structural Working Memory signals it optionally accepts come from
  there.

**Milestone 23A — Engineering Engine Foundation** — *Completed*
- Objective: introduce the application-level coordination mechanism
  that selects, plans and executes engineering workflows - implementing
  exactly **one** complete workflow (`KNOWLEDGE_QUERY`) to prove the
  architecture end to end before Milestone 23B expands the catalogue.
  Explicitly not an autonomous agent, an LLM brain, a reasoning engine,
  a chatbot, or a multi-agent orchestrator.
- Delivered: `app/domain/engineering_engine/**` — immutable planning
  and execution-result models (`WorkflowPlan`/`WorkflowStep`/
  `WorkflowExecution`/`EngineeringEngineExecutionResult`, 14 typed
  failure codes, an append-only `WorkflowExecutionTimeline`), a
  declarative `WorkflowDefinition`, a deterministic planner, and
  structural validators - importing no router, schema, FastAPI,
  persistence adapter, provider SDK, or application service, and
  depending on only two other domain contexts.
  `app/services/engineering_engine/**` — `WorkflowRegistry` (the one
  `EngineeringIntentType -> WorkflowDefinition` map, which is what
  replaces core intent branching), `StepHandlerRegistry`, a **typed**
  frozen `WorkflowExecutionContext` (never an untyped dict), ten step
  handlers that adapt to the existing Structured Retrieval, Context
  Builder, Prompt Builder, provider-neutral LLM Runtime and Engineering
  Response services without reimplementing any of them, a plan executor
  that stops at the first failure and records every remaining step as
  `SKIPPED`, the coordinating `EngineeringEngineService`, and a single
  composition root. `POST /projects/{id}/engineering-engine/execute` -
  the body never accepts a workflow plan; an unsupported intent returns
  HTTP 200 with `status="unsupported"` and runs no downstream component
  at all.
  Planning is fully deterministic (`WorkflowPlanId`/`WorkflowStepId`/
  `ExecutionId` all derived, never random); runtime output determinism
  is explicitly *not* claimed.
  Aggregate updates use **Policy B**: the engine returns explicit
  `PREPARED` proposals and never mutates `Conversation` or
  `EngineeringSession`, with the validator actively rejecting any
  result claiming `APPLIED`.
- Architecture impact: **new ADR (0020)** — why the engine is an
  application coordinator, why planning and execution are separate, why
  plans are explicit, why workflow registration replaces core intent
  branching, why only `KNOWLEDGE_QUERY` is supported initially, why the
  engine knows no provider details, why aggregate updates are explicit,
  why runtime nondeterminism differs from planning determinism, why
  failures and timelines are first-class, and how Milestone 23B adds
  workflows without changing the core.
- **Numbering note:** this milestone's number was not reserved in the
  original plan below, which already used "Milestone 23" for Dashboard
  (EPIC 6). That entry's number is left unchanged here, for the same
  reason Milestones 12-22's numbering collisions were left unchanged
  rather than cascade-renumbering subsequent milestones — see those
  milestones' own numbering notes.
- Dependencies: Milestone 22 (a classified `EngineeringIntent` to
  select a workflow for) and Milestones 13-18 (the components the
  workflow reuses).

**Milestone 23B.1 — Document Lookup Workflow** — *Completed*
- Objective: prove the Engineering Engine is genuinely extensible by
  registering a **second** workflow (`DOCUMENT_LOOKUP`) without changing
  its core - and, in doing so, establish that **not every engineering
  answer requires an LLM**. This is the first workflow that invokes no
  provider at all.
- Delivered: `DOCUMENT_LOOKUP_WORKFLOW` declared in
  `workflow_definitions.py` and registered in the composition root;
  three step handlers in their own module
  (`document_lookup_step_handlers.py`); the workflow's terminal three
  steps reuse Milestone 23A's registered handlers unchanged.
  **Document Retrieval** - the Engineering Index's read side, the
  deterministic answer to the question ADR-0002 always named as that
  context's purpose ("which documents mention X?"):
  `DocumentRetrievalRequest`/`DocumentReference`/`DocumentRetrievalResult`
  value objects, a request factory enforcing every invariant, a fixed
  documented relevance weight table (`document_relevance_policy.py`),
  pure aggregation/ranking with limit applied only after full
  deduplication, a `DocumentMetadataPort` with a SQLAlchemy adapter, and
  `app/services/document_retrieval_service.py`.
  **A non-LLM `EngineeringResponse` path**: `EngineeringResponseOrigin`
  (`LLM_INVOCATION` / `DETERMINISTIC_RETRIEVAL`), a document-lookup
  composition and assembler sharing Milestone 18's statistics and
  validation stages unchanged, and `document_references` on
  `EngineeringResponse`. Validation now enforces the origin/provider
  correspondence **in both directions**: a deterministic response naming
  a provider, model or runtime version is rejected - a response nothing
  generated must never look like one a model generated.
- Honesty constraints held: no metadata is invented (every
  `DocumentReference` field is one a repository already holds, and an
  unavailable one is reported as `null`, never filled in); relevance is
  a sum of named weighted components, never an opaque score; no document
  is read, parsed, summarized or interpreted; finding nothing is a
  `COMPLETED` execution carrying an `EMPTY` response, not a failure.
- Engine changes: **none to its decision logic.** The registry, planner,
  plan executor, engine service and structural validators were not
  modified. The additions were declarative enum members, typed context
  fields, a workflow definition, handlers, and registration. The
  step-handler *contract* (`WorkflowStepHandler`, `StepHandlerError`,
  `BaseStepHandler`) moved into its own `step_handler.py` so the core
  depends on the contract rather than on a concrete handler module - a
  behaviour-preserving extraction. No new failure code was introduced:
  every failure path reuses the existing taxonomy.
- Architecture impact: **no new ADR** — ADR-0020 already recorded that
  workflows are added by registration; this milestone exercises that
  decision rather than revising it. `engineering_response` gains
  `engineering_index` in `ALLOWED_DOMAIN_DEPENDENCIES` (a
  downstream-depends-on-upstream shared-vocabulary reuse, not a backward
  dependency), and
  `tests/architecture/test_engineering_engine_boundaries.py` gains the
  standing, executable form of the "core is closed for modification"
  claim so a future workflow cannot quietly erode it.
- Dependencies: Milestone 23A (the engine), Milestone 22 (the
  `DOCUMENT_LOOKUP` classification), and the Engineering Index
  (Milestone 8-era) for the mentions it reads.

**Milestone 23B.2 — Engineering Explanation Workflow** — *Completed*
- Objective: register a third workflow (`ENGINEERING_EXPLANATION`) that
  **explains** retrieved engineering knowledge - "spiegami il
  funzionamento della protezione 87T", "descrivi lo schema funzionale
  del trasformatore T1" - reusing the knowledge-query pipeline rather
  than building a parallel one, and again without touching the engine.
  The second LLM-powered workflow.
- Delivered: `ENGINEERING_EXPLANATION_WORKFLOW` declared in
  `workflow_definitions.py` and registered in the composition root. Its
  ten steps are the knowledge-query pipeline **step for step**, differing
  at exactly one: `BUILD_EXPLANATION_PROMPT` replaces `BUILD_PROMPT`,
  produces the same `PROMPT_PACKAGE` from the same `CONTEXT_PACKAGE`, and
  is served by the **same handler class**, parameterized at composition
  with a different Prompt Builder objective rather than duplicated.
  **`PromptObjective` in Prompt Builder** (`DIRECT_ANSWER` /
  `ENGINEERING_EXPLANATION`) - the minimum addition needed, and the one
  place the genuinely new behaviour lives. It selects between fixed,
  versioned instruction and expected-output sets declared in
  `composition_policy.py`; it is never a free-form prompt, template,
  persona or caller-supplied instruction string, so every prompt this
  system can produce stays enumerable and reviewable. Validation enforces
  that correspondence: a package whose instructions are not one of the
  declared sets is structurally invalid, however plausible its text.
- Honesty constraints held: **truthfulness constraints never vary by
  objective** - an explanation obeys the same "never invent an
  engineering fact" rule as a direct answer, because a longer answer is a
  larger opportunity to invent one, not a licence to. The explanation
  instruction set adds the two rules this objective specifically needs
  (`describe_only_what_the_evidence_covers`,
  `state_which_aspects_the_evidence_does_not_cover`), because "how does
  an 87T work" has a plausible textbook answer that owes nothing to *this*
  substation, and a plausible answer about the wrong installation is
  worse than an admitted gap. `DIRECT_ANSWER` output is byte-identical to
  Milestone 15's, so the knowledge-query prompt did not change.
- Retrieval scope: the workflow invents **no** retrieval criteria - it
  uses the same `BUILD_RETRIEVAL_REQUEST` step and handler as knowledge
  query, whose mode is derived purely from caller-supplied configuration.
  Explaining one relay by retrieving everything about the project is
  exactly the unrelated context this milestone forbids.
- Engine changes: **none to its decision logic**, and less than 23B.1
  needed. Two declarative enum members (`WorkflowType`,
  `WorkflowStepType`), a workflow definition, and two registrations. No
  new capability, no new artifact key, no new handler module, no
  execution-context change, no router change, **no new failure code** (a
  prompt failure is the existing `PROMPT_BUILD_FAILURE`, attributed to
  `BUILD_EXPLANATION_PROMPT`), and **no new response type or metadata** -
  an explanation returns an ordinary `EngineeringResponse` with
  `origin = LLM_INVOCATION` and fully populated provider metadata.
- Architecture impact: **no new ADR** — ADR-0020 already recorded that
  workflows are added by registration. One standing guarantee was added
  to `tests/architecture/test_engineering_engine_boundaries.py`:
  `test_no_handler_derives_its_behaviour_from_an_intent_or_workflow_type`,
  so a future workflow cannot reintroduce inside a handler the intent
  switch the registry exists to remove.
- Dependencies: Milestone 23A (the engine), Milestone 22 (the
  `ENGINEERING_EXPLANATION` classification), and Milestones 13-18 (the
  pipeline it reuses unchanged).

**Milestone 23B.3 — Classification-to-Retrieval Bridge** — *Completed*
- Objective: close the usability gap that made every workflow reachable
  only by a caller who already knew the graph's contents. The classifier
  decided *which workflow* a request wanted; the engine required
  retrieval criteria (a canonical entity id, lexical terms) nobody
  derived; no deterministic component connected the two. This milestone
  makes the chain traversable from a raw sentence:
  **Raw Request → Classification → Retrieval Bridge → Engine → Workflow.**
- Delivered: a new `retrieval_bridge` bounded context - immutable models,
  deterministic designation extraction, resolution against
  Canonicalization's *existing* public `normalize_entity_reference`, an
  immutable intent→retrieval **policy table** (versioned by
  `BRIDGE_POLICY_VERSION`, never an if/else chain), and structural
  validation of every configuration it emits. Plus
  `engineering_request_preparation_service.py` (the seam that composes
  classification + bridge into an `EngineeringEngineExecutionRequest`)
  and `POST /projects/{id}/engineering-requests/prepare`, whose response
  carries exactly the body `/engineering-engine/execute` accepts.
- Scope held: only the three intents with implemented workflows
  (`KNOWLEDGE_QUERY`, `DOCUMENT_LOOKUP`, `ENGINEERING_EXPLANATION`) are
  mapped. Navigation, Verification, Comparison and Drawing are refused
  with a typed `UNSUPPORTED_INTENT_MAPPING`, never given a default
  policy.
- Honesty constraints held: **no identifier is ever invented.** A
  designation that Canonicalization does not recognize ("87T", "Q52")
  becomes a lexical term, which is an honest "this system does not know
  which graph entity this names". **Retrieval is never silently
  broadened**: a request naming no designation is refused
  (`INSUFFICIENT_EVIDENCE`) rather than answered against everything; two
  distinct canonical entities are refused (`CONFLICTING_EVIDENCE`) rather
  than resolved arbitrarily; a surplus of designations is refused rather
  than truncated. Bare type words ("trasformatore") and bare numbers
  ("400") are deliberately not designations, because searching for either
  would widen retrieval past the question asked. Every refusal still
  reports the designations found, so it is inspectable rather than
  indistinguishable from a bug.
- Engine changes: **none at all.** The engine still receives an explicit
  execution request and cannot parse natural language - now enforced
  rather than asserted: architecture tests forbid it from importing the
  classifier service, the rule table, the request normalizer, or the
  bridge. The dependency runs one way only.
- A defect the design caught: the first implementation emitted an entity
  type alongside the canonical reference, which makes a Structured
  Retrieval `ENTITY_LOOKUP` request invalid. The **mode-agreement
  invariant** - the mode the bridge declares must equal the mode the
  engine derives from the same fields - caught it before it reached
  anything, and is now a standing test.
- Architecture impact: **no new ADR.** This milestone applies ADR-0019
  ("a classification result is not a command" - the bridge maps, it does
  not execute) and ADR-0020 ("the engine receives an explicit execution
  request" - preparation is a stage before it), rather than departing
  from either. New as-built reference:
  `docs/architecture/retrieval_bridge.md`; new boundary file
  `tests/architecture/test_retrieval_bridge_boundaries.py`.
- Dependencies: Milestone 22 (the classified intent it maps from),
  Milestone 11-era Canonicalization (the one canonical vocabulary), and
  Milestone 13 (the retrieval criteria vocabulary it emits).

**Milestone 24.1 — Engineering Verification Workflow** - *Completed*
- Objective: introduce the first **reasoning** workflow. Where the three
  existing workflows present retrieved knowledge, this one *evaluates* a
  statement against it: "verify that protection 87T is present", "check
  whether cable C-295 is connected to TA-12". The answer is a
  verification, not an explanation.
- Delivered: `ENGINEERING_VERIFICATION_WORKFLOW` registered in the
  composition root, its ten steps the knowledge-query pipeline with one
  difference (`BUILD_VERIFICATION_PROMPT` replaces `BUILD_PROMPT`, served
  by the *same* handler class parameterized with a new objective).
  `PromptObjective.ENGINEERING_VERIFICATION` in Prompt Builder, carrying
  the four instructions this milestone requires plus the closed four-token
  verdict vocabulary (`VERIFICATION_VERDICT_TOKENS`) - the only
  machine-readable token this system asks a model for, and the only place
  it is defined. `VerificationOutcome`/`VerificationAssessment` in
  Engineering Response, with `engineering_response_verification.py`
  reading the verdict from the answer's declared first line.
- Verification behaviour: exactly four outcomes (`SUPPORTED`,
  `NOT_SUPPORTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`) and no
  fifth category. The prompt forces the distinction that matters most -
  **absence of evidence is not evidence of absence** - because "the
  evidence does not show a differential protection on T1" and "T1 has no
  differential protection" are different findings, and in this domain
  confusing them is how a real installation gets signed off on a gap
  nobody looked for.
- Honesty constraints held: reading the verdict is **matching a declared
  protocol, not interpreting prose** - only the first line is examined,
  against four literals, with no keyword search, no negation handling and
  no scoring; a non-compliant line yields **no verdict** rather than a
  guessed one ("probably SUPPORTED" is read as no verdict). Truthfulness
  constraints are identical to every other objective. And the structural
  bound: **with no retrieved evidence the outcome is
  `INSUFFICIENT_EVIDENCE` whatever the model wrote**, because a
  `SUPPORTED` verdict could then only have come from the model's general
  knowledge - the assessment still records that the model spoke and was
  overruled, since that differs from a model that said nothing.
- Engine changes: **none to its decision logic**, and the same cost as
  23B.2 despite being a materially different kind of workflow - two
  declarative enum members, a definition, two registrations. No new
  capability, artifact key, handler module, execution-context change,
  router change, or **failure code** (a prompt failure is the existing
  `PROMPT_BUILD_FAILURE`). The engine evaluates nothing: architecture
  tests assert no engine module names a verification outcome, the
  assessment type, or any verdict literal.
- Response model: extended rather than overloaded. `verification` is a new
  optional field because `EngineeringResponseStatus.UNSUPPORTED` already
  means "the provider returned no usable text", and reusing it for "the
  evidence does not support the statement" would make two entirely
  different findings indistinguishable; warnings and uncertainties cannot
  express `SUPPORTED` at all.
- Also in scope, deliberately: a `VERIFICATION_REQUEST` row in the
  Retrieval Bridge policy table, so a raw verification sentence is
  preparable end to end. It searches lexically for **every** designation
  (a relational claim names two things; an entity lookup would carry one
  and drop the other) and expands the neighborhood by one hop, because a
  relational claim is settled by relationships.
- **Naming note:** the milestone brief names
  `EngineeringIntentType.ENGINEERING_VERIFICATION`; the classifier has
  published `VERIFICATION_REQUEST` since Milestone 22, and an intent-type
  value is a contract (CLAUDE.md §16). The workflow, workflow type and
  prompt objective are named "engineering verification"; the intent keeps
  its published name. Adding a synonym member would have created two names
  for one concept.
- Architecture impact: **no new ADR** - ADR-0020 already covers workflow
  registration and ADR-0015 the Engineering Response boundary; this
  milestone applies both. The one genuinely new decision - that a
  *declared token protocol* is not semantic parsing - is recorded in
  `engineering_response_verification.py`'s own docstring and in
  `engineering_engine.md`, and is narrow enough that an ADR would
  overstate it.
- Dependencies: Milestone 23A (the engine), Milestone 22 (the
  `VERIFICATION_REQUEST` classification), 23B.2 (`PromptObjective`), and
  Milestones 13-18 (the pipeline it reuses unchanged).

**Milestone 24.2 — Engineering Comparison Workflow** - *Completed*
- Objective: compare two explicitly identified engineering subjects using
  only governed project evidence - "confronta il trasformatore T1 con
  T2", "quali differenze ci sono tra il montante M1 e M2?". The first
  workflow with **two subjects**, and the first whose *pipeline* differs
  rather than only its prompt.
- Delivered, end to end:
  **Preparation** - `comparison_bridge.py` derives exactly two typed
  operands from a classified `ENGINEERING_COMPARISON` request, under a
  `COMPARISON_OPERAND_POLICY` applied to each side independently.
  **Retrieval** - two independent steps (`EXECUTE_LEFT_RETRIEVAL`,
  `EXECUTE_RIGHT_RETRIEVAL`) reusing Structured Retrieval unchanged.
  **Context** - a `ComparisonContextPackage` holding **two whole
  `ContextPackage`s**, each assembled by the existing builder, paired but
  never merged. **Prompt** - a `ENGINEERING_COMPARISON` objective with
  `LEFT_KNOWLEDGE`/`RIGHT_KNOWLEDGE` as separate typed sections.
  **Response** - a `ComparisonAssessment` on the ordinary
  `EngineeringResponse`.
- The rules that carry the weight:
  **Exactly two operands.** Fewer is `INSUFFICIENT_EVIDENCE` and the
  missing one is never inferred; more is `CONFLICTING_EVIDENCE` and the
  surplus is never truncated - choosing two of three would compare a pair
  the request did not ask for.
  **Order is structural, not conventional.** `left`/`right` are named
  fields on every model - execution request, execution context, context
  package, prompt sections - so there is no index to transpose. "Compare
  A with B" cannot silently become "compare B with A", which matters
  because additions, removals and every directional finding invert.
  **A missing side is never a difference.** When either side retrieved no
  evidence the outcome is structurally forced to `INSUFFICIENT_EVIDENCE`,
  whatever the model wrote. Given evidence for T1 and none for T2, a
  fluent answer reads "T2 lacks the differential protection T1 has" -
  which is a statement about what the index covers, not about the
  installation, and an engineer acting on it would commission a change on
  the strength of a gap. The prompt also renders an evidence-less side as
  an explicit statement that the project holds none, rather than as an
  empty section that invites the wrong inference.
- Outcome vocabulary: `COMPARABLE`, `INSUFFICIENT_EVIDENCE`,
  `CONFLICTING_EVIDENCE` - read from the same declared first-line protocol
  a verification verdict uses. Deliberately **not** "same" versus
  "different": a real comparison of two montanti usually contains both
  changed and unchanged aspects, so a top-level same/different verdict
  would force a false choice.
- **Structured findings are deliberately absent.** The prompt asks for
  findings grouped under ADDED / REMOVED / MODIFIED / UNCHANGED, and they
  stay **prose in the response body**. Extracting them into typed data
  would mean parsing free text to manufacture engineering findings -
  exactly what this system refuses. The limitation is recorded on
  `ComparisonAssessment` itself and is the milestone's top technical debt;
  it dissolves the day the runtime can return structured output.
- Engine changes: **none to its decision logic**, and all additions
  declarative - a workflow type, six step types, five artifact keys, a
  typed `ComparisonOperandCriteria` on the execution request, five
  execution-context fields, one handler module, six registrations. The
  engine's *vocabulary* grew; its logic did not. It selects, plans and
  executes exactly as before, and evaluates and compares nothing itself.
- Failure taxonomy: **no new codes.** Fewer/more operands reuse the
  bridge's `INSUFFICIENT_EVIDENCE`/`CONFLICTING_EVIDENCE`; a missing
  operand at execution is `INVALID_EXECUTION_REQUEST`; each side's
  retrieval failure is `RETRIEVAL_FAILURE` **attributed to its own step**,
  which is precisely why retrieval is two steps rather than one - a
  combined step would report a left and a right failure identically.
- Architecture impact: **no new ADR** - ADR-0020 covers registration and
  ADR-0015 the Engineering Response boundary. Four standing guarantees
  were added: no engine module names a comparison outcome, assessment
  type or finding literal; the engine imports neither the comparison
  reader nor the preparation policy; comparison instructions exist only in
  Prompt Builder; and **provider adapters and the runtime remain unaware
  of comparison semantics**.
- Dependencies: Milestone 23A (the engine), 22 (the classification, whose
  taxonomy already published `ENGINEERING_COMPARISON`), 23B.2
  (`PromptObjective`), 23B.3 (the bridge it extends), and 13-18.

**Milestone 25.1 — Document Ingestion Pipeline** - *Completed*
- Objective: make project knowledge enter the system through a
  deterministic, governed pipeline. Every milestone before this one turned
  *already-reviewed* knowledge into answers; this is the first on the
  input side. Its responsibility is **orchestration, lifecycle and state**
  - explicitly **not** extraction.
- Delivered: a new `document_ingestion` bounded context - an explicit
  `IngestionState` lifecycle (`UPLOADED → QUEUED → PROCESSING →
  PROCESSED/FAILED`, with `FAILED → QUEUED` for retry) governed by a
  `VALID_TRANSITIONS` table modelled on `project_lifecycle.py`'s own
  shape; a typed immutable `IngestionJob`; a pure `execute_ingestion_pipeline`;
  an `IngestionJobRepository` port with a SQLAlchemy adapter; the
  `document_ingestion_jobs` table (additive migration `c7a41d8f2b16`);
  `document_ingestion_service.py`; and five endpoints.
- What it deliberately does **not** do, enforced by architecture test
  rather than by intent: it reads no document contents (no parsing, no
  OCR), uses no LLM, no embeddings and no provider, imports neither Prompt
  Builder nor the Engineering Engine, and **writes neither the Engineering
  Index nor the Project Knowledge Graph**. The repository port's own
  abstract-method set is asserted, so the exclusions are a matter of
  contract rather than discipline.
- The lifecycle rules that carry the weight:
  **Every transition is validated** and an illegal one raises - a job that
  reached `PROCESSED` without passing through `PROCESSING` would be a
  record of something that never happened. Every state pair is asserted
  legal or illegal by test, not a handful of happy paths.
  **`PROCESSING` is persisted before the pipeline runs**, so a job that
  fell over mid-execution does not still read as `QUEUED`.
  **One job in flight per document**; a second request raises rather than
  racing. Re-ingestion is a *new* job, so what was processed when is never
  overwritten, and the accumulated jobs are the document's audit trail.
  **Retry keeps the same record**, incrementing `attempt_count` - the
  attempt history belongs to the job an engineer is already looking at.
- The document snapshot is a **copy taken at ingestion time**, not a live
  read: a job that silently started describing the current document would
  make its own recorded outcome unexplainable. Nothing in it is derived or
  inferred - a snapshot that added a fact would be an extraction.
- **A correction worth recording.** The first implementation refused
  `DocumentFormat.OTHER` as unsupported. Testing the real upload path
  showed the upload endpoint never sets `file_format` at all, so *every*
  uploaded document carries `other` - refusing it would have meant judging
  a document on a field nobody ever filled in (the same
  absence-of-evidence error this system refuses everywhere else) and would
  have left the pipeline unable to mark any real document ready.
  `UNSUPPORTED_FORMAT` now claims exactly one thing: a format value this
  system has no definition of, which is a data-integrity condition.
- Failures: `DOCUMENT_NOT_FOUND` and `UNSUPPORTED_FORMAT` produce a
  **recorded `FAILED` job** rather than an exception, so the attempt stays
  visible; only `DUPLICATE_INGESTION_REQUEST` and
  `INVALID_LIFECYCLE_TRANSITION` - the two cases where no job could
  legitimately exist - raise.
- Architecture impact: **no new ADR.** ADR-0002 already governs what the
  Engineering Index is for and ADR-0005 document scope; this milestone
  applies both by staying out of them. New as-built reference:
  `docs/architecture/document_management.md`, which also closes a
  pre-existing documentation gap - documents had no architecture note of
  their own.
- Dependencies: the existing document repository, and Milestone 23B.1's
  `DocumentMetadataPort` (reused unchanged - this context adds no second
  contract onto documents).

**Milestone 25.2 — Document Identity and Content Access** - *Completed*
- Objective: give the input side of the pipeline the minimum it needs to
  know *which* document it is handling - deterministic format
  classification, content identity, and a narrow read-only path to the
  bytes - without crossing into extraction.
- Delivered: a new `document_identity` bounded context (`ClassifiedFormat`
  and its evidence value objects, the `format_signatures` rule tables, a
  pure `classify_document_format`, `resolve_content_identity`, and three
  narrow ports); `FilesystemDocumentContentAdapter`,
  `SqlAlchemyDocumentStorageLocation` and
  `SqlAlchemyDocumentFormatRegistry`; `document_identity_service.py`;
  seven nullable identity columns on `document_ingestion_jobs` (additive
  migration `d5b93e17ca40`); format classification wired into the upload
  endpoint; and `scripts/maintenance/backfill_document_formats.py`.
- **One rule source.** Upload, ingestion and the backfill all classify
  through the same classifier, which reads only `format_signatures.py`.
  An architecture test asserts - on the syntax tree, not on prose - that
  nothing else declares a signature, a MIME map or an extension map. Two
  copies of a format rule would let the system disagree with itself about
  what a document is.
- **Evidence is ranked, and the ranking is the whole design.** A readable
  content signature decides absolutely, because the bytes are the document
  and the filename is a label somebody typed; the overruled evidence is
  still recorded rather than discarded. Without a signature, a MIME type
  and an extension that disagree **deadlock** into `CONFLICTING` - both
  are claims *about* the file rather than facts *from* it, so neither can
  arbitrate the other, and picking one would be the arbitrary
  classification this milestone forbids. A ZIP header abstains rather than
  guessing between `xlsx` and `docx`. Nothing with an opinion yields
  `UNKNOWN`, never a guess.
- **Identity is not deduplication.** Identical checksums are recorded and
  nothing is concluded from them. Whether a repeated upload is a
  duplicate, a re-issue under a new revision, or the same drawing filed
  against two projects is a question about the *documents*, and answering
  it here would invent a policy nobody stated.
- An **empty file fails** rather than hashing to SHA-256's empty digest -
  a real value, which is exactly the problem: recorded as an identity it
  would make every empty document look like the same document. If the
  bytes read disagree with the reported size, the attempt fails as
  `CHECKSUM_FAILURE`; a digest describing bytes other than the ones
  reported would be a lie.
- **Reads never rewrite.** An ingestion records the detected format
  beside the stored one and leaves the document row untouched; correcting
  it is the backfill's job, and the backfill plans without writing so an
  operator can read the report first. `record_format` sits on its own
  narrow port precisely so nothing calls it during a read. If the content
  changed since a prior job, the new job records the new checksum and the
  historical job is left exactly as it was.
- **Backwards compatibility.** Every new column is nullable and every new
  snapshot field defaults to `None`, so jobs written before this milestone
  read back as jobs that examined no content - which is the truth about
  them rather than a gap to fill in. A caller with no content port still
  runs the 25.1 metadata-only pipeline: "nobody looked" and "the content
  is broken" are different facts, and collapsing them would report every
  such ingestion as broken storage. Documents stored as `other` remain
  readable and are never modified during a normal read.
- What it deliberately does **not** do, enforced by architecture test: no
  parsing, OCR, text extraction, embeddings or LLM anywhere in the
  context; no Engineering Index or Knowledge Graph write; no domain import
  of a filesystem, cloud-storage client or ORM - the domain neither calls
  `open` nor constructs a path, asserted on the syntax tree; and no fifth
  bounded context gained storage access.
- Architecture impact: **no new ADR.** The milestone introduces no new
  persistence strategy and no external dependency - it applies the
  existing Ports & Adapters discipline to storage. Reference updated:
  `docs/architecture/document_management.md`.
- Dependencies: Milestone 25.1 (the ingestion lifecycle it extends) and
  the existing document repository.

**Milestone 26.1 — Canonical PDF Representation** - *Completed*
- Objective: convert a PDF into a deterministic, loss-minimising,
  reproducible representation suitable for future engineering
  extraction - and make that representation, rather than the original
  file, the thing all downstream semantic processing reads.
- Delivered: a new `canonical_pdf` bounded context (the
  `CanonicalPdfDocument → Page → Block → Span` value hierarchy, a
  construction factory enforcing every invariant, a typed failure
  taxonomy, `PdfParserPort` and `CanonicalRepresentationRepository`);
  `PyMuPdfParser`; a SQLAlchemy repository over four typed tables
  (additive migration `b7ded1e07fcd`); `canonical_pdf_service.py`; and
  two endpoints.
- **Why extraction must consume the representation, not the PDF** - the
  load-bearing decision of the milestone. Re-parsing a PDF next year
  under a different library release can legitimately yield different
  text; if extraction read the file, a claim already in the Knowledge
  Graph could silently stop being supported by the document it came
  from, with nothing able to show what changed. The representation is a
  fixed value bound to one checksum, one parser version and one
  representation version, so provenance resolves to a specific span of a
  specific representation of specific bytes. Confining PDF decoding to
  one adapter also means downstream milestones inherit *resolved*
  failures rather than re-handling encryption, corruption and missing
  text. The repository port exposes no method returning a path, a handle
  or raw content - the rule is structural, not advisory.
- **It records; it does not interpret.** No merged paragraphs, no
  rewritten or repaired text, no removed headers, no inferred tables,
  lists, headings or sections, no entities, and no geometric re-ordering
  of blocks - on a multi-column wiring schedule a sorting heuristic would
  be this system asserting how the page should be read. There is nowhere
  in the model *or the schema* to record such a thing, asserted by test
  on both.
- Preserved because the parser supplies it: page number, the parser's own
  reading order, verbatim text, bounding boxes, font family, font size,
  bold and italic. Image blocks are recorded as observed rather than
  dropped; spans keep the `line_index` they came from, so the parser's
  line grouping survives without anyone re-deriving it from coordinates.
- **Deterministic and idempotent.** The same bytes always produce an
  equal representation - asserted directly, which is possible because the
  value objects are frozen and carry no timestamp. Re-running finds the
  stored representation and re-uses it (`reused: true`, `200` rather than
  `201`); changed bytes carry a different checksum and produce a new
  representation *alongside* the old, so a conclusion drawn from last
  year's revision stays explainable. A unique constraint on
  `(document_id, content_checksum, representation_version)` is the
  persistence-level backstop.
- **Only PDF, and no OCR.** Everything else produces a typed
  `UNSUPPORTED_FORMAT` - a drawing is not badly-formed text. A PDF with
  no text span anywhere fails with `NO_EXTRACTABLE_TEXT`, which names an
  observation and refuses to diagnose: it does not claim the document is
  scanned, because nothing this milestone reads could support that.
  Persisting it would hand every future extractor a document that appears
  to say nothing, indistinguishable from one that genuinely does.
- Failures are each named rather than collapsed: `DOCUMENT_NOT_FOUND`,
  `UNSUPPORTED_FORMAT`, `NOT_READY_FOR_EXTRACTION`, `CONTENT_NOT_FOUND`,
  `CONTENT_INACCESSIBLE`, `EMPTY_CONTENT`, `ENCRYPTED_DOCUMENT`,
  `CORRUPTED_DOCUMENT`, `PARSER_FAILURE`, `EMPTY_DOCUMENT`,
  `NO_EXTRACTABLE_TEXT`, `REPRESENTATION_PERSISTENCE_FAILURE`. The five
  shared with ingestion carry identical values and are asserted equal by
  test, but are restated rather than imported - ingestion knows nothing
  about PDF internals and `ENCRYPTED_DOCUMENT` would mean nothing on an
  ingestion job.
- Reuse rather than reinvention: the flow starts at Milestone 25.1's
  `READY_FOR_EXTRACTION`, reads bytes through Milestone 25.2's
  `DocumentContentPort` and `DocumentStorageLocationPort`, and carries
  25.2's checksum onto the representation. The parser port takes **bytes,
  not a path**, so bypassing the content port is impossible rather than
  merely discouraged. PyMuPDF was already a dependency; nothing new was
  added.
- **Debt recorded, not hidden - and since resolved.** Four modules
  decoded PDFs before this milestone: `pdf_text_extractor` (live, via the
  upload endpoint's Knowledge Graph path) and three with no callers at
  all. All four were enumerated in an architecture test so the set stayed
  closed, and **Milestone 26.2 deleted every one of them** and migrated
  the upload path onto the canonical pipeline.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency; the milestone applies the existing Ports &
  Adapters discipline to PDF decoding. Reference updated:
  `docs/architecture/document_management.md`.
- Dependencies: Milestone 25.1 (the ingestion lifecycle it starts from)
  and 25.2 (content access and identity).

**Milestone 27.1 — Canonical Text Segmentation** - *Completed*
- Objective: build the reusable, semantic-neutral text segmentation layer
  every future extractor consumes, so that turning page layout into
  textual structure is decided once, recorded, and versioned - rather
  than re-implemented, slightly differently, inside each extractor.
- Delivered: a new `canonical_text` bounded context (the
  `Document → Section → Paragraph → Line → Token` value hierarchy, the
  `SpanProvenance` chain, a pure segmenter, a pure normaliser, a typed
  failure taxonomy and `CanonicalTextRepository`); a SQLAlchemy
  repository over five typed tables (additive migration `26978efc7d15`);
  `canonical_text_service.py`; and two endpoints.
- **What a section is, and why it is the whole design.** A section **is a
  page**. Not a chapter, not a heading, not an engineering section -
  those would have to be inferred, and a heading detector deciding
  "TECHNICAL DATA" was a section title would be guessing from font size,
  with every extractor downstream inheriting the guess as though it were
  an observation. Segmentation uses only boundaries the parser already
  recorded: page transitions, block boundaries, the line index Milestone
  26.1 preserved on every span, and whitespace. Nothing measures a gap or
  compares a font size.
- **Why extractors must consume the segmentation rather than PDF
  layout.** A block, a bounding box and a font size are facts about ink;
  "these lines form a paragraph" is a conclusion drawn from them. Drawn
  independently by five extractors, it would be drawn five slightly
  different ways, and two of them disagreeing about where a paragraph
  ends would produce two irreconcilable answers about one document.
  Deciding it once and versioning it under `segmentation_version` means a
  rule change produces a *new* segmentation beside the old, and
  conclusions drawn under the previous rules stay explainable.
  `CanonicalTextRepository` exposes no page, block or bounding box, and
  an architecture test pins the set of modules permitted to import the
  canonical PDF models at all.
- **Provenance is the point.** Every token carries
  `document → page → block → span → character range`, with offsets into
  the originating span's own text so the substring can be recovered and
  checked without re-parsing anything. Stored as columns on the token
  row rather than as joins, because "find this term and tell me exactly
  where it sits" is the read every extractor performs. A token never
  straddles two spans - a word split across a style boundary yields two
  tokens - because a merged token would point at no single span, and the
  chain is worth more than the tidier word.
- **Normalisation is NFKC plus a strip, and nothing else.** No case
  folding (`mV`, `kV` and `MV` are three different things), no
  abbreviation expansion (`CB` → "circuit breaker" is an ontology lookup
  wearing a normaliser's clothes), no spelling correction, no
  engineering normalisation, no stemming. Both forms are stored: the
  original is what the document says, the normalised form is what two
  documents compare on. **The known cost is pinned by test:** NFKC folds
  superscripts, so `mm²` normalises to `mm2` - acceptable only because
  the original is preserved verbatim and the provenance points at the
  exact characters. Changing it means bumping the segmentation version
  and re-segmenting, which is what that version is for.
- **Deterministic and idempotent.** No value object carries a timestamp,
  so "the same representation always segments the same way" is asserted
  directly by equality. The stored key is
  `(document_id, content_checksum, segmentation_version)`: re-running
  re-uses the stored result (`reused: true`, `200` rather than `201`), a
  changed document or changed rules produce a new segmentation alongside
  the old.
- Empty structures are kept, never pruned: an empty page is still a page,
  and dropping it would renumber every section after it and break the
  correspondence with the page an engineer is looking at. An image block
  becomes an empty paragraph for the same reason. A representation that
  segments to *zero* tokens is refused rather than stored - it would look
  to every extractor like a document that says nothing.
- Failures: `CANONICAL_REPRESENTATION_MISSING`,
  `INVALID_CANONICAL_REPRESENTATION` (caught on read, before segmentation
  begins), `UNSUPPORTED_REPRESENTATION_VERSION` (refusing is the only
  safe answer - a newer representation may carry fields this code would
  misinterpret), `SEGMENTATION_FAILURE`,
  `REPRESENTATION_PERSISTENCE_FAILURE`. The one shared with Milestone
  26.1 carries an identical value, asserted by test, but is restated
  rather than imported.
- What it deliberately does **not** do, enforced by architecture test:
  no entity, equipment or cable recognition; no Engineering Index or
  Knowledge Graph write; no LLM, Prompt Builder or Engineering Engine;
  no ontology lookup; and **no access to PDF storage or any PDF library**
  - the domain imports the canonical PDF models and its own modules, and
  nothing else. A service test additionally points a document's
  `file_path` at a file that never existed and segments it successfully,
  which is the strongest available proof that the original PDF is not
  read.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. Reference updated:
  `docs/architecture/document_management.md`.
- Dependencies: Milestone 26.1 (its only input).

**Milestone 26.2 — PDF Consumption Consolidation** - *Completed*
- Objective: make the canonical pipeline the *only* PDF path. Milestones
  26.1 and 27.1 built it; the upload endpoint was still quietly running a
  second one, and three further modules could decode a PDF as well.
- Delivered: `canonical_text_assembler` (a pure, documented rendering of
  a segmentation into text); `document_pipeline_service`, the application
  workflow that sequences ingestion, canonicalisation and segmentation
  and hands the assembled text to an injected consumer; the upload router
  migrated onto that workflow; and the four pre-canonical decoders
  deleted.
- **Repository analysis first, deletion second.** Every PDF-touching
  module was traced through imports, composition roots, routes, tests,
  scripts and the frontend, and checked for dynamic loading (`importlib`,
  `__import__`, `pkgutil` - none exists anywhere in `app/`).
  `pdf_text_extractor` had exactly one caller: the upload endpoint. The
  other three - and the whole `services/intelligence/` package their
  helpers belonged to - had none.
- **One decoder.** `app/infrastructure/canonical_pdf/pymupdf_parser.py`
  is now the only module in the application permitted to import a PDF
  library, asserted as an exact set rather than a subset. The retired
  files are asserted absent *from the filesystem* as well as unimported,
  because a restored file with no importers yet would pass every
  import-based check while sitting there waiting to be used.
- **The Knowledge Graph receives a string.** It is handed assembled text
  and nothing else - no document id, no storage reference, no
  segmentation, no parser object - so no consumer can reach the bytes for
  itself. Architecture tests assert the whole live chain
  (`knowledge_graph` → `services/ai/**` → `services/topology/**`) imports
  no PDF library, no content or storage-location port, no filesystem
  adapter, and opens no file.
- **Text assembly preserves the engineering text.** It uses **original**
  token text, never the NFKC-normalised form, because normalisation folds
  `mm²` into `mm2`. Regression tests assert that superscripts,
  subscripts, Greek letters (`Ω`, `Δ`, `φ`) and electrical symbols (`±`,
  `°`, `≤`, `×`) survive the whole pipeline into the text delivered
  downstream. The page marker is kept verbatim from the retired
  extractor, since that string is part of what the consumer reads.
- **Failures are named by stage.** The workflow reports which of
  ingestion, canonicalisation, segmentation, assembly or the downstream
  consumer stopped it, carrying **that stage's own typed code** rather
  than translating everything into a fourth vocabulary. The endpoint's
  `status` field keeps its long-standing values so existing clients see
  no change; the new `failure` object beside it means "failed" is no
  longer the end of the story.
- **Two intentional behaviour changes, both documented rather than
  smoothed over.** (1) Runs of whitespace inside a line collapse to a
  single space, and paragraph transitions become a blank line - the
  current entity patterns are whitespace-tolerant, and no designation's
  characters change. (2) A project-scoped upload now creates an ingestion
  job, because the upload *is* the pipeline; two Milestone 25.1 API tests
  were updated to count relative to that job rather than assume its
  absence.
- **A pre-existing finding worth recording.** The live Knowledge Graph
  extractor (`app/services/ai/extractor.py`) is **LLM-backed** and
  requires `ANTHROPIC_API_KEY`; without one the upload has always
  reported `failed`. This milestone neither introduced nor changed that -
  but it now names the stage, so the condition is visible instead of
  anonymous.
- Architecture impact: **no new ADR.** The milestone removes code and
  enforces boundaries the existing ADRs already imply; it introduces no
  new persistence strategy, dependency or architectural decision.
- Dependencies: Milestones 25.1, 25.2, 26.1 and 27.1 - it is the
  consolidation those four made possible.

**Milestone 28.1 — Engineering Evidence Extraction Foundation** -
*Completed*
- Objective: introduce a governed layer between canonical text and all
  future engineering knowledge construction, so that what a document was
  *observed* to contain is recorded deterministically, with provenance
  and a rule version, before anybody decides what it *means*.
- Delivered: a new `engineering_evidence` bounded context (evidence value
  objects, provenance, a pattern catalogue, a unit catalogue, a rule
  catalogue, an exact-`Decimal` quantity policy, a pure extractor, set
  validation and `EngineeringEvidenceRepository`); a SQLAlchemy
  repository over three typed tables (additive migration
  `24d9fadeeb4c`); `engineering_evidence_service.py`; and two endpoints.
- **Evidence is an observation, not an entity** - the decision the whole
  milestone rests on. An item says "the characters `20 kV` appeared on
  page 3, paragraph 2, line 1, tokens 4-5, under rule `voltage_value`
  version 1.0". It does not say a transformer exists, nor which one. A
  quantity beside a designation yields **two independent observations**:
  adjacency is a fact about ink, attribution is a judgement. There is no
  field on the model and no column in the schema in which "belongs to"
  could be written, and an architecture test asserts both stay that way.
- Supported catalogue: `DESIGNATION`, `VOLTAGE_VALUE`, `CURRENT_VALUE`,
  `POWER_VALUE`, `CABLE_SECTION_VALUE`. **`MANUFACTURER_NAME` is omitted,
  with reason**: recognising a manufacturer needs a list of
  manufacturers, and this repository has none —
  `ontology/attributes/manufacturer.yaml` is a free-text attribute with
  no enumerated values. Writing one would be an arbitrary, incomplete
  dictionary presented as a deterministic rule.
- **Designation recognition is conservative.** Three declared shapes,
  each requiring letters and digits together: `T1`/`QMT01`, `52-Q1`,
  `+E01-QA1`. Bare uppercase words, bare numbers and lower-case tokens
  are rejected — not every capitalised token is a designation, and the
  cost is asymmetric: a missed designation is a gap a later milestone can
  fill, a false one is an entity somebody has to disprove. The equipment
  category is never inferred from the designation.
- **Quantities are exact.** `Decimal` in the domain and `Numeric` in the
  schema, never `float`. The separator policy is explicit about what it
  cannot read: `1.250` is 1250 in one convention and 1.25 in the other,
  so it is recorded `AMBIGUOUS` and **carried without a normalised
  value** — a reviewer can settle it, and a guess could not be un-guessed
  once it had become a rated value in the graph.
- **The unit catalogue is small and closed.** No case folding (`mV`,
  `kV` and `MV` are three different quantities), no inferred units (a
  bare `630` beside "potenza" is a number beside a word), and conversions
  only where exact (kV→V; `mm²` has no base unit because there is nothing
  exact to convert it to).
- **Provenance is recorded at match time, never reconstructed.** Every
  item cites page, section, paragraph, block, line, token range and the
  character ranges of the canonical spans it drew from. Character ranges
  exclude trimmed punctuation, so `400 V,` points at `400 V`. An
  observation may cite **two spans** when a style changes mid-value, and
  never crosses a line — a value split across a line boundary is not
  extracted rather than recorded with an approximate location.
- **The extractor reads original token text, never the NFKC form.** The
  normalised form folds `mm²` into `mm2` and `I₁` into `I1`; matching on
  it would degrade the engineering symbols an item records and would
  silently promote a subscripted signal name to a designation.
  Regression tests cover `mm²`, `m³`, `Ω`, `Δ`, `φ`, `±`, `°`, `≤`, `×`
  and `I₁`. The canonical text normalisation model itself is unchanged —
  no blocker required redesigning it.
- **Statuses are categorical, deliberately not percentages.** `OBSERVED`
  and `AMBIGUOUS` are persisted; `REJECTED` candidates are diagnostics
  and never reach storage. A numerical confidence would have to be
  calibrated against something, and a regular expression either matched
  or it did not — inventing "0.85" would dress a boolean up as a
  measurement.
- **Rules are findable.** One pattern module, one unit module, one rule
  catalogue; architecture tests assert nothing else in the context calls
  `re.compile`, constructs a `UnitDefinition`, or writes a unit spelling
  as an executable literal. The extractor orchestrates and matches
  nothing itself — an inline `if` there would be a rule nobody could
  find, version or review, while every stored item cites a rule version.
- Ten typed failures, none collapsed into a generic runtime error.
- What it deliberately does **not** do, enforced by architecture test: no
  PDF library, no content or storage-location port, no filesystem; no
  LLM, Prompt Builder or Engineering Engine; no Engineering Index or
  Knowledge Graph write. A service test additionally points a document's
  `file_path` at a file that never existed and extracts successfully,
  which is the strongest available proof that no document is reopened.
- **Debt left standing, on purpose.** The live Knowledge Graph upload
  path still performs ad-hoc LLM extraction from assembled text.
  Migrating it is a separate milestone; an architecture test pins the
  current absence of a dependency between the two, so that change will be
  deliberate rather than incidental.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. New as-built reference:
  `docs/architecture/engineering_evidence.md`.
- Dependencies: Milestone 27.1 (its only input) and, through it, 25.1,
  25.2 and 26.1.

**Milestone 28.2 — Engineering Evidence Evaluation Framework** -
*Completed*
- Objective: make the platform able to measure the quality of its own
  extraction rules, permanently and continuously, before Entity
  Resolution is built on top of them. An extractor cannot grade itself,
  and a rule nobody has measured is a rule nobody knows the cost of.
- Delivered: a new `evidence_evaluation` bounded context (corpus models,
  a read-only corpus port, evaluation and regression models, exact
  metrics, a pure matcher, a pure engine, a regression detector, typed
  failures and a report port); a version-controlled reference corpus in
  `app/domain/evidence_evaluation/corpora/`; a YAML corpus loader and a
  SQLAlchemy report repository; four tables (additive migration
  `58327939f9a5`); `evidence_evaluation_service.py`; and five endpoints.
- **The corpus is the definition of correct, so it is data, not code.**
  It lives in the repository beside the ontology's YAML, is loaded and
  validated on read, and there is **no `save`** on the corpus port -
  asserted by test. Changing what "correct" means is a reviewed edit and
  a corpus version bump, so evaluations recorded against the old version
  stay valid statements about the old definition. A test additionally
  asserts the reference corpus is never constructed inline in the tests
  that measure against it: expectations editable beside the assertion
  would let anybody move the goalposts.
- **Annotations reuse the evidence domain model** - `EvidenceType`,
  `EvidenceStatus`, `EvidenceProvenance`, `EngineeringQuantity`,
  `DesignationValue`. A parallel annotation model would drift, and a
  format able to express something the evidence model cannot is an
  annotation nobody could satisfy. The one field omitted is
  `evidence_key`: asking an annotator to compute the extractor's SHA-256
  would be asking them to run the extractor.
- **Only exact matches count, and provenance is part of the match.** An
  observation with the right text in the wrong place is a false positive
  **and** a false negative - a consumer that trusted its location would
  read the wrong part of the document. There is no "near miss" outcome,
  which would let a rule that misplaces values look almost right. Two
  named provenance policies exist (`EXACT`, `LOCATION_ONLY`), and the one
  used is recorded on every report so a comparison is never between two
  definitions of "match". Approximate *text* matching is absent by
  design; introducing it would require its own named, versioned policy.
- **Metrics are exact and honest about being undefined.** `Decimal`
  quantised to six places, never `float`. F1 is computed from the counts
  as `2·TP / (2·TP + FP + FN)` rather than from already-quantised
  precision and recall - deriving it that way loses a digit, and two
  evaluations differing only in that digit would read as a regression (a
  real defect this milestone found and fixed). Precision with no
  predictions is `null`, not 0 or 1: reporting 0 would claim the
  extractor was wrong about things it never said.
- **Regression reports name the items, not just the numbers.** New and
  resolved false positives and negatives, metric deltas, and rule version
  changes beside them. A comparison across corpus versions is flagged
  `comparable: false` - still produced, but a metric that moved when the
  corpus grew has said nothing about the rules.
- **Reports are insert-only.** No `update`, no `delete` on the port: the
  history is what regression detection is made of. Evaluation executes
  the extractor over corpus documents rather than reading stored
  evidence, because an evaluation against stored evidence would measure
  what was stored on some past day rather than what the current rules
  produce - asserted by architecture test.
- **The measured baseline**, `substation_reference` 1.0 at extraction
  policy 1.0: 17 true positives, 0 false positives, 1 false negative -
  precision 1.000000, recall 0.944444, F1 0.971429. The annotations were
  written by reading the document text, and 17 of 18 agreed with the
  extractor including full provenance. The single miss is `TR-1`: the
  designation patterns do not recognise letters-hyphen-digits, and an
  engineer would call that a designation. It is annotated deliberately so
  the gap is measured rather than forgotten, and so the milestone that
  closes it can *show* recall rising.
- What it deliberately does **not** do, enforced by architecture test: no
  Entity Resolution, no Knowledge Graph, no Engineering Index write, no
  LLM, no Engineering Engine, no PDF library and no document storage -
  a corpus is self-contained in the repository, which is what lets an
  evaluation run in CI and mean the same thing next year. It also cannot
  write engineering evidence: a measurement must not modify what it
  measures.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. Reference updated:
  `docs/architecture/engineering_evidence.md`.
- Dependencies: Milestone 28.1 (the rules it measures) and 27.1 (the
  segmenter the corpus is materialised through).

**Milestone 29.1 — Engineering Entity Resolution Foundation** -
*Completed*
- Objective: turn engineering observations into engineering *objects*,
  deterministically, so that a later milestone can populate the
  Knowledge Graph from entities rather than from document text.
- Delivered: a new `engineering_entities` bounded context (entity value
  objects, an evidence-reference model, a versioned resolution rule
  catalogue, a pure resolver, set validation, typed failures and
  `EngineeringEntityRepository`); a SQLAlchemy repository over three
  typed tables (additive migration `46ec4e0fe42f`);
  `engineering_entity_service.py`; and four endpoints.
- **Evidence, entity, node are three different things** - the
  distinction the layer exists to make. Evidence says "I observed this,
  here, under this rule". An entity says "these observations refer to the
  same engineering object". A graph node says something about the
  installation, and this milestone writes none. An entity is a
  *deterministic hypothesis*: it follows from a stated rule at a stated
  version and can be recomputed from the same evidence at any time.
- **What it deliberately does not answer**: what an object is, what it
  does, what it belongs to, or which quantity is whose rating. `630 kVA`
  beside `TR1` yields **two entities that do not know about each other** -
  adjacency is a fact about ink, attribution is a judgement. There is no
  field in the model and no column in the schema in which a relationship,
  a topology or an equipment class could be written, and an architecture
  test asserts both.
- **The catalogue names no equipment class.** No transformer, breaker,
  CT, VT, relay or cable. Deciding that `T1` names a transformer is a
  classification needing a reviewed rule and a governed vocabulary;
  naming those classes now would let the model's shape imply knowledge
  the system does not have.
- **Grouping is by declared key, never similarity.** Designation
  observations group on the normalised designation **plus** the evidence
  status **plus** the extraction rule version: an `AMBIGUOUS` observation
  and an `OBSERVED` one are different claims about how much is known, and
  two observations recognised under different rule versions were
  recognised under different definitions. Grouping is within one
  document - two documents writing `T1` may mean two different
  transformers, and uniting them is cross-document resolution, which this
  milestone does not perform.
- **Quantities are never merged.** Two observations of `630 kVA` may be
  one rating written twice or two identically-rated transformers; the
  document does not say, and merging would arrive downstream as one piece
  of equipment where there were two.
- **Entities never own provenance; they aggregate it.** Each cites the
  evidence keys and locations that created it, while the character-level
  chain stays on the evidence item, which remains authoritative - an
  entity that copied it would become a second source of truth for where a
  thing was seen. Validation refuses an entity citing no evidence: that
  would be an assertion, not a hypothesis.
- **Status is derived, never invented.** Grouping ambiguous observations
  yields an ambiguous entity, so the uncertainty recorded at extraction
  time survives into the hypothesis rather than being laundered away by
  the act of grouping.
- Identity is a SHA-256 over document, evidence source, rule id and
  version, entity contract version and the entity's discriminator - so
  the same evidence always yields the same keys (schema-enforced
  idempotency) and a rule version bump yields different ones (a new set,
  not a silent rewrite). Three versions are recorded because they change
  for different reasons: extraction policy, resolution policy, and the
  entity contract itself.
- Seven typed failures, none collapsed into a generic runtime error.
- What it deliberately does **not** import, enforced by architecture
  test: canonical text, the canonical PDF context, any PDF library, the
  content or storage-location ports, the LLM runtime, Prompt Builder, the
  Engineering Engine, the ontology, the Engineering Index or the
  Knowledge Graph. Its whole dependency surface is the evidence model and
  its own modules.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. New as-built reference:
  `docs/architecture/engineering_entities.md`.
- Dependencies: Milestone 28.1 (its only input).

**Milestone 29.2 — Engineering Fact Construction Foundation** -
*Completed*
- Objective: build deterministic, provenance-rich structured statements
  between resolved entities, so that a later milestone can populate the
  Knowledge Graph from governed facts rather than reconstructing
  relationships from text.
- Delivered: a new `engineering_facts` bounded context (a closed
  predicate vocabulary, fact and diagnostic value objects, a versioned
  construction rule catalogue, a pure constructor, set validation, typed
  failures and `EngineeringFactRepository`); a SQLAlchemy repository over
  four typed tables (additive migration `86c866388a33`);
  `engineering_fact_service.py`; and four endpoints.
- **A fact is a structured association, not a classified property.** The
  predicate vocabulary has exactly one member and
  `HAS_ASSOCIATED_QUANTITY` **does not mean rated power, voltage or
  current**: a data sheet listing a *test* voltage beside a designation
  produces the same predicate as one listing a rated voltage, because the
  line does not say which it is. `HAS_RATED_POWER` and the other property
  and topology predicates are deliberately absent. The quantity's
  evidence type stays reachable through the fact's support so the
  semantic milestone has what it needs - reading it as a predicate here
  would be that promotion happening by accident.
- **One rule: `same_line_association`.** A designation entity and a
  quantity entity associate only when contributing observations of both
  occur on the same document line. **Paragraph association was
  deliberately not implemented**, and the repository evidence is the
  reason: the canonical parser makes each separately-placed run of text
  its own block, so a paragraph is sometimes exactly one line and
  sometimes several unrelated ones. A rule whose strictness depends on
  how the parser happened to block a page is not deterministic.
- **The cardinality policy is declared, not implied.** One designation
  with several quantities on a line produces one fact each (a data-sheet
  line listing ratings is a real shape). Two or more designations produce
  **no fact** and a diagnostic: `TR1 TR2 630 kVA` does not say which
  transformer the rating belongs to, and a guess would put a rating on
  the wrong equipment - invisible in a graph, expensive in a substation.
- **Ambiguity is not a fact and not a failure.** Declined lines are
  recorded as diagnostics in their **own table**, with no subject, object
  or predicate column, so an ambiguous pairing is structurally invisible
  to anyone querying `engineering_facts`. The construction still
  succeeds; the API distinguishes constructed, constructed-with-
  ambiguities, nothing-associable, reused and failed.
- **No proximity of any kind.** No token distance, no nearest-neighbour,
  no geometry, no same-page rule, no punctuation inference, no
  thresholds, no fuzzy matching, no embeddings. An architecture test
  asserts no similarity library is imported and that no distance, score
  or threshold is computed anywhere in the construction path.
- **Facts invent no provenance; they aggregate support.** Every fact
  names its subject entity, object entity, the observations that put them
  on one line (by evidence key and role), the rule and version, and where
  those observations occur. The character-level chain is not duplicated -
  it stays on the evidence and is reachable by key, never reconstructed
  by text search. The matched line is stored because a same-line rule is
  only credible if it can be re-checked.
- **Entities are referenced by key, not by foreign key.** A later
  re-resolution produces a new entity set, and a foreign key would either
  block it or cascade a historical fact set into nothing; a test proves
  fact history survives a newer entity set.
- **A defect this milestone found and fixed.** The first constructor
  counted evidence *observations* rather than distinct entities, so
  `Trasformatore TR1, sigla TR1, 630 kVA` - one transformer named twice -
  would have been reported as an ambiguous two-subject line and declined.
  It now counts distinct subjects, and both observations become support
  for the one fact.
- Ten typed failures, and ambiguous pairing is deliberately **not** among
  them: a line the rules decline is the rules working.
- What it deliberately does **not** import, enforced by architecture
  test: canonical text, the canonical PDF context, any PDF library, the
  content ports, the ontology, the LLM runtime, Prompt Builder, the
  Engineering Engine, the Engineering Index or the Knowledge Graph. Entity
  resolution cannot import facts, and evidence extraction cannot import
  either layer above it.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. New as-built reference:
  `docs/architecture/engineering_facts.md`.
- Dependencies: Milestone 29.1 (the entities it associates) and 28.1 (the
  evidence whose support it checks).

**Milestone 30.1 — Engineering Semantic Interpretation Foundation** -
*Completed*
- Objective: assign explicit, versioned engineering meaning to
  constructed facts, so that a later milestone populates the Knowledge
  Graph from interpreted knowledge rather than deciding what a document
  means for a second time.
- **The three responsibilities, stated once and kept apart: Semantic
  Interpretation assigns engineering meaning. The Knowledge Graph stores
  interpreted knowledge. Reasoning consumes interpreted knowledge.** This
  milestone delivers the first and stops there.
- Delivered: a new `engineering_semantics` bounded context (a closed
  statement vocabulary, the semantic rule catalogue, statement and
  diagnostic value objects, a pure interpreter, set validation, typed
  failures and `EngineeringSemanticRepository`); a SQLAlchemy repository
  over four typed tables (additive migration `7300ff6a7531`);
  `engineering_semantic_service.py`; and four endpoints.
- **One statement type, one rule.** `HAS_RATED_POWER`, produced by
  `rated_power_from_associated_power_quantity` 1.0: a designation
  associated with **exactly one** power quantity has that quantity as its
  rated power. `HAS_NOMINAL_VOLTAGE`, `HAS_NOMINAL_CURRENT`,
  `HAS_CABLE_SECTION`, the topology predicates and every classification
  statement are deliberately absent.
- **Why power and only power.** A voltage beside a designation may be a
  rated voltage, a test voltage, an insulation level or the voltage of
  the busbar the equipment connects to, and the association does not
  distinguish them. A `kVA` figure beside a designation is a rating far
  more reliably - which is still a judgement, and is why it is declared
  in a catalogue with a version rather than assumed. `TR1 20 kV` and
  `TR1 240 mm²` produce **no statement**; `TR1 20 kV 630 kVA` produces
  one, for the power. The catalogue was **not** widened to give every
  association a meaning.
- **No executable engineering rule exists outside the catalogue**, and an
  architecture test asserts nothing else in the context constructs a
  `SemanticRule`. Every stored statement cites a rule id and version; a
  judgement made elsewhere would be one nobody could find, version or
  review.
- **Ambiguity produces no statement.** Two associated power quantities
  yield a diagnostic in its own table - with no object and no
  statement-type column - and nothing else. The reason is structural: a
  fact carries entity **keys**, not values, so this layer cannot see
  whether the figures agree, and reaching for them would mean depending
  on entities. A boundary that forces the conservative answer is a
  boundary in the right place.
- **Status is inherited, never invented.** A statement is `interpreted`
  or `ambiguous` according to the supporting fact - a rated power read
  from `1.250 kVA` is still a rated power statement and still says the
  figure is unsettled. No confidence score, no probabilistic inference: a
  rule applied or it did not.
- **Statements own no provenance and carry no value or unit.** They cite
  supporting facts by key; the chain statement → fact → entity →
  evidence → characters is walkable endpoint by endpoint. The figure
  lives on the quantity entity, where a rated value has exactly one
  source of truth.
- **The evidence type the rule requires is a declared string, not an
  import.** Only Engineering Facts cross the boundary, so the catalogue
  names `power_value` as a literal and a test asserts it equals
  `EvidenceType.POWER_VALUE` - the same discipline as `ClassifiedFormat`
  against `DocumentFormat`.
- Identity binds the **whole upstream source identity**
  `(document_id, content_checksum, resolution_policy_version,
  fact_policy_version, semantic_policy_version)`: a re-resolution or
  re-construction is a different source even when the document has not
  changed, and a rule version bump produces a new set rather than a
  silent rewrite.
- Eight typed failures, and ambiguity within a subject is deliberately
  **not** among them: a subject the rules decline is the rules working.
- What it deliberately does **not** import, enforced by architecture
  test: engineering evidence, engineering entities, canonical text, the
  canonical PDF context, any PDF library, document identity, the content
  or storage ports, the ontology, the LLM runtime, Prompt Builder, the
  Engineering Engine, the Engineering Index or the Knowledge Graph — nor
  any numerical, statistical or similarity library. Only Engineering
  Facts cross the boundary.
- Architecture impact: **no new ADR.** No new persistence strategy and no
  new external dependency. New as-built reference:
  `docs/architecture/engineering_semantics.md`.
- Known debt: interpretation is **unmeasured**. Milestone 28.2's
  evaluation framework measures extraction only; entity, fact and now
  semantic quality are all asserted by unit test rather than measured
  against annotated documents. This is the third layer built on unmeasured
  rules, and the one where being wrong is most expensive — a wrong rated
  power is an engineering claim, not a parsing slip.
- Dependencies: Milestone 29.2 (its only input).

**EPIC 30.1.2 — Frontend–Backend Integration** - *Completed*
- Objective: make the frontend a faithful client of the backend. Not a UI
  redesign — an alignment, with the backend as the sole authority on the
  API contract. **No backend behaviour was changed to accommodate the
  frontend**; the backend suite stayed at 2777 passing throughout.
- **The frontend did not compile.** `npx tsc --noEmit` reported 22 errors
  before this EPIC: two type modules were referenced by names that did not
  exist on disk (`@/types/knowledge-graph` against `types/knowledge_graph.ts`,
  `@/types/project-intelligence` against a file literally named
  `project-intelligence-ts`), and `DocumentTable` read a `project` field no
  API returns. The repository also carried an `aoo/` directory (a typo of
  `app/`) and a file named `touch .env.local`.
- **Project creation could not succeed.** The form offered statuses
  `active`, `on_hold`, `completed` and `cancelled` — none of which the
  backend's `ProjectStatus` has ever contained — and treated `customer`
  as optional where the schema requires it (`min_length=2`). Any
  submission produced a 422 rendered as "Errore durante la creazione del
  progetto". Both are now transcribed from the backend and asserted by
  test.
- **One API client.** `lib/api/client.ts` is the only module that calls
  `fetch` — base URL, JSON and multipart, query building, 30 s/120 s
  timeouts, composed cancellation, and a retry policy that replays GETs on
  transport faults and **never** replays a POST. It replaced a 25-line
  `apiRequest` that threw `new Error("API request failed: 422")` for every
  failure.
- **A typed error model.** `ValidationError` / `NotFoundError` /
  `ConflictError` / `RequestError` / `ServerError` / `NetworkError` /
  `TimeoutError` / `RequestCancelledError`. FastAPI's two 422 shapes both
  survive: Pydantic's per-field array is bound onto form inputs, a domain
  rule's plain string is shown as the sentence it is. The rule is **never
  invent a cause** — the backend's own words are what the user reads. The
  string "an error occurred" appears nowhere.
- **One transcription of the contract.** `lib/contracts` declares every
  enum, request and response, each file naming its backend source module.
  `tests/contracts.test.ts` compares all of them against the backend's own
  OpenAPI document, exported by the new `scripts/export_openapi.py` to a
  committed `apps/backend/openapi.json` snapshot. That test is what found
  the `ProjectStatus` drift, and the missing `busbar`/`line` graph entity
  types.
- **Two state primitives replaced five hand-rolled hooks.**
  `useResource` and `useMutation` own loading vs refreshing, typed
  failures, cancellation on unmount and on input change, and cache
  correction from the server's own copy of a created resource. The
  previous `useHealth` fabricated an "everything offline" payload when the
  health check failed — inventing a backend answer to a request the
  backend never answered.
- **The Pipeline UI is the new centrepiece.**
  `/documents/{id}/pipeline` renders all seven stages with status, count,
  reuse state, ambiguities, errors, the version triad each ran under, and
  an inspector for every artefact down to the page, paragraph and line.
  It preserves four properties a careless UI would destroy: an unrun
  stage is *ready* not failed; an empty result is *completed* not an
  error; a re-used artefact says so; and a declined ambiguity is shown
  with its reason, because a stage that constructed nothing has the most
  to explain.
- **Timestamps are reported as absent where they are absent.** Pipeline
  artefacts carry none by design — that is what makes two runs compare
  equal — so the UI says "Non esposto (artefatto deterministico)" rather
  than showing a plausible date the API never sent.
- **Quantities stay strings.** `Decimal` is serialised as a JSON string so
  a rated voltage cannot pick up a rounding error; the UI never parses one
  into a JS number, asserted by a test that `20.500 kV` survives intact.
- **Every mock deleted:** `lib/demo-commissioning.ts` (905 lines),
  `lib/demo-timeline.ts`, the commissioning/timeline/focus components, the
  dashboard's hardcoded `0` counters and `+12% questo mese` trend, and the
  sidebar links to `/commissioning`, `/relay-testing`, `/ai`, `/reports`
  and `/settings` — five routes that do not exist. The backend's own
  constant-zero `commissioning`, `relay_testing` and `issues` figures are
  typed but deliberately **not rendered**: a fabricated 0% beside a real
  documentation figure reads as a measurement.
- 91 frontend tests (vitest + Testing Library, no network), covering
  create/edit/list, upload, every pipeline page, 422/404/409/500, network
  failure, timeout and cancellation. `typecheck`, `lint`, `test` and
  `build` are all green.
- Architecture impact: **no new ADR** — no new persistence strategy and no
  new backend dependency. New as-built references:
  `docs/architecture/frontend_architecture.md` (replacing the empty,
  misspelled `frontend_arcgitecture.md`) and `docs/developer_setup.md`.
- Known debt: `GET /documents/` still declares no `response_model` and
  leaks `file_path`; there is no `GET /documents/{id}` and no download
  endpoint; and neither list endpoint supports pagination, search or sort,
  so filtering is client-side over the whole list. All four are backend
  gaps, recorded rather than worked around.
- Dependencies: Milestone 30.1 (the last pipeline stage the UI exposes).

**Milestone 30.1.3 — Public API Hardening** - *Completed*
- Objective: make the Project and Document APIs explicit, typed, secure,
  scalable and fully represented in OpenAPI, before the Knowledge Graph
  adds more endpoints. Driven by the weaknesses EPIC 30.1.2's frontend
  audit exposed.
- **A Document bounded context exists for the first time.** Until this
  milestone documents lived only as ORM rows, which routers serialised
  straight onto the wire - which is *why* `file_path` was a public API
  field and *why* every list read the whole table.
  `app/domain/document_registry` now owns the registry read model:
  what documents exist, what an engineer may know about one, and the
  governed queries by which a caller reaches them.
- **Storage location is private backend state, structurally.** No value
  object in the context has a field for it, so no schema built from one
  can leak it. `DocumentDownload` is the single exception - the transport
  must hand the reference back to the content port - and an architecture
  test asserts it is the only carrier. A second test walks **every**
  schema in the OpenAPI document for a property named after a path, and
  it found a real leak: `DocumentContentIdentityRead.storage_reference`,
  on the ingestion API. Removed.
- **The download cannot traverse because it cannot express a path.** The
  chain is `id → registry → opaque reference → content port`; the only
  input is an integer and the reference is whatever the registry
  recorded. Streamed in 64 KiB chunks, every failure resolved before the
  first byte is written, `Content-Disposition: attachment` with an
  allow-listed filename, and a closed media-type table that serves an
  unclassified document as `application/octet-stream` rather than
  guessing. Route named `/content` rather than `/download`: every other
  per-document route in this API is a noun naming the artefact it serves.
- **The upload's own path-traversal hole is closed.** `save_file` joined
  the uploaded filename to the storage directory directly, so
  `../../app/main.py` was written wherever it resolved and two uploads of
  the same name silently overwrote each other. The stored name is now
  sanitised and made unique, and the computed path is resolved and checked
  to be inside the storage root before anything is written. The
  **original** filename is still what an engineer sees.
- **One pagination contract**, page-based, in the Shared Kernel -
  `app/domain/shared_kernel/pagination.py`, the first member of a
  deliberately hard-to-join kernel. Default 25, **maximum 100**, and a
  larger request is **refused with 422, never clamped**: a caller who
  asked for 10 000 and silently received 100 would believe it had read
  the whole registry. `total` is counted by the database over the filtered
  set, never by measuring a list loaded first.
- **Filtering, search and sorting are closed vocabularies.** Every filter
  is an enum member or a typed value object; no column name ever travels
  from a caller into a query, and the `_SORT_COLUMNS` tables are keyed by
  enum member with no `getattr` anywhere. Search behaviour is defined once
  and documented: case-insensitive, partial, trimmed, internal whitespace
  significant, `%` and `_` escaped. Every sort breaks ties by `id`, without
  which paging over a non-unique key shows one row twice and skips
  another.
- **`ProjectStatus` and `voltage_level` joined the domain aggregate.**
  They were persisted from the beginning but had no domain home, so the
  projects router re-read the ORM row to build every response - the one
  place a router still touched persistence directly. `ProjectStatus` now
  lives in `app/domain/project/project_status.py`, the public schema
  imports it from there rather than from `app.models`, and the router
  imports no ORM module at all. Delivery status and lifecycle state stay
  rigorously distinct: a project can be `energized` **and** `archived`,
  and both filters accept that.
- **Two smells this milestone's own architecture tests caught in its own
  code**: a sequence slice in the documents router (a fragile filename
  comparison, rewritten to ask the sanitiser) and a `getattr` on the
  stored project status (removed by storing the ORM enum). Both were
  found by tests written in the same milestone, before review.
- Backend: **2941 tests** (164 new), including path traversal, header
  injection, missing-versus-unreadable content, page-size enforcement,
  wildcard and SQL injection through search, and unsupported sort fields.
  Frontend: **119 tests** (28 new) covering paged envelopes, filters
  reaching the server, the absence of local filtering, document detail and
  the download.
- Frontend compatibility: `PagedResponse<T>` contracts, `useDocument`,
  server-side query state with page-1 reset on filter change, a debounced
  search, one `Pagination` control reporting the total, and a download
  action. **Client-side filtering of the whole registry is gone** - it
  would now filter one page.
- Architecture impact: **no new ADR** and **no migration** - the existing
  schema supports every query. New as-built reference:
  `docs/architecture/public_api.md`.
- Known debt: upload still answers **200** rather than 201 (a breaking
  change this milestone was not asked to make); other routers still hold
  sessions and build queries, and the architecture tests scope themselves
  to `documents.py` and `projects.py` rather than claiming otherwise; and
  search is `ILIKE '%term%'`, which no index can serve - deliberately not
  addressed, because adding one now would be guessing at a workload
  nobody has measured.
- Dependencies: EPIC 30.1.2 (whose audit produced the list).

**EPIC 32.1 — Deterministic Engineering Consistency Reasoning Foundation** - *Completed*
- Objective: introduce the first Engineering Reasoning capability -
  explicit, versioned, deterministic engineering conclusions derived
  exclusively from governed knowledge - and establish the architecture
  that keeps a conclusion from ever becoming a fact.
- **The headline: SubstationOS now concludes something.** Everything
  before this milestone *records*: what a document says, what was
  measured, what it means, what a human approved. This is the first
  capability that produces a statement which is in no document and was
  approved by no reviewer. The first thing it concludes is the thing a
  substation engineer most needs noticed: **two approved documents
  disagree**.
- **`Governed Knowledge != Reasoning Conclusion`, enforced as a type
  boundary rather than a flag.** A conclusion is `ReasoningResult` in its
  own bounded context, and reaches a response as `derived_reasoning` -
  deliberately **not** among `references`, because to every downstream
  consumer an evidence reference reads as one more governed fact
  supporting the answer. A conclusion is a statement *about* those facts.
  `DerivedReasoningAssessment.is_governed_knowledge` returns `False`
  permanently, so a caller tempted to treat one as the other has to read
  the word while doing it.
- **Four outcomes, never a boolean and never a score**: `CONSISTENT`,
  `INCONSISTENT`, `INSUFFICIENT_KNOWLEDGE`, `AMBIGUOUS`. An absence of
  contradiction is not agreement, and "the graph does not record a rated
  power for this transformer" is not "this transformer is consistent".
  Collapsing the last three into "not consistent" is how a real
  installation gets signed off on a gap nobody looked for.
- **Nothing is promoted, enforced by absence.** The whole reasoning
  surface imports no repository, no session, no promotion service, no
  Human Review module and no graph port; the engine step handler declares
  no `__init__`, so it is constructed with nothing at all. An end-to-end
  test asserts the governed graph is byte-identical across an execution
  that concluded `INCONSISTENT` - the case a future "just record the
  conclusion" change would target first. `knowledge_promotion_service`
  remains the single graph-authoring authority.
- **Deterministic as a decision, not an inheritance.** No LLM, no
  embedding, no probability, confidence, score, likelihood, ranking or
  threshold, no randomness, no clock. `Decimal`, never `float`. A
  structural fitness function asserts no *identifier* in the reasoning
  surface is named for a score - checked on the AST, because the
  docstrings say the word repeatedly, always to forbid it.
- **Units are never converted.** The governed graph carries a declared
  value and a declared unit but no base value - those exist only at the
  evidence layer. Two governed quantities in different units therefore
  yield `unsupported_comparison` → `INSUFFICIENT_KNOWLEDGE`. Converting
  would put a unit table in the reasoning layer, applied to values whose
  provenance says nothing about how they were normalised.
- **No new intent.** `VERIFICATION_REQUEST` already owns the consistency
  vocabulary the deterministic classifier matches on (`incoerenza`,
  `coerente`, `inconsistency`); a `CONSISTENCY_CHECK` intent would have
  made that classifier ambiguous, and an ambiguous deterministic
  classifier is worse than no new intent. Reasoning is a **workflow
  capability** instead: `ENGINEERING_VERIFICATION` (now version `2.0`) is
  the only workflow that declares it, so every other workflow comes back
  with `derived_reasoning` of `None`.
- **No new public API, no migration, no new table, no configuration, no
  external dependency.** A conclusion is reachable where it is
  meaningful - on the engineering response. A standalone `POST
  /reasoning` would accept a caller-supplied context package, which is a
  caller-supplied claim about what governed knowledge says: the same
  class of problem AF-PROV-002 forbids for provenance.
- **AF-01 held.** No invariant was weakened, bypassed, renamed away or
  reinterpreted. AF-REASON-001/002/003 stopped being forward
  requirements and became executing fitness functions; AF-DEP-001 gained
  six frozen directions involving `engineering_reasoning`; AF-DET-002's
  deterministic core gained it as an eleventh context. All additions.
- Scope is deliberately one rule - `governed_quantity_consistency` v1.0
  over `HAS_RATED_POWER`, the only relationship kind governed semantics
  currently produces. Not a rule engine, DSL or plug-in registry. The
  deliverable is the boundary; a second rule now costs a file.
- Recorded in
  [ADR-0029](../architecture/adr/0029-deterministic-engineering-reasoning-foundation.md)
  and [engineering_reasoning.md](../architecture/engineering_reasoning.md).
- Dependencies: EPIC 31.3 (governed context), Architecture Freeze AF-01.

**EPIC 31.4 — Legacy Retrieval Surface & Canonical Facts Retirement** - *Completed*
- Objective: leave **one** runtime engineering knowledge graph. A pure
  retirement milestone - no new product capability, and none was added.
- **The headline: `graph_contexts == ["governed_knowledge_graph"]`.** The
  Canonical Facts graph-shaped projection, the retrieval over it and the
  twenty routes that served it are gone. Queryable engineering graph
  knowledge is now, by construction, the Governed Knowledge Graph.
- **The route inventory was 20, not 15.** The audit re-enumerated the
  live route table rather than trusting EPIC 31.2's count, and found one
  router serving eight routes of which only two carried a
  `/graph-executions` path. Six of the others sat under
  `/projects/{id}/knowledge-graph/*` - **one path prefix away from the
  governed graph's own `/knowledge-graph/*`**. Nothing had confused them
  (the frontend only ever called the governed routes), but the
  arrangement was one careless integration away from doing so.
- Withdrawn routes return **404**, following ADR-0025's precedent: no
  `410` shim, because it preserves a URL whose only honest answer is that
  the data behind it should never have been served. The routers are
  deleted, not deregistered.
- **`RetrievalMode` was moved, not aliased.** `retrieval_bridge` is live
  and authoritative - it prepares requests for the *governed* engine -
  and imported one enum plus four bounds from the retiring package. The
  enum is now defined outright in
  `app/domain/retrieval_bridge/retrieval_mode.py` and the bounds are
  stated locally, which the bridge's own docstring had always claimed
  without it being true. All eight live imports point at the bridge,
  proven by inspection.
- **`canonical_facts`, `proposed_claims` and `review_workflow` survive**,
  with their routes and their data. They hold human-authored claims and
  the legacy review history over them - the *input* the retired
  projection was computed from, not a graph. The invariant is about
  graph-shaped queryable knowledge projections, not about every
  relational table that relates two things.
- Migration `f4a90c27b615` drops seven tables, dependants first. Fresh
  install reaches HEAD with 45 tables and none of the seven; a
  representative pre-retirement database upgrades with governed graph,
  semantic statements, reviews, documents, audit history and the retained
  claim/review tables all intact. **Downgrade restores the schema shape,
  empty** - verified, and stated in the migration, in ADR-0028 and in
  `operational_reliability.md` rather than discovered mid-rollback.
- **No legacy row was converted into governed knowledge and no review was
  fabricated.** Every dropped row was derived; the unique input survives.
  Loading the projection into the governed graph would have required
  attributing approvals to engineers who never gave them.
- **ADR-0004 now has nothing behind it.** A claim approved in the legacy
  workflow reaches no queryable graph at all - not "a different graph
  disagrees", but "there is nowhere else to ask". EPIC 31.2's shadow
  comparison test was rewritten to assert that stronger fact rather than
  deleted.
- Capability removals with no successor, recorded honestly: property-bag
  attribute search, broad lexical search, orphan detection, and building
  or executing a graph from approved claims.
- New architecture tests prove the invariant structurally: one runtime
  graph context, no retired package in any of six layers, no runtime
  import of the lineage, no retired route, no retired ORM table, and -
  the one that could only be written now - **no pipeline or review module
  writes any graph**, where before only the governed half could be
  asserted.
- Recorded in
  [ADR-0028](../architecture/adr/0028-retire-the-canonical-facts-graph.md).
  ADR-0007 and ADR-0010 are marked superseded; ADR-0025, ADR-0026 and
  ADR-0027 keep their decisions and gain a note that their deferred
  condition is now discharged.
- A pre-existing defect surfaced during the search sweep and was fixed in
  passing: the LLM invocation smoke-test script built its prompt with
  `project_id = 0`, which Context Assembly has always rejected - it could
  never have reached a provider.
- Known limits: existing installations lose the projection rows on
  upgrade (documented, with an export); `scripts/benchmarks` still
  imports one governed fixture from `tests/**`, contrary to its own
  docstring - pre-existing, unrelated to the lineage, and recorded as
  debt rather than fixed here.
- Dependencies: EPIC 31.3 (which met the second retirement condition).

**EPIC 31.3 — Governed Context Assembly** - *Completed*
- Objective: remove the last compatibility boundary between governed
  knowledge and the answer an engineer reads. EPIC 31.2 moved retrieval
  onto the governed graph but deliberately kept one adapter
  (`governed_context_projection.py`) so that retrieval and its four
  downstream consumers were not migrated in the same change. That
  isolation had served its purpose.
- **The headline: the Engineering Engine speaks one vocabulary end to
  end.** Context Builder consumes `GovernedRetrievalResult` directly, the
  adapter is **deleted**, and with it went the last score-shaped ordering
  value and the last `graph_builder` type in the governed path. Two
  architecture tests hold the line: the adapter file must not exist, and
  no module anywhere may project governed results into the candidate
  vocabulary.
- A `ContextItem` **wraps** a `GovernedRetrievalItem` rather than copying
  its fields. That is what makes the three guarantees structural rather
  than conventional: provenance has no default and no `| None` so it
  cannot be dropped; the per-query outcome travels with every item so
  ambiguity cannot be lost; and there is exactly one representation of a
  governed answer in the system, so no two copies can disagree.
- **Ambiguity now survives all five stages**: the item's origin, the
  query summary, an `AMBIGUOUS_RETRIEVAL` context warning, an
  `AMBIGUOUS:` block in the prompt, and an `AMBIGUOUS_KNOWLEDGE` warning
  plus a `HIGH` uncertainty on the `EngineeringResponse`. An ordered list
  reads as a ranked one and the first line of a ranked list reads as the
  answer, so a chain that preserved ambiguity four times and dropped it
  once would have preserved nothing.
- **`MISSING_PROVENANCE` was removed from the warning vocabulary**, and
  its absence is the point: a governed item cannot be constructed without
  provenance, so the warning described a state the platform can no longer
  reach — and a warning that can never fire reads as reassurance.
- Prompt Builder and Engineering Response migrated with it. A knowledge
  line now ends in the governed match strategy and the statement key that
  authorises it, where it used to end in `(score 100.0)`; citations carry
  `item_id`, `node_ids`, `edge_ids`, `statement_key`, `review_id` and
  `document_id` — identities only, never statement or evidence text. The
  system-context section states plainly that *approved* means an engineer
  accepted that statement, not that the knowledge is complete or that a
  question has one answer.
- **One route withdrawn, and it is the milestone's only compatibility
  break**: `POST /projects/{id}/context-builder/build`. Its only possible
  input was a legacy `KnowledgeCandidateCollection`, and after this
  milestone a `ContextPackage` asserts a statement key, a review id and a
  named reviewer — so accepting one in a request body would let any
  authenticated caller mint a context that *looks* reviewed, the exact
  ADR-0004 failure three milestones were spent removing. Provenance a
  caller asserts is not provenance. `/prompt-builder/build` and
  `/engineering-response/build` keep their `context_package` bodies: they
  persist nothing and write no graph, so a fabricated body harms only the
  caller's own answer.
- Recorded in
  [ADR-0027](../architecture/adr/0027-governed-context-assembly.md), with
  [governed_context_assembly.md](../architecture/governed_context_assembly.md)
  as the as-built reference.
- **Canonical Facts retirement readiness:** ADR-0026 recorded two
  conditions. The second — "`structured_retrieval`'s value objects
  reference `graph_builder`, so the Context Builder migration is required
  first" — is now **met**: no module the Engineering Engine reaches
  imports either. The first is unchanged: four legacy route groups
  (`/graph-builder`, `/graph-executions`, `/projects/{id}/graph`,
  `/projects/{id}/structured-retrieval`) still serve the lineage.
  **The technical work is done; the remaining blocker is entirely a
  product decision** about whether the platform continues to offer them.
  The forward migration dropping the seven legacy tables is still not
  written, because a migration for tables a live route serves is a trap
  for whoever runs it.
- Known limits: the wire shape of `ContextPackageRead` changed
  (`selected_items` replaces `selected_candidates`, governed identities
  and provenance replace a score and a `GraphEntityId`); no frontend code
  consumed it. `context_builder_version` is renamed
  `context_assembly_version` through the prompt, the LLM request metadata
  and the response — the field always meant "which context assembly
  produced this", and now says so.
- Dependencies: EPIC 31.2 (the governed retrieval this assembles).

**EPIC 31.2 — Governed Structured Retrieval** - *Completed*
- Objective: make the Engineering Engine answer **only** from knowledge a
  named engineer approved. Until this milestone its retrieval read the
  Canonical Facts projection - a substrate fed from Proposed Claims
  approved in the *legacy* review workflow - while the Governed Knowledge
  Graph answered only the Workspace and its own API.
- **The headline: engineering retrieval now consumes governed knowledge
  exclusively.** A new bounded context, `governed_retrieval`, reads the
  governed graph through `GovernedKnowledgeReader` - a port with **no
  write method**, so "retrieval never writes" is a type rather than a
  rule. The engine's two composition roots name that reader and no graph
  repository at all, and an architecture test asserts it.
- **Nothing about the engine's shape changed.** The workflow definitions,
  the step types, the artifact keys, the planner and the executor were
  untouched: a step still builds a retrieval plan and a step still
  executes it. Only the substrate moved.
- Five typed queries with explicit fields and explicit semantics; no free
  text, no filter object, no expression, no query language. The
  provenance query *is* the identity query, because every result already
  carries its full provenance.
- **No property bag was carried forward, in either direction** - the
  governed graph did not acquire one to ease the migration (which would
  have undone
  [ADR-0024](../architecture/adr/0024-governed-knowledge-graph-as-projection.md)),
  and neither did the retrieval path. An architecture test fails on
  `properties`, `attributes` or `payload` anywhere in it.
- **Ranking is by match strategy, not by score.** The legacy
  implementation summed documented weights; the weights were
  deterministic and were still a number attached to engineering
  knowledge. Every governed result carries exactly one strategy - the
  strongest that held - the governed field that carried it, and the value
  compared, so "why did this match?" has one answer.
- **Ambiguity is preserved rather than resolved.** `TR1` in two drawings
  is two governed nodes and two answers; the outcome is computed before
  any limit, so a truncated page cannot present several governed answers
  as one certain one. Cross-document entity resolution stays upstream,
  outside this bounded responsibility.
- **Quality was measured before the substrate moved**, which the EPIC
  required: nine baseline scenarios and a shadow comparison against
  legacy retrieval, run through the real API against real documents,
  real reviews and real promotions. Every difference is classified and
  each class is named by a test - one expected governance difference,
  one strict provenance improvement, two deliberate capability removals
  (attribute-bag search, and lexical matching over entity types and
  attribute values) - and **zero unexplained differences**, recorded by a
  test rather than claimed.
- Governance proven end to end through real review paths: `APPROVED +
  APPLIES` retrievable; `REJECTED`, `NEEDS_INVESTIGATION`,
  `REQUIRES_REVALIDATION` and `ORPHANED` not; `HISTORICAL` excluded from
  the default scope; `REMOVED` excluded from every scope.
- One endpoint added - `GET /projects/{id}/governed-retrieval/assets` -
  serving the one requirement product has: reading what the engine
  retrieved and why. Same capability as the graph API it reads,
  authorised the same way.
- **One temporary adapter**, named and dated:
  `governed_context_projection.py` maps a governed outcome into the
  `KnowledgeCandidate` vocabulary Context Builder speaks. Migrating
  retrieval **and** its four downstream consumers at once would have made
  a quality regression in any of them invisible, which is the one thing
  this milestone was required not to do. Retirement condition stated in
  the module and asserted by an architecture test: delete it when Context
  Builder consumes `GovernedRetrievalResult` directly.
- **The Canonical Facts projection was NOT retired, and the blocker is
  stated rather than glossed.** Seven of the ten retirement-gate
  conditions pass; three fail for one reason - four route groups
  (`/graph-builder`, `/graph-executions`, `/projects/{id}/graph`,
  `/projects/{id}/structured-retrieval`) still serve it. Withdrawing
  served capabilities is a product decision, not something an engine
  change implies, and "remove only what is proven unused" still holds:
  these are proven used, by their own API. The objective condition that
  permits retirement is recorded in
  [ADR-0026](../architecture/adr/0026-governed-structured-retrieval.md)
  section 9, and `test_graph_consolidation.py` now asserts the new truth
  in both directions - the engine no longer reads the lineage, and the
  lineage is still reachable through its own routes.
- The full end-to-end integration test now runs the governed lineage:
  document to pipeline to semantic statement to approval to promotion to
  governed retrieval to engine answer, and asserts the answer references
  the governed node by its governed identity.
- Recorded in
  [ADR-0026](../architecture/adr/0026-governed-structured-retrieval.md);
  as-built reference in
  [governed_structured_retrieval.md](../architecture/governed_structured_retrieval.md).
- Known limits: two deliberate capability removals (above); one temporary
  adapter; designation folding is a Python-side scan of the scoped node
  set (measured, no index added ahead of a need); project visibility
  remains filtering rather than enforcement, inherited unchanged from
  EPIC 30.3.
- Dependencies: EPIC 31 (the governed graph), EPIC 31.1 (the first
  retirement).

**EPIC 31.1 — Legacy Graph Retirement** - *Completed*
- Objective: leave exactly one authoritative engineering knowledge model
  in the repository. A consolidation milestone, with almost no new
  user-visible functionality by design.
- **The headline: the ADR-0004 violation is over.** From Architecture
  Freeze v1.0 until this milestone, `knowledge_graph.ingest_document` ran
  on every document upload and wrote LLM-extracted entities straight into
  the queryable graph - no reviewer, no review date, no provenance beyond
  a filename, a bare `confidence` float as the only trust signal.
  [ADR-0004](../architecture/adr/0004-reviewed-facts-only-in-queryable-graph.md)
  recorded that it must not happen and that it was happening;
  [ADR-0009](../architecture/adr/0009-legacy-knowledge-graph-isolation.md)
  quarantined it. Both are now discharged, and their status lines say so.
- Retired, all proven unused first: `services/knowledge_graph.py`,
  `routers/knowledge_graph.py`, `schemas/knowledge_graph.py`,
  `models/knowledge_graph.py`, `services/entity_extractor.py`,
  `services/topology/**` and `services/ai/**` - the last being an entire
  second LLM client that predated the governed provider abstraction.
  Migration `e28b91f4c073` drops `project_entities` and
  `entity_relations`.
- **Ingestion now writes no graph at all.** The pipeline's downstream
  consumer is `None`; an upload stores, identifies and canonicalises a
  document and does nothing else. Knowledge reaches the graph only
  through an explicit, capability-gated promotion of a statement an
  engineer approved, and an architecture test asserts the consumer.
- Recorded in
  [ADR-0025](../architecture/adr/0025-retire-the-legacy-knowledge-graph.md),
  which also explains the two decisions that were **not** obvious:
  - **Deletion, not deprecation.** The routes had been marked deprecated
    for four milestones and it had changed nothing. A `410 Gone` shim was
    rejected: it preserves a URL whose only honest answer is that the
    data should never have been served.
  - **The rows are dropped, not migrated.** Every governed edge requires
    an approving review and there is none; manufacturing approvals for
    unreviewed AI output would be the exact fraud the platform exists to
    prevent. The migration carries the export SQL for an operator who
    wants the rows, and `downgrade()` restores the schema **empty**,
    stated rather than discovered.
- **One graph implementation deliberately remains**, and the milestone
  says so rather than claiming a clean sweep: the Canonical Facts lineage
  (`graph_builder`, `project_knowledge_graph`, `graph_query`) is read at
  runtime by Structured Retrieval and therefore by the whole Engineering
  Engine stack. "Only remove code proven unused" was the instruction, and
  this is proven *used* - an architecture test now asserts that it still
  is, so the day nothing reads it is the day the repository notices.
  Retiring it means rewriting Structured Retrieval's matching against
  typed fields instead of property bags, which is a milestone with a
  measurable quality impact rather than a cleanup.
- Frontend: `/projects/{id}/knowledge-graph` **survives and is
  rewritten** against the governed graph - engineers have it bookmarked,
  so the address stays and what it shows does not. It now lists governed
  concepts and their relationships, each carrying the provenance that
  authorised it and a link back to the statement in the Workspace. The
  legacy contracts, components and hook are deleted, and a test asserts
  the page never calls the retired endpoint.
- Existing tests repointed rather than deleted: six "this stage writes no
  graph" assertions queried the dropped tables and now query the governed
  ones, which is a strictly stronger property. Two OpenAPI tests that
  asserted the legacy router was *marked deprecated* now assert it does
  not exist.
- A welcome side effect: with the legacy `EntityType` gone, the OpenAPI
  name collision disappeared and the frontend contract stops carrying the
  fully-qualified workaround name.
- Known limits: existing installations lose the legacy rows on upgrade
  (documented, with an export); `analysis.entities_found` on upload is
  now always `0`, kept rather than removed to avoid a breaking response
  change.
- Dependencies: EPIC 31 (the governed replacement that made retirement
  possible).

**EPIC 31 — Governed Knowledge Graph** - *Completed*
- Objective: make approved engineering knowledge queryable. The platform
  could interpret documents and record judgement about the
  interpretations; nothing could answer "what is TR1's rated power, and
  why do we believe it?".
- **The core principle: the graph is a projection, never a source of
  truth.** Pipeline artefacts stay immutable, reviews stay immutable, and
  the graph is derived from both - droppable and rebuildable at any time.
  Three tests assert rebuildability, and `clear()` exists on this
  repository and on no other in the system.
- Delivered: a `governed_knowledge_graph` bounded context (vocabulary,
  identity, provenance, lifecycle, promotion rules, generations, events,
  a port), three tables, a promotion service with incremental and full
  modes, a resource-oriented query API, and a graph panel in the
  Engineering Workspace.
- **This is the first implementation that satisfies
  [ADR-0004](../architecture/adr/0004-reviewed-facts-only-in-queryable-graph.md)**,
  which has recorded since Architecture Freeze v1.0 that only reviewed
  facts may enter a queryable graph and that the legacy path did not
  comply. The graph consumes exactly one thing: a semantic statement
  whose current review is `APPROVED` and whose applicability is
  `APPLIES`. Rejected, inconclusive, awaiting-revalidation and orphaned
  are each refused, each with a named reason, each tested separately.
- Four decisions recorded in
  [ADR-0024](../architecture/adr/0024-governed-knowledge-graph-as-projection.md):
  - **The projection is a pure function of the statements and the
    reviews.** Identities are hashes of governed keys, and `created_at`
    comes from the authorising review rather than from the clock - so
    nothing stored depends on when promotion ran, and a rebuild
    reproduces byte-identical content rather than merely re-populating.
  - **Incremental promotion and full rebuild call the same rule
    function.** Neither re-implements it, so they cannot disagree about
    what is promotable - the usual failure mode of an incremental
    projection.
  - **Provenance is mandatory and structural.** Construction raises
    without it and the columns are `nullable=False`. There is no
    confidence, score or weight anywhere: a number expressing how much to
    trust governed knowledge would reintroduce exactly what ADR-0004
    rejected.
  - **Identity derives from governed keys, never from labels.** Both ids
    are `UNIQUE`, so duplicate prevention is a constraint rather than a
    convention.
- Lifecycle: knowledge whose authorisation stops holding becomes
  `HISTORICAL` **with a recorded reason** - not removed, not disabled,
  not superseded. Re-approval reactivates the same edge, so its identity
  survives the round trip. Reconciliation runs in both directions, so a
  statement a re-run dropped cannot leave knowledge sitting current and
  unvisited.
- **The vocabulary is two node kinds and one edge kind**, and that is a
  finding rather than a shortcut: governed semantics produces two entity
  types and one statement type. Voltage, Protection, Connection, Function
  and Location are deliberately absent - for voltage specifically, the
  semantics context *refuses* to interpret it, since an associated
  voltage may be rated, test, insulation or busbar voltage.
  `knowledge_graph.md` §3 lists what each further concept needs upstream
  first.
- No graph query language. No Cypher, GraphQL or SPARQL: a governed graph
  whose value is that every answer is explainable should not first ship a
  way to ask questions nobody planned. A test asserts no such path exists.
- Security: a new `promote_engineering_knowledge` capability, separate
  from `record_engineering_review` - passing a judgement and publishing
  its consequence are different acts. Two audit actions; a promotion that
  reconciled nothing is deliberately not audited.
- **Known limit, stated prominently: three graph implementations now
  coexist.** The legacy path (ADR-0009) and the Canonical Facts lineage
  (Milestones 11.1/11.2) were not touched, because extending the latter
  would have meant admitting a second ungoverned source into governed
  tables. `knowledge_graph.md` §2 states the relationship and recommends
  the retirement path; it is one milestone per graph and belongs in
  neither this one.
- Other limits: no cross-document entity resolution (`TR1` in two
  drawings is two nodes, deliberately); project visibility is filtering
  rather than enforcement, inherited from EPIC 30.3; a rebuild is
  synchronous and unbounded.
- Dependencies: Milestone 30.1 (the statements), EPIC 30.3 (the identity
  that authorises promotion) and EPIC 30.4 (the judgements it promotes
  on).

**EPIC 30.4 — Human Review** - *Completed*
- Objective: let authenticated engineers record governed decisions about
  what the deterministic pipeline produced, without any of it becoming an
  input to the pipeline. The platform could interpret a document; nobody
  could record that they had checked the interpretation.
- **The core principle, and the whole shape of the milestone: engineering
  truth and engineering judgement stay separate, forever.** Pipeline
  output is deterministic and immutable; reviews are attributable and
  append-only; a review references an artefact by key and never contains
  one. An API test asserts the semantic set compares equal before and
  after a review is recorded, and an architecture test fails if any
  engineering domain module imports the review context.
- Delivered: a `human_review` bounded context (target, decisions,
  reasons, review, snapshot, policy, applicability, projection, events,
  an append-only port), one append-only table, a resource-oriented API,
  and a review panel in the Engineering Workspace with decision badges, a
  history timeline, reviewer identity and permission states.
- Two decisions recorded in
  [ADR-0023](../architecture/adr/0023-human-review-append-only-judgement.md):
  - **The current decision is never stored.** It is the newest review for
    a target, computed on read. There is no `status`, `is_current`,
    `superseded_at` or `current_decision` column - architecture tests
    assert their absence in both the ORM model and the migration - because
    a stored current decision is a second account of a fact the ordered
    history already states, and the day the two disagreed nobody could
    say which was true. `superseded` is derived from position.
  - **Revalidation is decided by artefact identity, not by comparison.**
    `statement_key` is already a SHA-256 over the document, the fact
    source, the triple and the rule versions, so an identical re-run
    reproduces the same key and *any* change produces a different one.
    "Does this review still apply?" is therefore a lookup, not a
    heuristic - and correct by construction, because the pipeline already
    computes the identity it depends on.
- Three applicability states, every transition tested against real
  pipeline runs: `applies` (the key is present), `requires_revalidation`
  (a current interpretation exists and the key is absent - the pipeline
  moved on), `orphaned` (there is no interpretation to compare against).
  **A review is never discarded in any of them**, and there is
  deliberately no state meaning "migrated to the new statement": carrying
  a judgement onto a differently-derived artefact would attribute to a
  named engineer an opinion about something they never saw.
- Three decisions (`approved`, `rejected`, `needs_investigation`), no
  custom states and no workflow engine. Nine catalogued reasons, **paired
  to the decisions they may accompany**, so "approved because the
  interpretation is incorrect" is a sentence the trail cannot contain.
  The pairing is served from the API rather than duplicated in clients.
  A comment is required where the reason alone explains nothing.
- Snapshots record **identity, not the artefact**: checksum, rule id and
  version, contract version, three policy versions, and a fingerprint
  over the support chain. No statement type, subject, object, quantity or
  support payload - and no field into which one could be written.
- Authorization: a new `record_engineering_review` capability, granted to
  engineer and administrator, kept separate from the read permission so a
  future auditor role needs no route change. No "reviewer" role invented.
  The reviewer is the authenticated identity; a test submits a forged
  `reviewer` in the body and asserts it is ignored.
- The Workspace stays read-first: the review action occupies its own
  panel, and the statement list carries two badges that say different
  things - what the *pipeline* produced, and what an *engineer* decided.
  The UI never says `Corretto`/`Errato` or ✓/✗, `approved` is not green,
  and "mai revisionato" is a state rather than a decision - all asserted.
- Prepares the Knowledge Graph and implements none of it: a promotion
  rule can be written as "current decision `approved` and applicability
  `applies`" against contracts that already exist.
- Distinct from the pre-existing `review_workflow` context (Milestone
  10.1), which reviews Proposed Claims on the legacy graph path with a
  mutable status. The two are not merged, not renamed and not related;
  `human_review.md` states the difference.
- Known limits: review targets are semantic statements only
  (`ReviewTargetType` is generic and has one member, deliberately); no
  assignment, voting, approval chains or notifications; the document-wide
  summary is unpaged and costs one count per reviewed target; comments
  are plain text; authorization stays per-role rather than per-project.
- Dependencies: Milestone 30.1 (the statements it judges), EPIC 30.2 (the
  Workspace it extends) and EPIC 30.3 (the identity it attributes to).

**EPIC 30.3 — Identity, Authentication and Audit Foundations** - *Completed*
- Objective: make every future engineering action attributable to a
  verified person. Human Review, collaboration and Knowledge Graph
  governance all depend on knowing *who*, and none of them could be built
  before that existed.
- Delivered: an `identity` bounded context (users, credentials, sessions,
  roles, capabilities, audit identity, project access), an `audit`
  bounded context (append-only events), server-side session
  authentication, deny-by-default authorization at the API boundary, and
  a frontend session with a login screen, route guard, identity display
  and expiry handling. **No engineering behaviour changed and no pipeline
  rule changed.**
- Two decisions recorded in
  [ADR-0022](../architecture/adr/0022-session-authentication-and-password-hashing.md):
  - **Opaque server-side sessions in an `HttpOnly` cookie**, not JWT. A
    stateless token cannot be revoked, which would make logout a
    client-side gesture and leave a disabled account's sessions
    authenticating requests until they expired. SSO and MFA fit the
    session model without changing it - SSO opens the same session by a
    different proof, MFA gates its creation.
  - **scrypt from `hashlib`**, in a self-describing
    `algorithm$parameters$salt$digest` form, with `needs_rehash` and a
    re-hash at login. Argon2id is the better algorithm and was declined
    *for now* because it is a compiled dependency and this repository has
    no dependency manifest to record one in - the single largest piece of
    operational debt it has. The upgrade path is built rather than
    promised.
- **The rule the whole EPIC turns on: audit identity attaches to actions,
  never to artefacts.** An entity, a fact and a semantic statement are
  functions of a document's bytes and the versioned rules that read them;
  a user on any of them would end determinism. An architecture test fails
  if any engineering domain module imports the identity or audit context,
  a second fails on a `user_id`/`actor`/`created_by`/`owner` column in any
  engineering ORM model, and an API test runs the same stage over the same
  document as two different engineers and asserts the artefacts compare
  equal.
- **Deny by default.** Authentication is middleware plus a short list of
  explicitly public routes, so a router added next year is protected
  because nobody did anything. `tests/api/test_api_security.py` walks
  every path in the live OpenAPI document and requires each to be either
  declared public or to refuse an anonymous caller `401` - with a
  companion test asserting the sweep can build a URL for every route, so
  a new path parameter cannot make a hole look like a pass.
- Three levels only - anonymous, engineer, administrator - and routes
  declare a **capability** rather than a role, so a future
  project-membership model can grant one from a second source without any
  route changing. Deliberately not a dozen speculative roles.
- Hardening, each with a test: password never stored or reversible and
  unrepresentable in any response schema; session fixation structurally
  impossible; CSRF by a **session-bound** token rather than plain
  double-submit; `hmac.compare_digest` throughout and a full key
  derivation paid even for an unknown address, so timing discloses
  nothing; unknown address, wrong password and disabled account answered
  identically; no web storage, no `dangerouslySetInnerHTML`, and no
  redirect to a supplied address anywhere in the frontend.
- Audit trail: append-only, with no update or delete on the port at all.
  Records login, failed login, logout, password change, user create and
  disable, project creation, document upload, pipeline execution and
  access denials, each with actor, timestamp, action, resource and
  outcome. Nothing sensitive is *representable* - there is no field a
  credential could be written to. An audit write that fails deliberately
  does not fail the audited action, and a test pins that trade.
- Project ownership is recorded from the authenticated identity and
  consulted on **deletion only** - the destructive operation, and the one
  worth guarding while no membership model exists. `created_by` is no
  longer accepted from the request body, where it meant whatever the
  caller typed.
- Existing behaviour preserved: all 3079 backend tests pass, including
  every pre-existing one, now running against the **protected**
  application through the same `install_security` the real one uses.
- Known limits, stated rather than deferred quietly: **no dependency
  manifest** (the reason Argon2id was declined); no rate limiting on
  login; no MFA, SSO or password-reset workflow; authorisation is
  per-role rather than per-project; cookies are set without `Secure` for
  plain-HTTP development and a TLS deployment must set it; security
  headers belong to a reverse proxy and are documented but not set.
- Dependencies: EPIC 30.1.3 (the governed public API it protects) and
  EPIC 30.2 (the Workspace whose actions it attributes).

**EPIC 30.2 — Engineering Workspace** - *Completed*
- Objective: give an engineer a way to *validate* the platform's
  engineering claims, not merely observe that the pipeline ran. The
  deterministic pipeline could produce a `HAS_RATED_POWER` statement;
  nothing let anyone check one against the drawing it came from.
- Delivered: `/documents/{id}/workspace`, a document-centric workspace
  with three regions - source viewer, engineering explorer, inspector -
  in which the whole support chain
  `Semantic Statement → Fact → Entity → Evidence → Canonical Source
  Location → Original Document` is navigable in both directions. Every
  transition follows a reference an artefact declares
  (`entity.evidence[].evidence_key`, `fact.subject_entity_key`,
  `statement.supporting_fact_keys`); no relationship is inferred, and an
  architecture test fails on any fuzzy-matching import, any comparison of
  two artefacts by observed text or quantity value, any rule identifier
  declared in frontend code, any direct `fetch`, and any write.
- Two decisions recorded in
  [ADR-0021](../architecture/adr/0021-engineering-workspace-document-viewer.md):
  - **No support-chain endpoint.** The four artefact endpoints already
    return their document's whole set with support references inline, so
    the chain costs four requests once and every traversal afterwards is
    a map lookup. A projection endpoint would only have created a second
    place where a support relationship is described.
  - **No PDF rendering library.** Highlights are drawn on an SVG map of
    the canonical representation, at the bounding boxes the parser
    recorded, joined by `(page_number, block_reading_order,
    span_reading_order)`. PDF.js would have introduced a second source of
    page geometry, and no test could detect the day the two disagreed.
    The original bytes remain one tab away and un-annotated.
- One backend addition:
  `GET /documents/{id}/canonical-representation/pages/{page_number}`, a
  strict read-only projection of the stored representation - an API test
  asserts it is identical to that page of the full read - so the page map
  reads the page it displays rather than every page of a drawing set.
- Distinctions the UI is built to preserve, each with a test:
  **unrun ≠ empty**, **empty ≠ failed**, **ambiguous ≠ rejected**,
  **diagnostic ≠ semantic statement**. A declined subject appears in
  Diagnostiche and never in the statements list. `interpreted` is not
  green anywhere, and the copy says in as many words that it means
  *produced by a rule*, not *approved by an engineer*.
- Partial availability: the five reads settle independently, so a semantic
  endpoint returning 500 leaves Evidence, Entities and Facts fully
  inspectable.
- **Inspection-only, deliberately.** No approve, reject, correct, edit,
  merge, override or annotate, and no control implying one. An approval
  needs an actor, a timestamp, a scope, a reason, an audit trail and a
  rule for what a pipeline re-run does to it - a governed Human Review
  bounded context, which is the recommended next milestone.
- Known limits, stated rather than deferred quietly: there is still no
  authentication or authorisation of any kind; the canonical page map
  renders extracted text only, so a purely graphical drawing looks sparse
  there; and the *Originale* tab delegates to the browser's own PDF
  viewer, where any JavaScript embedded in a document is handled inside
  the browser's sandbox and is not additionally disabled by SubstationOS.
- Dependencies: Milestone 30.1 (the last pipeline stage it inspects) and
  Milestone 30.1.3 (the governed document endpoints it reads).

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
- **The Canonical Facts graph projection is still here, no longer read
  by the Engineering Engine.** EPIC 31.2 moved engineering retrieval onto
  the Governed Knowledge Graph, but `graph_builder`,
  `project_knowledge_graph` and `graph_query` remain because four route
  groups still serve them. The retirement gate and the objective
  condition that opens it are in
  [ADR-0026](../architecture/adr/0026-governed-structured-retrieval.md)
  section 9; the debt entries below now describe **that lineage's own
  API**, not the engine.
- **One temporary adapter at the Context Builder seam (EPIC 31.2).**
  `governed_context_projection.py` maps governed retrieval results into
  the `KnowledgeCandidate` vocabulary Context Builder, Prompt Builder and
  Engineering Response speak, and carries a score-shaped ordering value
  derived purely from the documented match-strategy rank. Both go when
  Context Builder consumes `GovernedRetrievalResult` directly - the
  stated retirement condition, asserted by an architecture test. Deferred
  deliberately: migrating retrieval and its four consumers at once would
  have made a quality regression in any of them invisible.
- **`structured_retrieval`'s value objects still reference
  `graph_builder`.** `KnowledgeCandidateReference.graph_entity_id` is a
  `GraphEntityId` and `KnowledgeCandidateRelationship.relationship_type`
  a `GraphRelationshipType`, both exposed on the wire by
  `KnowledgeCandidateRead`. Retiring `graph_builder` therefore also
  requires the Context Builder migration above, or a deliberate wire
  contract change. Recorded so the dependency is not discovered halfway
  through the retirement.
- **Two legacy retrieval capabilities have no governed counterpart
  (EPIC 31.2).** Attribute-bag search, and lexical matching over entity
  types and attribute values. Neither is a gap to be filled: the governed
  graph has no property bag by decision (ADR-0024), and the engineering
  question underneath attribute search is a governed relationship
  traversal. Classified as `LEGACY_BEHAVIOUR_NOT_SUPPORTED` by a test in
  `tests/api/test_governed_retrieval_baseline.py`.
- **Governed designation matching is a Python-side scan of the scoped
  node set.** Deliberate: folding in SQL would make the answer depend on
  the database's collation, and a retrieval contract promising
  reproducibility cannot rest on that. No index added ahead of a measured
  need - see `performance_baseline.md`, "Governed Structured Retrieval".
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
- **Engineering Response's `SUMMARY`/`TECHNICAL_EXPLANATION`/
  `ASSUMPTIONS`/`NEXT_ACTIONS` sections are always empty.** Populating
  them honestly requires either genuine semantic segmentation of the
  provider's own free text (out of scope - this builder performs no AI
  usage) or a future provider capability emitting genuinely structured,
  machine-parseable output. Deliberate and documented, not an
  oversight — see ADR-0015 and `engineering_response.md`'s Sections
  table.
- **Engineering Response produces nothing for a failed or cancelled
  invocation.** Only a successful `LLMResponseEnvelope` ever reaches
  this builder (per `LLMInvocationResult`'s own invariant); how a
  `terminal_error` is ever shown to an engineer is left to a future
  milestone - not solved speculatively here.
- **Engineering Response is the first domain bounded context whose
  primary input originates from the application layer
  (`LLMResponseEnvelope`) rather than an upstream domain context.**
  Resolved by a single, explicit translation seam
  (`app/services/engineering_response_service.py`) that restates the
  application type into a domain-owned shape before the domain ever
  sees it - see ADR-0015. Any future domain context with a similar need
  should follow the same pattern rather than inventing a new one, or
  worse, importing `app.application.**` directly into `app/domain/**`.
- **Engineering Session has no persistence.** A session's lifetime
  today is exactly one client's own request/response chain - each API
  call accepts and returns the full session; nothing is held
  server-side between calls. A real, multi-request session store is
  explicit future work (likely alongside Milestone 20's Conversation
  Foundation), not solved speculatively in Milestone 19 - see ADR-0016.
- **Engineering Session's `update-configuration` endpoint was not
  literally named in Milestone 19's own "equivalent to" endpoint list.**
  Added because `CONFIGURATION_UPDATED` is an explicitly required
  timeline event type that no other endpoint could ever exercise - a
  small, documented, in-scope extension, not scope creep - see
  `engineering_session.md`.
- **Conversation has no persistence**, the same posture Engineering
  Session already takes - a conversation's lifetime today is exactly
  one client's own request/response chain. A real, multi-request
  conversation store is explicit future work, not solved speculatively
  in Milestone 20 - see ADR-0017.
- **Conversation's `attach-response` and `change-status` endpoints were
  not literally named in Milestone 20's own "such as" endpoint list.**
  Added because `ENGINEERING_RESPONSE_ATTACHED` (an explicitly required
  Turn responsibility) and `STATUS_CHANGED` (an explicitly required
  timeline event type) would otherwise have no real caller ever
  exercising them - the same documented, in-scope extension precedent
  ADR-0016 already established for `update-configuration` - see
  `conversation.md`.
- **Only one ConversationTurn may be open at a time.** A deliberate
  simplification keeping the API surface small (no `turn_id` parameter
  needed on `add-message`/`attach-response`/`complete-turn`); if a
  future need for concurrent or branching turns emerges (e.g. parallel
  tool calls), it is a documented extension point in ADR-0017, not
  solved speculatively now.
- **Working Memory's `CURRENT_OBJECTIVE`/`CURRENT_EQUIPMENT`/
  `CURRENT_ELECTRICAL_AREA`/`CURRENT_TASK` entry types are permanently
  unpopulated.** No structural signal exists today that identifies
  them without semantic interpretation of message content, which this
  milestone forbids. Deliberate and documented, not an oversight - see
  ADR-0018 and `working_memory.md`'s entry-type table. Populating them
  requires either a future capability with genuinely structured input
  (e.g. an explicit field a user sets) or a deliberate, separately
  justified decision to introduce semantic interpretation - not solved
  speculatively here.
- **Working Memory has no persistence**, the same posture every
  Milestone 19-20 bounded context already takes - a `WorkingMemory`'s
  lifetime is exactly one client's own request/response chain. This is
  more load-bearing here than elsewhere: Working Memory is explicitly
  designed to always be rebuildable rather than persisted, so this is
  not merely deferred work but the milestone's own core design choice
  (see ADR-0018).
- **Engineering Request Classification's rule vocabulary needs ongoing
  maintenance as real request phrasing is observed.** Novel phrasing
  falls to `GENERAL_ENGINEERING_REQUEST` or `UNSUPPORTED_REQUEST`
  rather than being guessed at - the intended trade-off of a
  deterministic classifier (ADR-0019), but it does make vocabulary
  coverage an explicit, ongoing task rather than something a model
  absorbs implicitly.
- **The classifier's engineering domain vocabulary is limited to
  SubstationOS's current scope** (primary substations, HV/MV,
  transformers, switchgear, protection, measurement, cables,
  equipment, bays/montanti, drawings, project documentation). A
  request using engineering terms outside that list classifies as
  `UNSUPPORTED_REQUEST` - correct today, and something EPIC 8's
  multi-domain expansion must revisit alongside the Canonical Domain
  itself.
- **The Engineering Engine has no persistence and no transaction.**
  Nothing is stored - not the `EngineeringResponse`, not the aggregate
  update proposals, not the execution record. The *intended future*
  transaction boundary would atomically persist all of them together;
  **that transaction does not exist today**, and the engine neither
  implements it nor depends on it (ADR-0020) - Milestone 23B.1's
  document-lookup workflow included.
- **The Engineering Engine supports five workflows.** Five of the ten
  `EngineeringIntentType` values return `UNSUPPORTED`. This is deliberate
  (23A proved the architecture, 23B.1 proved it is extensible, 23B.2
  proved extension gets *cheaper* as the shared pipeline matures, 24.1
  proved a reasoning workflow costs the engine no more than a rephrased
  prompt, and 24.2 proved a workflow whose *pipeline* differs still costs
  it nothing but declarations); there is deliberately no fallback workflow
  and no "just ask the LLM" path for unknown intents.
- **A comparison reports no structured findings.** The ADDED / REMOVED /
  MODIFIED / UNCHANGED grouping exists only as prose in the response body,
  because extracting it would mean parsing free text to manufacture
  engineering findings. A consumer can read the outcome
  (`COMPARABLE` / `INSUFFICIENT_EVIDENCE` / `CONFLICTING_EVIDENCE`)
  machine-readably and must read the findings themselves.
- **A comparison compares evidence, not installations.** Two subjects
  whose evidence is thin will compare as thin, and the system says so
  rather than filling the gap. It never compares a subject against typical
  practice for its equipment type.
- **A verification verdict is the model's judgement, not the system's.**
  SubstationOS reads a declared token and bounds it structurally when no
  evidence was retrieved; it does not itself decide whether a statement is
  true. `SUPPORTED` means "a model, given only this project's reviewed
  evidence, said the evidence supports this" - it is not an engineering
  sign-off, and the response's own uncertainty declarations remain the
  honest measure of how far it should be trusted.
- **An explanation is a differently-instructed prompt, not a different
  reasoning capability.** `ENGINEERING_EXPLANATION` retrieves the same
  governed graph evidence as a knowledge query and asks the model to set
  out function and role rather than answer directly. It performs no
  multi-step reasoning, consults no document contents, and builds no
  causal or functional model of the installation - the quality of an
  explanation is bounded by what the reviewed graph already holds.
- **`DOCUMENT_LOOKUP` reports where equipment is mentioned, not what the
  documents say.** It reads the Engineering Index only: no document is
  opened, parsed, summarized, rendered, or ranked by its contents, and no
  file is returned - the answer is a set of document references with page
  or locator evidence. A document whose mentions were never indexed is
  invisible to it, which is why "no matching documents" honestly reports
  that the equipment may be undocumented *or* simply not indexed yet.
- **The engine still does not derive retrieval criteria from request
  text** - and never will. Since Milestone 23B.3 a separate stage does,
  deterministically, *before* the engine: the Classification-to-Retrieval
  Bridge. The engine continues to receive an explicit execution request
  and is now prevented by architecture test from importing the
  classifier, the rule table, the request normalizer, or the bridge.
- **The bridge resolves no conversational reference.** "Come funziona
  questo montante?" names no designation, so it is refused rather than
  guessed at. Resolving "questo" needs Working Memory, which the bridge
  deliberately does not consult - a request that means something only in
  the context of the previous turn is not yet answerable end to end.
- **The canonical vocabulary the bridge resolves against is narrow.**
  Canonicalization recognizes a letter-prefix-then-digits shape over
  seven entity types, so real designations like "87T" (an ANSI device
  number) and "Q52" become lexical terms rather than entity lookups.
  Lexical retrieval still finds them; entity lookup would be stronger.
  Aligning canonical entity types with the Electrical Ontology's own
  `EquipmentDefinition` ids and aliases remains the deliberate open
  integration point Canonicalization's own module docstring names.
- **`EngineeringIntentEvidenceType.STRUCTURAL_CONTEXT` is defined but
  never produced.** The two structural Working Memory signals the
  classification input accepts are carried and available but do not
  currently influence classification or generate evidence - reserved
  for a future capability with a demonstrated need, not wired
  speculatively (the same "reserved but honestly unpopulated"
  precedent ADR-0015 and ADR-0018 already established).

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
