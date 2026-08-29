# ADR-0026: Governed Structured Retrieval

## Status

Accepted.

## Context

[ADR-0025](0025-retire-the-legacy-knowledge-graph.md) retired the
original AI-written Knowledge Graph and left one graph implementation
standing that it explicitly could not remove:

> `graph_builder`, `project_knowledge_graph` and `graph_query` stay.
> They are read at runtime by Structured Retrieval and therefore by the
> whole Engineering Engine answering stack. **They are not proven
> unused, so they are not removed.**

It also stated what closing that gap would require:

> `graph_query` returns nodes with **property bags**, and
> `structured_retrieval` matches on them. The governed graph
> deliberately has no property bags (ADR-0024), so the matching
> strategies need rewriting against typed fields. […] Retrieval quality
> would change, and that change needs measuring rather than assuming.

So the Engineering Engine — six milestones of working
question-answering — was reading a substrate fed from Proposed Claims
approved in the *legacy* review workflow, while the Governed Knowledge
Graph, fed from deterministic semantics that a named engineer approved,
answered only the Workspace and its own API.

That is the situation this milestone ends.

## Decision

### 1. Engineering retrieval consumes governed knowledge exclusively

A new bounded context, `governed_retrieval`, reads the Governed
Knowledge Graph and nothing else. The Engineering Engine's two retrieval
steps — and the two comparison retrieval steps — now run against it. The
engine's composition roots name a `GovernedKnowledgeReader` and no graph
repository at all, and an architecture test asserts it.

Nothing else about the engine changed: the workflow definitions, the
step types, the artifact keys, the planner and the executor were
untouched. A step still builds a retrieval plan and a step still executes
it.

**Why a bounded context rather than an application service over the
graph.** Retrieval has its own vocabulary — queries, match strategies,
ambiguity outcomes, diagnostics — and the graph must never learn any of
it, or a graph's content could come to depend on what somebody searched
for. And retrieval needs its own **read-only port**: the graph's
repository carries `upsert_node`, `upsert_edge`, `record_generation` and
`clear`, and a retrieval that depended on it would make "retrieval never
writes" a convention instead of a type.

### 2. Property bags were not carried forward, in either direction

The governed graph did not acquire a property bag to ease the migration,
and the retrieval path did not acquire one either. An architecture test
fails on `properties`, `attributes` or `payload` anywhere in the
governed retrieval path.

Forcing property bags into the governed graph would have undone
ADR-0024's central decision, and ADR-0025 named it in advance as the
answer that must not be given. The consequence is that two legacy
capabilities have **no governed counterpart at all** — attribute-bag
search, and lexical search over attribute keys and values — and this ADR
records that as a deliberate removal rather than a gap to be filled
later. The engineering question underneath attribute search ("what is
TR1's rated power?") is a governed relationship traversal, and it is a
better answer than a dictionary lookup: it names the statement, the
review and the reviewer.

### 3. Ranking is by match strategy, not by score

The legacy implementation summed documented weights — 100 for an exact
canonical id, 80 for a normalized identifier, 10 per lexical token. The
weights were documented and the total was deterministic, and it was
still a number attached to a piece of engineering knowledge.

Governed results carry a **match strategy** and a total order over
strategies. A strategy is a fact about the comparison that produced the
result; a weight is a quantity about the knowledge, and ADR-0004 and
ADR-0024 both refused to let the platform attach one. An architecture
test fails on `confidence`, `probability` or `relevance` in this context.

### 4. Retrieval does not recompute review eligibility

The promotion contract already guarantees that an `ACTIVE` graph object
was authorised by a review whose current decision is `APPROVED` and
whose applicability is `APPLIES`. Retrieval reads `state`, and that is
the whole of its governance logic.

The alternative — retrieval independently checking the review — would be
a second implementation of the same rule, and the day the two disagreed
neither would be authoritative. An architecture test asserts that no
module in this context mentions `ReviewDecision`, `ReviewApplicability`,
`APPROVED`, `APPLIES`, `human_review` or `promotion_rules`.

### 5. Ambiguity is preserved rather than resolved

`outcome` is `NO_MATCH`, `UNIQUE_MATCH` or `MULTIPLE_MATCHES`, computed
from the count **before** any limit is applied, so truncating a page can
never present several governed answers as one certain one.

`TR1` in two drawings is two governed nodes, and a designation query
returns both. Picking one — by document, by recency, by database
order — would be exactly the silent cross-document merge the identity
model exists to refuse, and in this domain a confident answer about the
wrong transformer is worse than an admitted ambiguity.

### 6. Cross-document entity resolution stays out of retrieval

It belongs upstream: an entity-resolution milestone would have to
produce a *governed* cross-document identity, and the graph would then
promote that, unchanged in principle. Doing it inside retrieval would
mean a query deciding two pieces of engineering knowledge are the same
thing — a judgement with no reviewer, no record and no way to disagree
with it.

### 7. Retrieval quality was measured before the substrate changed

Nine baseline scenarios and a shadow comparison run through the real
API, against real documents, real pipeline runs, real reviews and real
promotions — and, for the comparison, the real Canonical Facts lineage
built through Proposed Claims. Every difference is classified, and each
class is named by a test:

| Class | Count | What |
|---|---:|---|
| `EXPECTED_GOVERNANCE_DIFFERENCE` | 1 | Legacy answers from knowledge no engineer approved as a semantic statement |
| `NEW_CORRECT_BEHAVIOUR` | 1 | Governed results carry statement, review, reviewer and rule version; legacy carried a `GraphExecution` id and an always-empty `source_fact_ids` |
| `LEGACY_BEHAVIOUR_NOT_SUPPORTED` | 2 | Attribute-bag search; lexical matching over entity types and attribute values |
| `BUG` | 0 | No unexplained difference survived |

The zero is recorded by a test rather than left as a claim.

### 8. One temporary adapter, named and dated

`governed_context_projection.py` maps a governed retrieval outcome into
the `KnowledgeCandidate` vocabulary Context Builder, Prompt Builder and
Engineering Response already speak.

It is a compromise and is documented as one. Migrating retrieval **and**
its four downstream consumers in a single change would have made a
quality regression in any of them invisible — the one thing this
milestone was required not to do. The adapter is named, documented,
covered by its own tests, and carries an explicit retirement condition:
**delete it when Context Builder consumes `GovernedRetrievalResult`
directly.** An architecture test asserts it is the only module of its
kind, so it can be deleted rather than hunted for.

It invents no property bag, computes no confidence, and loses no
provenance: `KnowledgeCandidate.governed_statement_keys` was added so a
projected candidate names the governed statement that authorised it, and
Context Builder's missing-provenance warning now distinguishes "states
its origin one of two ways" from "states it neither way".

### 9. The Canonical Facts projection is **not** retired

The retirement gate has ten conditions. After this milestone:

| # | Condition | Status |
|---:|---|---|
| 1 | No production runtime caller depends on it | **fails** |
| 2 | The Engineering Engine uses governed retrieval | passes |
| 3 | Baseline scenarios pass | passes |
| 4 | All unexplained retrieval differences resolved | passes |
| 5 | No property-bag compatibility dependency remains | passes |
| 6 | No API depends on the legacy graph | **fails** |
| 7 | No frontend code depends on it | passes |
| 8 | No background service writes or reads it | passes |
| 9 | Architecture tests prove the dependency is gone | passes |
| 10 | Docs identify the governed graph as the sole runtime engineering knowledge graph | **fails** |

**The blocker is conditions 1, 6 and 10, and it is one blocker.** Four
route groups still serve the lineage:

```
POST /graph-builder/build/project/{id}       and its reads
POST /graph-executions/batches/{id}          and its reads
GET  /projects/{id}/graph/…                  Graph Query
POST /projects/{id}/structured-retrieval/…   legacy retrieval
```

They are served, documented and tested capabilities. Removing them is a
product decision about what the platform offers, not a cleanup that
follows from an engine change — and this milestone's own instruction was
to delete only what is proven unused. These are proven *used*, by their
own API.

**The objective condition that permits retirement:** those four route
groups are withdrawn. At that point nothing reads `graph_builder`,
`project_knowledge_graph` or `graph_query`, and the retirement is
mechanical — delete the contexts, their models, their schemas, their
services and their tests, and add a forward migration dropping
`project_graph_nodes`, `project_graph_relationships`, `graph_executions`,
`graph_execution_operation_results`, `graph_execution_fingerprints`,
`graph_operation_batches` and `graph_operations`. That migration is
**not** written now: writing a migration for tables a live route still
serves would be a trap for whoever runs it.

A second, smaller condition applies to `structured_retrieval` itself:
its `KnowledgeCandidate*` value objects still reference
`graph_builder`'s `GraphEntityId` and `GraphRelationshipType`, so
retiring `graph_builder` also requires the Context Builder migration in
§8. The two conditions are independent and can be met in either order.

`tests/architecture/test_graph_consolidation.py` now asserts the new
truth in both directions: the engine no longer reads the lineage, and
the lineage is still reachable through its own API. The day those routes
go, that test fails and says the lineage has become genuinely dead.

## Consequences

**Positive**

- **The Engineering Engine answers only from knowledge a named engineer
  approved.** Every reference in an engineering answer now carries a
  statement key, a review id, a reviewer, a rule version and a document.
- Ambiguity reaches the caller. "Two drawings designate a TR1" is
  reported rather than resolved by database order.
- Historical knowledge cannot answer a current question by accident;
  reading it is an explicit scope.
- Retrieval cannot write. Not by rule — by interface.
- Matching is explainable per result and reproducible across machines,
  because no fold depends on a database collation.

**Negative**

- **Two legacy capabilities are gone** (§2). An installation that relied
  on attribute-bag search has no governed replacement, and this ADR does
  not pretend otherwise.
- **The Engineering Engine now finds less**, in exactly the installations
  where knowledge was entered as Proposed Claims rather than derived from
  documents and reviewed. That is the intended behaviour of the
  architecture and the reason the difference is classified rather than
  fixed.
- One temporary adapter exists (§8), and with it a score-shaped ordering
  value that outlives the scoring policy it replaced. It goes when the
  adapter goes.
- Two graph implementations still exist (§9).

**Neutral**

- Designation folding is a Python-side scan of the scoped node set. At
  present the governed graph holds only what somebody approved, so the
  set is small; a benchmark records the number so the day that stops
  being true is visible.

## Rejected Alternatives

**Add a property bag to the governed graph so the legacy matching
strategies could be repointed.** Rejected outright. It would undo
ADR-0024's central decision, let a quantity acquire a designation, and
turn the governed graph into the generic property graph it exists not to
be. ADR-0025 named this as the answer that must not be given.

**Keep the legacy scoring weights so downstream ranking was unchanged.**
Rejected. The weights were the most defensible thing about the legacy
implementation and still produced a number attached to engineering
knowledge. The ordering they encoded is preserved as a documented
strategy precedence, which is the same information without the
misreading.

**Migrate Context Builder, Prompt Builder and Engineering Response in
this milestone too.** Rejected as unsafe rather than as too much work: a
change touching retrieval and its four consumers at once would make a
quality regression in any of them invisible, and this milestone's
critical success condition was that quality must not be silently
reduced. The seam is a single named adapter with a retirement condition
instead.

**Delete the Canonical Facts lineage anyway, since the engine no longer
reads it.** Rejected. Four route groups still serve it. Deleting a
served capability to achieve a headline count of one graph is exactly
what ADR-0025 refused to do a milestone earlier, and the reasoning has
not changed.

**Keep the legacy tables and quietly stop serving them.** Rejected for
the reason ADR-0025 gave: it leaves a queryable store with no owner and
no reader, which anybody with SQL access still finds and has no way to
know is ungoverned. Either the routes are a capability or they are not.

**Expose a general governed query API.** Rejected. One endpoint exists,
and it serves the one requirement product has: reading what the engine
retrieved and why. A general query surface would be a way to ask
questions nobody planned answers for, which is precisely what a graph
whose value is explainability must not ship first.

**Solve cross-document entity resolution inside retrieval to remove the
ambiguity.** Rejected — see §6. It would be a query making an
engineering judgement with no reviewer and no record.

## Related

- [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) — only
  reviewed facts may answer engineering questions. This milestone
  extends that from *the graph* to *the answering stack*.
- [ADR-0010](0010-structured-retrieval-foundation.md) — the legacy
  retrieval this replaces for the Engineering Engine. Still in force for
  its own API.
- [ADR-0024](0024-governed-knowledge-graph-as-projection.md) — the
  no-property-bag decision that made the rewrite necessary rather than
  optional.
- [ADR-0025](0025-retire-the-legacy-knowledge-graph.md) — retired the
  first graph and stated what retiring the second would require.
- `docs/architecture/governed_structured_retrieval.md` — the as-built
  reference.
