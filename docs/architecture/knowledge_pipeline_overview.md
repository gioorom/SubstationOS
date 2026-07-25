# Knowledge Pipeline Overview

**Status:** As-built reference, established by Milestone 12 (Knowledge
Platform Hardening), extended by Milestone 13 (Structured Retrieval
Foundation). Describes the governed knowledge pipeline as it exists
today — not the product vision (`project_intelligence_architecture.md`
describes vision and roadmap; this document describes what is actually
implemented, tested, and running). Update this document when a stage's
real behavior changes; it is not an ADR and carries no historical
Context/Decision record of its own.

## The pipeline, stage by stage

```
Documents → Engineering Index → Proposed Claims → Review Workflow →
Canonicalization → Graph Builder → Project Knowledge Graph → Graph Query →
Structured Retrieval
```

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

## Required conceptual distinction

```
CanonicalFact = normalized approved engineering assertion
GraphOperationBatch = deterministic mutation plan
GraphExecution = audited application of a mutation plan
Project Knowledge Graph = current project-scoped graph state
Graph Query = deterministic read model
Structured Retrieval = deterministic, structured-criteria ranking layer over Graph Query
Semantic Retrieval = future retrieval and ranking layer
AI Assistant = future consumer, not owner, of engineering truth
```

Semantic Retrieval and the AI Assistant are **not implemented**. No
code in this repository performs embedding, vector search, semantic
ranking, or natural-language query interpretation today — every read
in Graph Query is a deterministic, exact query (by id, by type, by
attribute presence, by 1-hop adjacency), and Structured Retrieval
(Milestone 13) adds only deterministic, structured-criteria matching
and a fixed, documented scoring policy on top of it - still no
free-text question, no NL intent detection, no AI provider call (see
[structured_retrieval.md](structured_retrieval.md),
[ADR-0010](adr/0010-structured-retrieval-foundation.md)). Describing
Semantic Retrieval or the AI Assistant as existing would misrepresent
the system; they are named here only to mark where a future milestone
(Context Builder, then the AI Assistant, per the Product Development
Plan) will attach, and to make clear that when they do arrive, they
consume Structured Retrieval's deterministic output — they do not gain
their own path to engineering truth.

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
```

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
