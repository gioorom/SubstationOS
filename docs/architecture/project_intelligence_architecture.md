# Project Intelligence Architecture

**Status:** Proposed architecture, not yet implemented.
**Scope:** Architecture design only — no code, no YAML, no engineering
document was analyzed to produce this document.

This document defines how SubstationOS turns uploaded, project-specific
engineering documentation into traceable, queryable engineering knowledge
— scoped to one real installation at a time. It sits directly on top of two
existing governing documents and must never contradict either:

- **`CLAUDE.md`** — how SubstationOS is built: Domain Driven Design,
  Ports & Adapters, the dependency rule, and the ontology reference
  pattern under `app/domain/ontology/`.
- **`knowledge/protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`** — how raw
  documentation becomes trusted **canonical** engineering knowledge:
  extraction levels, confidence tiers, review states, conflict
  resolution, and versioning.

This document answers a question the Canonical Knowledge Protocol
deliberately does not: *the canonical domain (what a transformer is, what
attributes it can have) already exists — how does one real project's
uploaded documents become a trustworthy instance of that domain?*

## Positioning: what SubstationOS is, and is not

Per `PRODUCT_VISION.md`, SubstationOS is an **Engineering Operating
System**, not a document repository and not a PDF parser. Concretely:

- A document repository stores files. SubstationOS stores **facts**, each
  one traceable to a file, a page, and an engineer's review.
- A PDF parser produces text. SubstationOS produces **typed engineering
  entities** — instances of the canonical ontology's `EquipmentDefinition`
  and `AttributeDefinition` concepts — connected into a graph.
- SubstationOS is a **Project Intelligence Platform**: it takes the
  canonical domain (the vocabulary of what *can* exist in any substation,
  data center, or industrial plant) and, for one specific real
  installation, builds the trustworthy record of what *does* exist there,
  per that project's own documentation.

### Grounding in what already exists

This is not a greenfield design. Reading the current codebase before
writing this document surfaced real, working infrastructure this
architecture must build on, not duplicate or contradict:

| Already exists | Where | What it does today |
|---|---|---|
| `Project` persistence model | `app/models/project.py` | id, name, unique `code`, customer, EPC, location, voltage level, status, description — already a solid Project record. |
| `Document` persistence model | `app/models/document.py` | filename, path, format, a `category` field with a `DocumentCategory` enum — **the field exists; nothing populates it yet.** |
| Project graph model | `app/models/knowledge_graph.py` | `ProjectEntity` (typed, per-project, JSON attributes, source document) and `EntityRelation` (typed, confidence float, source document) — a real, working graph store. |
| AI extraction pipeline | `app/services/ai/*` | A working `AIProvider` port (`base.py`) with a Claude adapter, entity and relationship extraction against Anthropic's API. Relationship extraction exists but is **currently disabled** in the ingest flow. |
| Ingest orchestration | `app/services/knowledge_graph.py` (`ingest_document`) | On PDF upload, extracts text, calls the AI extractor, and **persists the result directly into the graph** — no review step of any kind. |
| Topology inference | `app/services/topology/*` | A rule-based matcher for **one hardcoded transformer-bay template** — real, but not general. |
| Project health scoring | `app/services/project_intelligence.py` | A document-count heuristic, not wired to the graph at all. |

The single most important architectural gap this document exists to close:
**today, AI-extracted facts are written straight into the queryable graph,
with no review state, no confidence policy, and no way to distinguish a
confirmed fact from an unreviewed guess.** This is exactly the failure mode
the Canonical Knowledge Protocol was written to prevent at the canonical
level — this document applies the same discipline at the project level.

---

## 1. Architecture Vision

```
Canonical Domain
      ↓
Create Project
      ↓
Upload Documents
      ↓
Document Classification
      ↓
Document Indexing
      ↓
Knowledge Extraction
      ↓
Project Knowledge Graph
      ↓
Semantic Query Engine
      ↓
AI Assistant
```

### Canonical Domain

The pre-existing, project-independent **vocabulary** — what can exist, in
any project, of any discipline (`app/domain/ontology/**`):

- **Equipment Definitions** — `EquipmentDefinition`, implemented.
- **Attribute Definitions** — `AttributeDefinition`, implemented.
- **Relationship Vocabulary** — the typed ways equipment concepts may
  relate (`connects_to`, `feeds`, `protects`, `contains`, ...) — designed
  by this architecture (§7) and by ADR-0003, not yet implemented as a
  canonical-domain concept in `app/domain/ontology/**` (today, typed
  relationships exist only as project-scoped `EntityRelation` rows, which
  is a different thing — see §7).
- **Domain Constraints** — invariants a valid instance must satisfy (e.g.
  the validators already implemented per `CLAUDE.md` §4.3:
  `AttributeDefinitionValidator`, `EquipmentDefinitionValidator`) —
  implemented for uniqueness/shape constraints; a general constraint
  vocabulary beyond that is designed, not yet implemented.

Every project consumes this vocabulary; no project ever adds to or edits
it as a side effect. Extending the Canonical Domain is a separate,
deliberate, human-governed process — the same YAML-authoring discipline
`CLAUDE.md` §7 already requires — never an automatic consequence of one
project's extraction (see §6).

**A note on ownership, corrected for Architecture Freeze v1.0:** Extraction
Levels 0–8, Review States, Confidence Policy, and Canonicalization Rules
are **not** Canonical Domain concepts. They belong to the **Canonical
Knowledge Protocol** (`knowledge/protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`
§§3, 5, 6, 8) — the *methodology* by which any knowledge, canonical or
project-scoped, is produced and trusted. The Canonical Domain is the
*vocabulary* that methodology's output is eventually expressed in. An
earlier version of this document blurred the two by listing "Ontology
Levels 0-8" as part of the Canonical Domain; that wording is corrected
here and in the architecture diagram below.

### Create Project

A Project is instantiated: it is given an identity (per the existing
`Project` model, its unique `code`), its business metadata (customer, EPC,
location — already modeled), and — new to this architecture — a bound
reference to the version of the Canonical Domain in effect at creation
time (see §10, Milestone 8 recommendations). Nothing about a substation's
equipment exists yet; only the container that will hold it does. This
stage is deliberately thin and fast, matching the existing implementation's
shape.

### Upload Documents

Files are received into a Project's own Document Repository (§2). Upload
is a storage operation only — no interpretation happens here. This matches
the existing `POST /documents/upload` endpoint's role, with one required
change: project association becomes mandatory, not optional (today's
`Document.project_id` is nullable; see §10).

### Document Classification

Every uploaded document is assigned a document type from a governed
taxonomy (§4) before any content is read for meaning. Classification
answers *"what kind of document is this?"*, never *"what does it say?"*.

### Document Indexing

A fast, automated pass builds the Engineering Index (§5): a structured
inventory of what a document appears to mention — equipment tags, signal
tags, cable identifiers, page locations — without engineering judgment,
without review, and without yet being trusted as fact.

### Knowledge Extraction

The Canonical Knowledge Protocol's extraction levels and lifecycle (Raw
Extraction → Engineering Review → Canonical/Project Knowledge) run against
the classified, indexed document, scoped to this one Project. This is
where facts are actually produced — reviewed, confidence-scored, traceable
(§6).

### Project Knowledge Graph

Reviewed, approved, project-scoped facts are assembled into a connected
conceptual model of the installation (§7): equipment, cables, signals,
cabinets, terminal blocks, frames, protection relays, and the documents
and pages that support every one of them.

### Semantic Query Engine

Natural-language questions about one project are answered by querying this
graph — never by asking an LLM to recall or guess (§8).

### AI Assistant

The user-facing surface: takes the Semantic Query Engine's sourced,
traceable results and presents them conversationally, always attaching the
traceability record (§9). The Assistant is a presentation layer over
proven knowledge, not a source of it.

---

## 2. Project

A Project represents one real engineering installation: a Primary
Substation, a Transmission Substation, a Data Center, an Industrial Plant,
a Renewable Plant, or any future installation type. The architecture must
generalize across all of them without modification — no component upstream
of the Canonical Domain may hardcode substation-specific assumptions.

### What already satisfies this

The existing `Project` model (id, name, code, customer, EPC, location,
status, description) is already discipline-agnostic in shape. One field is
not: `voltage_level`, which only makes sense for electrical installations.
This is noted, not urgently flagged — per `CLAUDE.md` §12 (YAGNI), the
product's actual current focus is HV/MV substations, and generalizing this
field before a second discipline is real work would be speculative. The
architectural requirement is narrower and already met: **nothing above the
Canonical Domain layer may assume "substation"** — Document Classification,
the Engineering Index, the Knowledge Graph's conceptual model, and the
Semantic Query Engine are all discipline-neutral containers whose content
shape comes entirely from whichever Canonical Domain concepts a given
project's documents turn out to instantiate.

### Binding invariant

A Project instantiates exactly one version of the Canonical Domain at any
given time (§10). Project names, codes, and every other business fact
about a Project are runtime data — never referenced by name in code, in a
prompt, or in a classification rule. A rule that says "if project name
contains 'Gamma'" is a defect, full stop, regardless of how convenient
it would be during development.

### Project as a boundary

Every artifact this architecture produces — a document, an index entry, an
extracted fact, a graph node, a query result — belongs to exactly one
Project. This is not a soft convention; it is the multi-tenancy mechanism
the entire platform's scalability depends on (§10), and it already exists
in the codebase as the `project_id` foreign key pattern `docs/ARCHITECTURE.md`
names as a "single source of truth" principle.

---

## 3. Document Repository

Each Project owns its own documents; documents are never shared or
inferred across Projects. Supported document families, and the role each
plays:

| Family | Role |
|---|---|
| **PDF** | The primary carrier of functional schematics, single-line diagrams, cable schedules, and protection settings — the majority of extractable engineering content, per the Canonical Knowledge Protocol's extraction levels. |
| **Excel** | Structured tabular data that is often *already* close to canonical shape — cable schedules, equipment lists, I/O lists. Because it is already tabular, it is frequently a **higher-confidence** source than an equivalent hand-drawn PDF table (see §6's confidence policy). |
| **DWG** | Native CAD drawings (general arrangement, layout, routing) — geometric and spatial truth a rendered PDF export can lose. Supports the Civil and Layout document types (§4) with the highest-fidelity source available. |
| **Images** | Site photographs, scanned legacy drawings, nameplate photos. Typically the lowest-confidence source (handwriting, glare, poor scans) but often the *only* source for as-built or historical information no digital drawing captures. |
| **Vendor Manuals** | Equipment-class documentation (not project-specific) that corroborates or supplies default characteristics for a specific instance's `AttributeDefinition` values, without itself being project-specific engineering truth — always cited as a secondary, corroborating source, never as authoritative over a project's own as-built documentation. |
| **Standards** | Referenced, not extracted from directly — a Level 8 "Engineering Rule" (per the Canonical Knowledge Protocol) may cite a standard; the standard document itself, if uploaded for reference, is indexed for retrieval but not mined for project facts. |
| **Commissioning Reports** | Feed Extraction Level 7 (Commissioning) — the record of what was actually tested, and against what criteria, for this specific installation. |
| **Construction Drawings** | The as-built record — frequently the authoritative source when it conflicts with an earlier design-stage drawing (see the Canonical Knowledge Protocol §7, Conflict Resolution). |

Every document family is stored, classified, and indexed through the same
pipeline (§1). No family gets a bespoke ingestion path — the pipeline's
stages differ in *which extraction levels apply*, never in *whether the
pipeline applies*.

### Document scope: PROJECT versus CANONICAL_LIBRARY

Not every document belongs to a Project. **Vendor Manuals** and
**Standards** (above) are frequently reusable across many projects — a
manufacturer's datasheet or an IEC standard does not describe one
installation, it describes a class of equipment or a rule every
installation may need to reference. SubstationOS therefore recognizes two
explicit, named document scopes:

- **`PROJECT`** — the document was uploaded inside a specific Project (§2),
  belongs to that Project alone, and is the only kind of document that
  feeds that Project's Engineering Index (§5) and Project Knowledge Graph
  (§7). This is the scope every document family above defaults to except
  the two named next.
- **`CANONICAL_LIBRARY`** — the document is a reusable reference (vendor
  manual, standard, internal specification), owned by no single Project,
  governed by a separate process, and never itself a direct source for a
  Project Knowledge Graph node. A `CANONICAL_LIBRARY` document may still
  be *cited* as corroborating context from within a Project (per the
  Vendor Manuals row above), but the citation points to the library
  document, it does not pull the library document *into* the Project's
  own scope.

**This distinction must never be represented by a nullable Project
reference.** A document with no Project is ambiguous under a nullable
scheme — it could mean "not yet assigned," "upload error," or
"deliberately global," and a nullable foreign key cannot tell those apart.
`CANONICAL_LIBRARY` must be a first-class, explicit scope value, not the
absence of one. This is recorded as a formal decision in
[ADR-0005](adr/0005-project-vs-canonical-library-document-scope.md); the
schema change it implies is future implementation work, out of scope for
this document.

---

## 4. Document Classification

Every uploaded document is assigned a type from a governed taxonomy before
extraction begins:

- Functional Diagram
- Construction Drawing
- Cable List
- Interconnection Table
- Protection Logic
- Vendor Manual
- Commissioning Procedure
- Civil Drawing
- Layout

This taxonomy governs which of the Canonical Knowledge Protocol's nine
extraction categories (and their underlying Levels 0–8) are even
attempted against a document — a Cable List is never run through the
`protections.md` prompt; a Protection Logic document is never run through
`cables.md`. Classification is a routing decision, not a content decision.

### Why classification must precede extraction

1. **Correct prompt selection.** Each extraction prompt (`knowledge/extraction/prompts/*.md`)
   is scoped to a specific document shape. Running the wrong prompt against
   the wrong document type does not merely waste effort — it invites the
   exact failure mode the Canonical Knowledge Protocol's Extraction Rules
   forbid: an extraction session forced to "find" equipment in a document
   that is actually a cable schedule will either extract nothing (safe,
   but wasteful) or over-reach into inference (forbidden).
2. **Validation.** A document classified as "Cable List" that an
   extraction pass finds contains no cable-shaped tables at all is a
   detectable inconsistency — either the classification was wrong or the
   document is malformed. Classification-before-extraction makes this
   check possible; classification-after-extraction (or no classification
   at all) does not.
3. **Cost and latency.** Extraction against an AI provider is the most
   expensive stage in the pipeline. Classification is cheap by comparison
   and prunes the extraction search space before that cost is incurred.
4. **Existing schema readiness.** `Document.category` already exists in
   the persistence model with a (narrower, substation-specific) enum. This
   stage is the missing piece that actually populates it — today the field
   exists and nothing sets it.

Classification itself may be rule-based (filename conventions, title-block
OCR pattern matching), AI-assisted, or both — that choice is an
implementation decision for a future milestone, not fixed by this
architecture. What is fixed is that classification is a distinct,
auditable stage whose *output* (the assigned type) is itself a fact with
its own confidence, not a silent side effect of extraction.

---

## 5. Engineering Index

The Engineering Index is a structured inventory of what each document
**appears to contain**, built automatically at the Document Indexing
stage, immediately after classification and before deep extraction.

For every document, the index records candidate mentions of:

- Equipment (tags, symbols, labels)
- Signals (tag names)
- Cables (identifiers)
- Cabinets and Frames (location tags)
- Protections (device numbers, function tags)
- Drawings (cross-referenced sheet/drawing numbers)
- Functions (named procedures, logic blocks)
- Cross References (references to other documents or sheets)

— each entry carrying, at minimum, the document it came from and the page
it appeared on.

### Why the Engineering Index is not the Knowledge Graph

This is the most important distinction in this architecture, and the two
are frequently conflated in systems that do not separate them — which is
exactly what today's implementation does (`ingest_document` writes
AI-extracted mentions directly into the same table the query API reads
from).

| | Engineering Index | Project Knowledge Graph |
|---|---|---|
| **Built by** | Automated pass only | Engineering Review + canonicalization (§6) |
| **Trust level** | None — a candidate mention, not a fact | Reviewed and approved, per the Canonical Knowledge Protocol's review states |
| **Purpose** | Search, navigation, extraction routing, completeness checking ("has this document been indexed yet?") | Answering engineering questions with traceable authority |
| **Relationships** | None — flat mentions per document | Rich, typed relationships between entities (§7) |
| **Mutability** | Rebuilt freely as classification/indexing logic improves | Append-only and versioned, per the protocol's Versioning Strategy |
| **Queried by** | Document search, "which documents mention X?" | The Semantic Query Engine (§8) |

The Engineering Index exists so a user can find and browse documents
*while* extraction and review are still in progress — it is available
almost immediately after upload. The Project Knowledge Graph only ever
contains what an engineer has actually approved. A mention in the
Engineering Index is a lead; a node in the Project Knowledge Graph is a
fact. Conflating the two — as today's implementation does — means every
query answer is only ever as trustworthy as raw, unreviewed AI output,
which directly violates the Canonical Knowledge Protocol's Canonical Rules
(§8 of that document) applied at project scope.

---

## 6. Knowledge Extraction

Knowledge Extraction is the Canonical Knowledge Protocol's full lifecycle
(Raw Extraction → Engineering Review → Canonical/Project Knowledge),
executed per document, per extraction level, scoped to one Project. Every
rule in that protocol — no inference, mandatory source and page citation,
explicit confidence tiers, no automatic merging, conflicts preserved for
review — applies here without exception or relaxation. A Project's scale
or deadline is never a reason to skip Engineering Review.

### The non-negotiable invariant

**Extraction must never modify Canonical Knowledge. Extraction only
creates Project Knowledge.**

Concretely:

- An extraction session may only ever produce **instances** that reference
  existing `EquipmentDefinition` and `AttributeDefinition` entries by
  `id` — it never creates, edits, or deletes an entry in the Canonical
  Domain (`app/domain/ontology/**`) as a side effect of processing a
  project's documents.
- If a document contains something that does not map to any existing
  canonical concept (a genuinely new equipment category, an attribute
  never seen before), extraction does not invent one. It records the raw
  fact with an explicit `Open question: no matching canonical concept`
  and stops there. Extending the Canonical Domain to accommodate a
  genuinely new concept is a **separate, deliberate process** — the same
  human-governed YAML-authoring discipline `CLAUDE.md` §7 already
  requires — never an automatic or implicit consequence of one project's
  extraction run.
- This separation is what makes "thousands of projects" (§10) safe: no
  project's extraction session can corrupt, dilute, or silently extend the
  vocabulary every other project also depends on.

### How extraction enriches project knowledge

Each approved fact from Engineering Review becomes a candidate for
canonicalization *at the project level* — the same Stage 4 discipline the
Canonical Knowledge Protocol defines, scoped to "this Project" instead of
"the whole domain." A Project's canonical knowledge is versioned exactly
as the protocol's §9 describes: Version 1 on first canonicalization,
Version 2+ only when the asserted fact itself changes (a new document
revision, a resolved conflict), superseded versions retained permanently.
The result of this stage — and only this stage's output — is what may
populate the Project Knowledge Graph (§7).

---

## 7. Project Knowledge Graph

A conceptual model, not a database design. The graph represents the
installation as engineers actually think about it: things, and how they
relate.

### Node concepts

| Node type | Represents | Typed by (Canonical Domain reference) |
|---|---|---|
| Equipment | A physical apparatus instance | `EquipmentDefinition` |
| Cable | A physical cable instance | `EquipmentDefinition` (cable-category) |
| Signal | A tagged I/O point | Signal concept (Extraction Level 5) |
| Cabinet | A physical enclosure | `EquipmentDefinition` (cabinet-category) |
| Terminal Block | A wiring termination point within a cabinet | `EquipmentDefinition` (sub-component) |
| Frame | A structural/mounting assembly | `EquipmentDefinition` (frame-category) |
| Protection Relay | A protection device instance | `EquipmentDefinition` (relay-category) |
| Function | A protection or control logic function | Extraction Level 6 concept |
| Document | A source document | Document Repository record (§3) |
| Page | A specific page within a document | Belongs to a Document |

Every node type traces back to a Canonical Domain concept it instantiates
— this is the "Projects instantiate the domain" relationship made
concrete in the graph itself, not just asserted in prose.

### Edge concepts

| Edge type | Meaning |
|---|---|
| `contains` | A Cabinet contains a Terminal Block; a Frame contains Equipment. |
| `connects_to` | Two Equipment items are electrically connected (directly or via intermediate equipment). |
| `feeds` | A directional power or signal flow from one Equipment/Signal to another. |
| `terminates_at` | A Cable terminates at a specific Terminal Block. |
| `protects` | A Protection Relay/Function protects a piece of Equipment. |
| `measures` | An instrument transformer or sensor measures a quantity on a piece of Equipment. |
| `documented_in` | Any node is supported by a Document, at a specific Page — the traceability edge every other edge and node ultimately depends on (§9). |
| `part_of` | A component is part of a larger equipment assembly. |

Every node and every edge carries the same mandatory metadata the
Canonical Knowledge Protocol requires of a fact (§4 of that document, and
§9 below): source document, page, confidence, reviewer, review date, and
canonical (project) version. A graph element without this metadata is not
a valid element — the graph's integrity *is* its traceability.

### Relationship to the existing implementation

The existing `ProjectEntity`/`EntityRelation` model already expresses most
of this shape (a typed, per-project entity/relation store with a
confidence field). Two conceptual gaps this architecture identifies:

1. **Missing review-state discipline.** `EntityRelation.confidence` is a
   bare float with no accompanying review state, reviewer, or version —
   the Canonical Knowledge Protocol's `RAW/UNDER_REVIEW/APPROVED/
   REJECTED/SUPERSEDED` state machine has no equivalent today. This is the
   central gap §6 above exists to close.
2. **Missing node types.** The existing `EntityType` enum has no explicit
   Terminal Block or Frame concept — both are required by this task and
   both are common enough in functional schematics (per this session's own
   prior extraction-methodology work) to warrant first-class node types,
   not an "other" catch-all.

Neither gap requires a redesign of the existing model's *shape* — both are
additive extensions, which is exactly what §10's scalability requirement
demands.

---

## 8. Semantic Query Engine

User questions are answered by querying the Project Knowledge Graph, never
by asking an LLM to recall or reason about the substation from memory.

### Workflow

```
Interpret question
      ↓
Identify Project
      ↓
Query Project Knowledge Graph
      ↓
Collect supporting documents
      ↓
Generate answer
```

### Worked example

*"Inside project CP Pippo, find every cable leaving cabinet DQ1910 and
arriving at frame DQ7500."*

1. **Interpret question.** The LLM parses the natural-language question
   into a structured query intent: entity type `Cable`, source constraint
   `Cabinet = DQ1910`, destination constraint `Frame = DQ7500`. This step
   produces a query, not an answer — the LLM's output here is a request to
   the graph, and nothing it produces at this step is shown to the user as
   fact.
2. **Identify Project.** "CP Pippo" is resolved to a specific Project
   record (by name or code) — every subsequent step operates within that
   Project's boundary alone. A query can never leak across Projects; this
   is the same `project_id` boundary described in §2.
3. **Query Project Knowledge Graph.** The structured intent becomes a
   graph traversal: find `Cable` nodes with a `terminates_at` edge to
   Cabinet `DQ1910` and a `terminates_at` edge to Frame `DQ7500` (or an
   equivalent multi-hop path through intermediate equipment, per the
   `connects_to`/`terminates_at` edges recorded during extraction, §6, §7).
   This step returns **data**: a set of graph nodes and edges, each
   already carrying its own traceability metadata.
4. **Collect supporting documents.** For every returned node and edge, the
   `documented_in` edges are resolved to their source documents and pages
   — the exact drawings and cable schedules that support the answer.
5. **Generate answer.** The LLM composes a natural-language response
   **strictly from the data returned in steps 3–4.** It does not add, is
   not permitted to add, and is architecturally prevented from adding any
   cable, cabinet, or fact that was not present in the retrieved subgraph.
   If the graph returns zero results, the correct answer is "no such
   record exists in this project's knowledge," never a plausible-sounding
   guess.

### Why the LLM cannot invent facts

This is an architectural guarantee, not a prompting discipline. The
LLM only ever operates in two roles in this workflow: translating a
question into a structured query (step 1), and translating structured,
already-sourced results into prose (step 5). At no point does the LLM
have an opportunity to assert a fact that did not already exist, with its
own citation, in the Project Knowledge Graph before the question was
asked. This mirrors `CLAUDE.md` §3's "AI as a Service" principle exactly:
AI is an adapter behind a domain-owned interface, never a hard dependency
of the domain's truth — and it reuses the *existing* `AIProvider` port
(`app/services/ai/base.py`) rather than introducing a second, parallel AI
integration surface, so the Semantic Query Engine's model is swappable the
same way the extraction pipeline's already is (§10).

---

## 9. Traceability

Every answer the AI Assistant produces must reference:

- **Project** — which installation this answer is about.
- **Document** — the specific source document.
- **Drawing** — the drawing/document number as printed on its own title
  block.
- **Page** — the page (the document's own internal numbering, per the
  Canonical Knowledge Protocol §4).
- **Revision** — which revision of the document the fact came from.
- **Confidence** — the tier the fact was assigned (100/90/70%, per the
  Canonical Knowledge Protocol §5), never silently dropped when a fact
  is surfaced through the Semantic Query Engine.

This is not a new schema — it is the Canonical Knowledge Protocol's
Mandatory Metadata (§4 of that document) with one addition: **Project**,
which scopes every other field the same way `project_id` already scopes
every row in the existing `Document` and `ProjectEntity` tables. A fact
that cannot answer all six of these, on demand, is not eligible to be
surfaced as an answer — it stays in the Engineering Index or in
`UNDER_REVIEW`, never in a response to a user.

---

## 10. Scalability

The architecture must support thousands of projects, millions of extracted
facts, future document types, future AI models, and future engineering
disciplines, without architectural redesign. Each requirement is satisfied
by a specific design choice already made above, not by aspiration:

| Requirement | How this architecture satisfies it |
|---|---|
| **Thousands of projects** | Project is a hard multi-tenancy boundary (§2) already implemented as a `project_id` foreign key. Nothing in Document Classification, the Engineering Index, or the Knowledge Graph's conceptual model is project-specific — the boundary is data, not code. |
| **Millions of extracted facts** | The Engineering Index/Knowledge Graph split (§5) means the expensive, review-gated path (Knowledge Graph) only ever holds approved facts, while the cheap, high-volume path (Engineering Index) absorbs raw extraction volume without polluting query-time trust. Facts are append-only and versioned (§6, §9, per the Canonical Knowledge Protocol §9) — growth never requires destructive migration of historical facts. |
| **Future document types** | Document Classification (§4) is a governed but open taxonomy, not a fixed list baked into extraction logic — a new document type is a new classification value plus, if needed, a new extraction prompt (`knowledge/extraction/prompts/`), never a change to the Classification → Indexing → Extraction pipeline shape itself. |
| **Future AI models** | Every AI touchpoint (classification, extraction, query interpretation, answer generation) sits behind the same `AIProvider` port pattern already established in `app/services/ai/base.py` — a new model or provider is a new adapter, never a change to a domain-facing interface, per `CLAUDE.md` §3's "AI as a Service." |
| **Future engineering disciplines** | A new discipline (data center, industrial plant) means extending the Canonical Domain with new `EquipmentDefinition`/`AttributeDefinition` concepts, per the existing ontology reference pattern (`CLAUDE.md` §4.3) — Document Classification, the Engineering Index, the Knowledge Graph's node/edge concepts, and the Semantic Query Engine are all already discipline-neutral (§2); they gain new *content*, never new *shape*. |

---

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                        CANONICAL DOMAIN                             │
│   Equipment Definitions · Attribute Definitions ·                   │
│   Relationship Vocabulary · Domain Constraints                      │
│         (app/domain/ontology/**, one instance, all projects)        │
└───────────────────────────────────────┬─────────────────────────────┘
                                          │ instantiated by
                                          │
      (governed throughout by the CANONICAL KNOWLEDGE PROTOCOL:
       Extraction Levels 0-8 · Review States · Confidence Policy ·
       Canonicalization Rules — methodology, not vocabulary)
                                          ▼
┌───────────────────────────────────────────────────────────────────┐
│  PROJECT  (id, code, customer, EPC, location, status — existing)    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DOCUMENT REPOSITORY (PDF, Excel, DWG, Images, Manuals, ...)  │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                              ▼                                      │
│                 DOCUMENT CLASSIFICATION                             │
│      (Functional Diagram / Cable List / Protection Logic / ...)     │
│                              ▼                                      │
│                    DOCUMENT INDEXING                                │
│         → ENGINEERING INDEX (fast, unreviewed, per-document)        │
│                              ▼                                      │
│                  KNOWLEDGE EXTRACTION                               │
│   Raw Extraction → Engineering Review → Project Canonicalization    │
│         (governed entirely by the Canonical Knowledge Protocol)     │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           PROJECT KNOWLEDGE GRAPH (reviewed, versioned)       │   │
│  │  Equipment · Cables · Signals · Cabinets · Terminal Blocks ·  │   │
│  │  Frames · Protection Relays · Functions · Documents · Pages   │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                               ▼
                  SEMANTIC QUERY ENGINE
   Interpret → Identify Project → Query Graph → Collect Docs → Answer
                               ▼
                        AI ASSISTANT
        (always cites Project · Document · Drawing · Page ·
                     Revision · Confidence)
```

---

## Component Responsibilities

| Component | Responsibility | Existing code | Status |
|---|---|---|---|
| Canonical Domain | Defines what *can* exist, for every project | `app/domain/ontology/**` | Implemented |
| Project | Identity, boundary, business metadata, and record lifecycle for one installation | `domain/project/**`, `models/project.py`, `services/project_service.py`, `routers/projects.py` | Implemented — `DRAFT`/`ACTIVE`/`ARCHIVED`/`DELETED` lifecycle, soft delete, canonical domain version binding (see Milestone 8 recommendations below) |
| Document Repository | Stores uploaded files, scoped to a Project or the Canonical Library | `models/document.py`, `routers/documents.py`, `domain/project/project_document_scope.py` | Implemented — explicit `PROJECT`/`CANONICAL_LIBRARY` scope (ADR-0005), enforced at upload |
| Document Classification | Assigns a governed document type before extraction | `Document.category` field exists | **Gap — field exists, nothing populates it** |
| Engineering Index | Fast, unreviewed inventory of document mentions | — | **Gap — does not exist** |
| Knowledge Extraction | Runs the Canonical Knowledge Protocol's lifecycle, scoped to a Project | `services/ai/*` (extraction working; review missing) | **Partial — extraction exists, review stage is missing** |
| Project Knowledge Graph | Reviewed, versioned, queryable model of the installation | `models/knowledge_graph.py`, `services/knowledge_graph.py` | **Partial — storage/query exist; review-state and versioning fields are missing** |
| Semantic Query Engine | Answers questions by querying the graph, never by guessing | `routers/knowledge_graph.py` (query layer); interpret/generate steps not yet built | **Partial — query layer exists; NL interpretation/answer generation do not** |
| AI Assistant | User-facing presentation of sourced, traceable answers | — | **Gap — does not exist** |

---

## Data Flow Summary

1. A Project is created, bound to the current Canonical Domain version.
2. Documents are uploaded into that Project's Document Repository.
3. Each document is classified (document type assigned, traceable).
4. Each document is indexed (Engineering Index populated — fast, raw,
   unreviewed candidate mentions).
5. Each document, per applicable extraction level, goes through Raw
   Extraction → Engineering Review, governed entirely by the Canonical
   Knowledge Protocol, scoped to this Project.
6. Approved facts are canonicalized *at the project level*, versioned, and
   only then become nodes and edges in the Project Knowledge Graph.
7. A user asks a natural-language question; the Semantic Query Engine
   resolves the Project, queries the graph, and collects the supporting
   documents for every result.
8. The AI Assistant presents the answer, always with Project, Document,
   Drawing, Page, Revision, and Confidence attached.
9. Nothing in steps 3–8 ever writes to the Canonical Domain. The only
   path that changes the Canonical Domain is the separate, human-governed
   ontology-authoring process `CLAUDE.md` §7 already defines.

---

## Recommendations for Project Creation Workflow (Milestone 8)

The `Project` persistence model, schema, and CRUD router already exist and
are solid — Milestone 8 is not "build a Project entity," it is "make
Project creation the trigger that correctly provisions everything this
architecture assumes exists beneath a Project." Concretely:

1. **Bind a Canonical Domain version at creation time.** *Implemented —
   Project Lifecycle foundation milestone.* Every `Project` carries a
   `canonical_domain_version` field (`app.domain.project.project_models`),
   defaulting to the documented sentinel `UNVERSIONED_CANONICAL_DOMAIN =
   "unversioned"`. This is the binding *point*, not the versioning
   *scheme*: how `app/domain/ontology/**` itself should be versioned
   remains an open question, tracked in
   `ARCHITECTURE_FREEZE_V1_CHECKLIST.md` item 7.
2. **Replace the nullable `project_id` with an explicit document scope.**
   *Implemented — Project Lifecycle foundation milestone.* ADR-0005 is
   `Accepted`; `documents.scope`
   (`app.domain.project.project_document_scope.DocumentScope`) is now the
   explicit `PROJECT`/`CANONICAL_LIBRARY` value, enforced at
   `POST /documents/upload`: a `PROJECT`-scoped document requires a
   Project reference, a `CANONICAL_LIBRARY`-scoped document rejects one.
3. **Treat project `code` as the stable external identifier.**
   *Implemented — Project Lifecycle foundation milestone.* The domain
   `Project.traceability_reference` property returns `self.code`,
   formalizing this as the identifier future traceability records cite.
4. **Provision empty scopes, not empty tables.** *Implemented, to the
   extent those scopes exist to provision — Project Lifecycle foundation
   milestone.* `CreateProject` provisions the Project record itself, which
   is the boundary key (`project.id` / `project.code`) the Document
   Repository already writes against and the future Engineering Index and
   Project Knowledge Graph will write against. No extraction, indexing,
   AI, or background job runs at creation. The Engineering Index and
   Project Knowledge Graph *components* themselves remain unbuilt (see
   `ARCHITECTURE_FREEZE_V1_CHECKLIST.md` item 4) — there is nothing yet
   for their "scope" to be beyond this shared key.
5. **Decide the fate of substation-specific fields on generalization.**
   `voltage_level` is fine to keep as-is today (§2) — but Milestone 8
   should explicitly decide, and record the decision (an ADR under
   `docs/architecture/adr/`, the convention established alongside
   Architecture Freeze v1.0 — see [`adr/README.md`](adr/README.md)), on
   whether discipline-specific Project fields belong on the core `Project`
   record or in a discipline-specific extension — before a second
   discipline makes that decision urgent instead of optional.
6. **Do not couple Project creation to extraction.** Creating a Project
   must remain a fast, synchronous, low-risk operation, exactly as it is
   today — Document Classification, Indexing, and Extraction are separate,
   asynchronous stages triggered by upload, never by creation.
