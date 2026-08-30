# Governed Structured Retrieval (EPIC 31.2)

> **Context:** `app/domain/governed_retrieval/**`,
> `app/infrastructure/governed_retrieval/**`,
> `app/services/governed_retrieval_service.py`
> **Rule:** retrieval **retrieves** knowledge. It does not create it,
> infer it, reinterpret it, or approve it.

---

## 1. What changed, and why it is not a cleanup

Until this milestone the Engineering Engine's retrieval read the
**Canonical Facts** graph projection:

```
Canonical Facts → graph_builder → project_knowledge_graph
                → GraphQueryRepository → Structured Retrieval
                → Engineering Engine
```

That substrate is fed from Proposed Claims approved in the *legacy*
review workflow, and its nodes carry a **property bag** — a
`dict[str, str]` of attribute names and values that Structured Retrieval
matched against. It is not the Governed Knowledge Graph, and knowledge
in it has never passed the governed Human Review.

The path is now:

```
Deterministic Pipeline
        ↓
Semantic Statements
        ↓
Governed Human Review
        ↓
Governed Knowledge Graph
        ↓
Governed Structured Retrieval
        ↓
Engineering Engine
```

The migration could not be a repoint. The governed graph deliberately
has **no property bag** ([ADR-0024](adr/0024-governed-knowledge-graph-as-projection.md)),
so every matching strategy had to be rewritten against typed governed
fields, and the retrieval quality that changed had to be measured rather
than assumed. [ADR-0026](adr/0026-governed-structured-retrieval.md)
records the decisions; §11 below records the measurement.

## 2. Where it sits

`governed_retrieval` is its **own bounded context**, not an application
service over the graph. Two reasons decided it:

- it has its own vocabulary — queries, match strategies, ambiguity
  outcomes, diagnostics — and the governed graph must never learn any of
  it. An architecture test asserts the graph imports nothing from here.
- it needs its own **read-only port**. The graph's own repository carries
  `upsert_node`, `upsert_edge`, `record_generation` and `clear`; a
  retrieval that depended on it would make "retrieval never writes" a
  convention rather than a type.

```
GovernedGraphRepository  ← promotion writes through this
GovernedKnowledgeReader  ← retrieval reads through this (no write method)
```

| Concern | Location |
|---|---|
| Vocabulary, queries, matching, assembly | `app/domain/governed_retrieval/` |
| Read port | `app/domain/governed_retrieval/governed_knowledge_reader.py` |
| Adapter | `app/infrastructure/governed_retrieval/sqlalchemy_governed_knowledge_reader.py` |
| Orchestration (the only I/O) | `app/services/governed_retrieval_service.py` |
| API | `app/routers/governed_retrieval.py`, `app/schemas/governed_retrieval.py` |
| Engine integration | `app/services/engineering_engine/governed_retrieval_step_handlers.py` |

## 3. The typed query model

Five queries. Each is a frozen dataclass with explicit fields, built
only through `GovernedRetrievalQueryFactory`, which enforces every
invariant at construction — so a query that exists is a query that may be
executed.

| Query | Engineering question |
|---|---|
| `AssetDesignationQuery` | "Which governed assets does this designation name?" |
| `AssetQuantityQuery` | "What quantities does governed knowledge assert about this asset?" |
| `RelationshipQuery` | "Which governed relationships exist, of this kind, in this scope?" |
| `DocumentKnowledgeQuery` | "What governed knowledge came out of this document?" |
| `GovernedIdentityQuery` | "What is this governed object, and where did it come from?" |

There is **no free-text field, no filter object, no operator and no
expression** anywhere on the contract. `GovernedIdentityQuery` is also
the provenance query: every result already carries its full provenance,
so asking for provenance *is* asking for the object by identity rather
than for a second, differently-shaped resource.

### What the legacy modes became

| Legacy `RetrievalMode` | Governed counterpart |
|---|---|
| `ENTITY_LOOKUP` | `GovernedIdentityQuery`, or `AssetDesignationQuery` when the caller has a designation rather than a governed id |
| `ENTITY_TYPE_SEARCH` | **Nothing.** The governed graph holds what a document *designates*, never what equipment *is* — deciding `TR1` is a transformer is a classification the entity context refuses to make |
| `ATTRIBUTE_SEARCH` | **Nothing.** There is no property bag to search. The engineering question underneath it ("what is TR1's rated power?") is `AssetQuantityQuery` |
| `RELATIONSHIP_SEARCH` | `RelationshipQuery` |
| `LEXICAL_SEARCH` | `AssetDesignationQuery`, narrowed to the two fields that actually name equipment |
| `COMBINED` | **Nothing.** Combining criterion kinds only made sense against a property bag |

§11 classifies each of these as a deliberate removal rather than a
regression, with a test naming the class.

## 4. Normalization

Three folds, in `governed_normalization.py`. All pure, all total, all
deterministic. **No stemming, no edit distance, no embeddings, no
similarity, no substring matching.**

| Fold | `"C-295"` becomes | Also matches |
|---|---|---|
| exact | `"C-295"` | — |
| `normalize_designation` | `"c-295"` | `" C-295 "`, `"c-295"` |
| `canonical_designation_key` | `"c295"` | `"C 295"`, `"c295"` |

`canonical_designation_key` reproduces the legacy
`lexical_matching.normalize_identifier` behaviour exactly, so the
capability an engineer relied on survives under a name that says what it
does. `GOVERNED_NORMALIZATION_VERSION` is echoed on every result's
diagnostics.

### Why folding happens in Python and not in SQL

The governed graph's own list endpoint offers `search` backed by
`ILIKE '%term%'`. Retrieval deliberately does **not** use it:

- its collation is a property of the database, so the same governed
  graph could answer differently on SQLite and PostgreSQL, and a
  deterministic contract cannot rest on that;
- a substring match cannot explain itself — `"T1"` inside `"QT10"` is a
  coincidence, not an identification.

The adapter therefore filters on **indexed, exact governed columns
only** (kind, state, project, document) and the fold is a domain rule.
The cost is one scan of the governed nodes in scope; §11 records the
measurement and the condition under which a normalized-designation index
becomes justified.

## 5. Matching, and why there is no score

Every result carries **exactly one** `GovernedMatchStrategy` — the
strongest one that held — plus the governed field that carried it and the
value that was compared. "Why did this match?" has one answer, and it is
the most specific true one.

| Rank | Strategy | Means |
|---:|---|---|
| 0 | `GOVERNED_IDENTITY` | The caller named the object's own id |
| 1 | `EXACT_DESIGNATION` | The governed label *is* the designation |
| 2 | `NORMALIZED_DESIGNATION` | Equal once case and whitespace are folded |
| 3 | `NORMALIZED_VALUE` | Equal to the value the **pipeline itself** normalized |
| 4 | `CANONICAL_DESIGNATION` | Equal only after separators are dropped |
| 5 | `RELATIONSHIP_TRAVERSAL` | Reached through a governed relationship |
| 6 | `EDGE_KIND` | Selected by governed relationship kind |
| 7 | `DOCUMENT_SCOPE` | Selected because its provenance names the document |

**Ranking is by strategy, not by score.** The legacy implementation
summed documented weights (100 for an exact canonical id, 80 for a
normalized identifier, 10 per lexical token…) and the number was still a
number: once results carry one, somebody eventually reads it as a measure
of how *true* the knowledge is. A strategy is a fact about the
comparison; a weight is a quantity about the knowledge, and the governed
graph has no place for the second (ADR-0004, ADR-0024).

Ranks 2 and 3 are a deliberate pair: the normalized *label* outranks the
normalized *value* because the label is what a drawing shows an engineer.

### Ordering

```
(strategy rank, primary label folded, secondary label folded, governed identity)
```

Total, and never dependent on insertion order, on a database's default
sort, or on a clock — the final component is a SHA-256 over governed
keys, so no two items compare equal.

## 6. The result model

```
GovernedRetrievalResult
├── outcome                NO_MATCH | UNIQUE_MATCH | MULTIPLE_MATCHES
├── items[]
│   ├── result_id          derived from governed identity alone
│   ├── kind               asset | quantity | relationship
│   ├── node               node id, kind, label, normalized value, unit
│   ├── relationship       edge id, kind, both endpoints resolved
│   ├── state              active | historical
│   ├── retirement_reason  why it stopped being current
│   ├── match              strategy, matched field, matched value, fold
│   └── provenance         mandatory - see §7
├── total_before_limit
├── applied_limit
└── diagnostics            see §9
```

`result_id` is composed from the result kind and the governed node/edge
ids — never a counter, a page position, a timestamp, a database row id or
a label. A quantity reached by traversal carries **both** the edge and
the node, because the same quantity node can be the object of two
different relationships and those are two engineering answers.

Everything else is referenced **by identity**: the statement, the facts,
the entities and the evidence stay in the pipeline, which remains their
single account.

## 7. Provenance

Mandatory, and structural: `GovernedRetrievalItem.provenance` has no
default and no `| None`, so an item that could not state where it came
from cannot be constructed. That mirrors the governed graph's own
`nullable=False` columns — provenance-less governed knowledge does not
exist upstream, so retrieval needs no runtime guard for a state the
platform cannot produce.

The chain an engineer can walk:

```
Retrieval result
      ↓ result_id
Governed node / edge
      ↓ statement_key
Semantic statement
      ↓ review_id
Current APPROVED review
      ↓ support_fingerprint
Support chain → Evidence → Canonical location → Original document
```

Every link addresses an artefact that already has its own endpoint. A
baseline test walks it: it takes the `statement_key` off a returned
result and asks
`GET /documents/{id}/engineering-semantics/{key}/promotion`, which
confirms the promotion.

## 8. Governance: retrieval implements none

The graph's promotion contract already guarantees that an `ACTIVE`
object was authorised by a review whose current decision is `APPROVED`
and whose applicability is `APPLIES`. Retrieval therefore reads
**`state`, and nothing else about governance**.

Recomputing eligibility here would create a second governance
implementation, and the day the two disagreed neither would be
authoritative. An architecture test asserts that no module in this
context mentions `ReviewDecision`, `ReviewApplicability`, `APPROVED`,
`APPLIES`, `human_review` or `promotion_rules`.

Proven end to end, against real reviews and real promotions:

| Review state | Retrievable? |
|---|---|
| `APPROVED` + `APPLIES` | **yes** |
| `REJECTED` | no |
| `NEEDS_INVESTIGATION` | no |
| `REQUIRES_REVALIDATION` | not as current knowledge |
| `ORPHANED` | not as current knowledge |
| graph object `HISTORICAL` | excluded from the default scope |
| graph object `REMOVED` | excluded from **every** scope |

## 9. Historical knowledge

```python
class RetrievalScope(str, Enum):
    CURRENT_ONLY = "current_only"                    # the default
    CURRENT_AND_HISTORICAL = "current_and_historical" # always explicit
```

`CURRENT_ONLY` is the default on every factory method and the **only**
scope the Engineering Engine uses — there is no engine request field that
could widen it. Historical knowledge is what the platform *used* to
assert; letting it quietly answer a current engineering question is the
silent staleness the whole lifecycle model exists to prevent.

The one exception is `GovernedIdentityQuery`, which defaults to
including historical objects: a caller who names an id already knows the
object exists, and answering "no such object" for one that is merely
retired would be a lie about the graph's contents. The result still
reports its `state`.

## 10. Ambiguity, and cross-document identity

`outcome` is computed from `total_before_limit`, **never** from the
returned page — so truncating a page can never turn several governed
answers into one apparently certain one.

`TR1` in document A and `TR1` in document B are two governed nodes
(`graph_identity`), so a designation query returns two items and
`MULTIPLE_MATCHES`. Retrieval does **not** merge them: deciding they are
the same transformer is cross-document entity resolution, which no
governed rule performs and which stays outside this bounded
responsibility. A quantity query with an ambiguous subject traverses
**every** resolved asset rather than picking one.

For a list-shaped query (`RelationshipQuery`, `DocumentKnowledgeQuery`)
`MULTIPLE_MATCHES` is the expected answer and says nothing about
ambiguity.

## 11. The quality baseline and the shadow comparison

`tests/api/test_governed_retrieval_baseline.py` runs entirely through
the real API: real documents, real pipeline runs, real reviews, real
promotions, and — for the comparison — the real Canonical Facts lineage
built through Proposed Claims.

**Nine baseline scenarios**, each stating its query, the identities it
expects, the provenance it expects, and the ordering where ordering is
contractual: asset by designation; designation matching under
typography; quantity for an asset; provenance on every result;
provenance walked back to the statement; no-match; two documents sharing
a label; project scope; deterministic ordering.

**Differences from legacy retrieval, each classified and each named by a
test:**

| Class | Difference |
|---|---|
| `EXPECTED_GOVERNANCE_DIFFERENCE` | Legacy answers from Canonical Facts that no engineer approved as a *semantic statement*. Governed retrieval does not. This is the purpose of the architecture |
| `NEW_CORRECT_BEHAVIOUR` | A legacy candidate's strongest provenance is a `GraphExecution` id and its `source_fact_ids` is always empty. A governed result names the statement, the review, the reviewer, the rule version and the document |
| `LEGACY_BEHAVIOUR_NOT_SUPPORTED` | Attribute-bag search has no governed counterpart — the graph has no attribute bag, and the engineering question underneath it is a relationship traversal |
| `LEGACY_BEHAVIOUR_NOT_SUPPORTED` | Lexical search no longer matches entity types, attribute keys and attribute values. It matches designations, which is what names equipment |

`BUG` has no test, because no unexplained difference survived: the three
that exist are two deliberate capability removals and one strict
provenance improvement. A test records that absence rather than leaving
it assumed.

### Performance

`scripts/benchmarks/graph_performance_benchmark.py` gained
`run_governed_retrieval_benchmarks`, measuring designation lookup,
quantity traversal, relationship lookup, document-scoped knowledge and
provenance-by-identity against a governed graph of the same size as the
Canonical Facts dataset the legacy retrieval benchmark uses. See
[performance_baseline.md](performance_baseline.md) for numbers and
methodology.

**No index was added.** `designation_lookup` filters by kind, state and
project in SQL — all indexed by
`ix_governed_graph_nodes_project_state` — and folds designations in
Python. Adding a normalized-designation column now would denormalize the
governed model ahead of a measured need; the benchmark is what makes the
day that changes visible rather than theoretical.

## 12. The Engineering Engine

The workflow definitions, the step types, the artifact keys, the planner
and the executor are **unchanged**. A step still builds a retrieval plan
and a step still executes it; only the substrate changed.

| Engine request field | Governed query |
|---|---|
| `retrieval_canonical_entity_id` (`"CABLE:C-295"`) | `AssetDesignationQuery("C-295")` — the `CABLE` prefix is a classification with no governed counterpart, so it is dropped rather than matched against something invented |
| `retrieval_lexical_terms` | one `AssetDesignationQuery` **per term**, so each keeps its own outcome and its own ambiguity |
| `retrieval_include_neighborhood` | traverse governed relationships from each resolved asset — a governed edge *is* the neighbourhood |
| `retrieval_entity_type`, `retrieval_attribute_name` | **nothing**, and the plan says so in `unsupported_criteria` rather than returning an empty result a caller would read as "there is no such equipment" |

**No fallback**: a configuration naming no designation retrieves nothing
and reports `NO_MATCH`. Broadening to "everything in the project" would
answer a question nobody asked, and in this domain a confident answer
about the wrong equipment is worse than an admitted gap.

### The temporary adapter is gone (EPIC 31.3)

EPIC 31.2 shipped one compatibility module,
`governed_context_projection.py`, which mapped a governed outcome into
the `KnowledgeCandidateCollection` Context Builder then accepted. It
existed so that retrieval and its downstream consumers could migrate
separately — doing both at once would have made a quality regression in
either invisible.

It carried an explicit retirement condition: *delete it when Context
Builder consumes `GovernedRetrievalResult` directly.* **EPIC 31.3 did
that, and deleted it.**

The engine now hands `GovernedRetrievalResult` objects straight to
Governed Context Assembly, so the governed identity, the match strategy,
the mandatory provenance and the per-query ambiguity all reach the
context without passing through a translation that could drop any of
them. Two architecture tests hold the line: the adapter file must not
exist, and no module anywhere may project governed results into the
candidate vocabulary.

See [governed_context_assembly.md](governed_context_assembly.md) and
[ADR-0027](adr/0027-governed-context-assembly.md).

## 13. API

```
GET /projects/{project_id}/governed-retrieval/assets
    ?designation=TR1&include_quantities=&include_historical=&limit=
```

**One endpoint, and it is the one the Engineering Engine uses.** The
requirement it serves is inspection: an engineer reading an engine answer
must be able to ask *what was retrieved and why*, and get exactly what
the engine got — same query, same matching, same ordering, same
provenance.

Everything browse-shaped is already a resource
(`/knowledge-graph/nodes`, `/knowledge-graph/edges`,
`/documents/{id}/engineering-semantics/{key}/promotion`), and
duplicating those here would be a second way to ask the same thing.

- **Authorization:** `use_engineering_platform`, the same capability
  `/knowledge-graph/nodes` requires — this endpoint reads the same rows.
- **No query language.** The only inputs are a designation, a scope and
  a limit. No Cypher, no GraphQL, no SPARQL, no filter object. A test
  asserts the router contains no `filters`, `where`, `expression`,
  `raw_query` or `dict[`.
- **No 404.** A designation the graph knows nothing about is a
  successful result whose outcome is `no_match`. Only a structurally
  invalid query answers `422`.

## 14. Observability

Every result carries deterministic diagnostics: query type, scope, the
fold applied, the strategies attempted, candidates examined, matched
count, returned count, ambiguity and no-match flags, the normalization
and matching policy versions, and the graph generation that answered.

Every field is a count, a version or a closed enum value. There is no
probabilistic quality score, and no document content, review comment or
reviewer prose is logged. `duration_seconds` is the one field that
varies run to run, and a test pins that nothing else may.

## 15. Security

Unchanged from EPIC 30.3, deliberately. Reading governed knowledge needs
`use_engineering_platform`; the endpoint reads exactly the rows
`/knowledge-graph/nodes` already serves, through a port with no write
method, so it opens no path that did not exist.

`project_id` on a query is **filtering, not enforcement** — the same
inherited gap the rest of the platform has
([security_architecture.md](security_architecture.md)). It did not block
this milestone: retrieval isolates a project's knowledge exactly as well
as the graph API it reads does, and no worse. Fixing it is a
platform-wide change to authorization, not a retrieval change.

## 16. Known limits

- **Three node kinds and two edge kinds**, because that is what governed
  semantics produces. Retrieval inherits the catalogue and invents
  nothing. `IS_LOCATED_IN` (EPIC 32.P1) is retrieved by the existing
  typed `RelationshipQuery`; no new query type was needed, and
  `GovernedResultKind` gained one member so a structural location can be
  reported as what it is.
- **No cross-document entity resolution** — see §10. Outside this
  bounded responsibility by design.
- **No attribute-bag search**, and no governed replacement for it. §11
  classifies it.
- **Designation folding is a scan** in the scoped node set — see §4 and
  §11.
- ~~One temporary adapter at the Context Builder seam~~ — **retired by EPIC 31.3**; see §12.
- **The Canonical Facts lineage still exists**, no longer read by the
  Engineering Engine but still served by its own routes. See
  [ADR-0026](adr/0026-governed-structured-retrieval.md) for the
  objective condition that permits its retirement, and
  [knowledge_graph.md](knowledge_graph.md) §2 for the inventory.

---

## Files

| Concern | Location |
|---|---|
| Domain | `apps/backend/app/domain/governed_retrieval/` |
| Read port | `.../governed_retrieval/governed_knowledge_reader.py` |
| Adapter | `apps/backend/app/infrastructure/governed_retrieval/` |
| Service | `apps/backend/app/services/governed_retrieval_service.py` |
| Engine steps | `apps/backend/app/services/engineering_engine/governed_retrieval_step_handlers.py` |
| Engine artifacts | `.../engineering_engine/governed_retrieval_artifacts.py` |
| API | `apps/backend/app/routers/governed_retrieval.py`, `app/schemas/governed_retrieval.py` |
| Domain tests | `tests/domain/test_governed_retrieval_domain.py` |
| Service tests | `tests/services/test_governed_retrieval_service.py` |
| Context assembly | `app/domain/context_builder/`, `docs/architecture/governed_context_assembly.md` |
| Adapter tests | `tests/infrastructure/test_sqlalchemy_governed_knowledge_reader.py` |
| Baseline, governance, shadow | `tests/api/test_governed_retrieval_baseline.py` |
| Architecture | `tests/architecture/test_governed_retrieval_boundaries.py` |
| Benchmarks | `scripts/benchmarks/graph_performance_benchmark.py` |
