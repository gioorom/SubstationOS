# Governed Knowledge Graph (EPIC 31)

> **Tables:** `governed_graph_nodes`, `governed_graph_edges`,
> `governed_graph_generations`
> **Rule:** the graph is a **projection**. It is never the source of
> truth, and it may always be rebuilt.

---

## 1. Philosophy

This is not a generic property graph, a document index, a semantic search
engine or an LLM memory. It is the **governed engineering knowledge
layer**: the query model over what an engineer has approved.

```
Document → Pipeline → Semantic Statement → Human Review → Knowledge Graph
```

Three properties define it, and everything else follows from them:

| | |
|---|---|
| **Derived** | Every node and edge is computed from a semantic statement and its current review. Nothing originates here. |
| **Rebuildable** | Drop it, rebuild it, and the content is identical. That is asserted by a test, not promised. |
| **Explainable** | Every node and every edge carries full provenance, and cannot be constructed without it. |

The pipeline stays the producer of engineering knowledge. Human Review
stays the record of engineering judgement. The graph is what those two
imply, made queryable.

## 2. The graph inventory, after EPIC 31.4

**There is one.** The repository held three graph implementations; EPIC
31.1 retired the first, EPIC 31.4 retired the second, and the third is
this one.

| | Source lineage | Status |
|---|---|---|
| ~~`knowledge_graph.py` + `project_entities` / `entity_relations`~~ | AI extraction, written straight from upload | **Retired, EPIC 31.1.** Code deleted, tables dropped by migration `e28b91f4c073`. See [ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md). |
| ~~`graph_builder` + `project_knowledge_graph` + `graph_query` + legacy `structured_retrieval`~~ | Canonical Facts, from legacy-workflow claims | **Retired, EPIC 31.4.** 20 routes withdrawn, ~60 modules deleted, seven tables dropped by migration `f4a90c27b615`. See [ADR-0028](adr/0028-retire-the-canonical-facts-graph.md). |
| **`governed_knowledge_graph`** | Semantic statements + Human Review | **The only runtime engineering knowledge graph.** Asserted structurally: `graph_contexts == ["governed_knowledge_graph"]`. |

So:

```
Queryable engineering graph knowledge  =  Governed Knowledge Graph
```

### What was **not** retired, and why it is not a second graph

`canonical_facts`, `proposed_claims`, `review_candidates` and
`review_history_events` **survive**, with their own routes and their own
tables.

They hold **human-authored records**: a claim an engineer wrote, the
candidate it became, the approval somebody gave it in the legacy
`review_workflow`, and that review's history. They were the *input* the
retired projection was computed from - not the projection.

The invariant this section states is about **graph-shaped queryable
engineering knowledge projections**, not about every relational table
that relates two things. By that definition none of the following is a
graph, and each is retained:

| Not a graph | Why |
|---|---|
| `engineering_facts`, `engineering_semantics` | Pipeline artefacts. A fact relates two entities, but nothing queries them as a graph and no projection is built from them. |
| `human_review`, `audit_events` | Records of judgement and of action. |
| `canonical_facts`, `proposed_claims`, `review_candidates` | Human-authored claims and the legacy review history over them. |

Deleting them would destroy engineering and audit information nothing
else records. Retiring a projection is not a reason to delete its
inputs.

### What the two retirements ended

**EPIC 31.1.** `ingest_document` wrote LLM-extracted entities into the
queryable graph on **every upload** - no reviewer, no review date, no
provenance beyond a filename, and a bare `confidence` float as the only
trust signal.
[ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md) recorded
at Architecture Freeze v1.0 that this must not happen and that it was
happening anyway; [ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md)
quarantined it. EPIC 31 built the replacement; EPIC 31.1 deleted the
original, together with `services/entity_extractor.py`,
`services/topology/**` and `services/ai/**`.

**EPIC 31.4.** The Canonical Facts graph was a projection *computed
from* approved claims: `graph_builder` turned them into operations, an
execution wrote nodes and relationships carrying JSON property bags, and
legacy Structured Retrieval matched on those bags. Its governance came
from the legacy claim-review workflow over hand-entered claims - not
from deterministic interpretation of a document that an engineer then
approved.

It survived three milestones for reasons that were true at the time:

| Milestone | Why it stayed |
|---|---|
| 31.1 | The Engineering Engine read it. Removing a live retrieval substrate to win a headline count would have broken six milestones of functionality. |
| 31.2 | The engine stopped reading it, but four route groups still served it and one compatibility adapter still spoke its vocabulary. |
| 31.3 | The adapter went. The routes remained - a product decision, not an engineering one. |

EPIC 31.4 took that decision. The audit re-enumerated the live route
table rather than trusting the earlier count and found **20 routes, not
15**: one router served eight, six of them under
`/projects/{id}/knowledge-graph/*` - one path prefix away from this
graph's own `/knowledge-graph/*`. That near-collision is gone with them.

**ADR-0004 now has nothing behind it.** A claim approved in the legacy
workflow reaches no queryable graph at all - not "a different graph
disagrees", but "there is nowhere else to ask". A test asserts exactly
that.

**Ingestion still writes no graph.** Uploading a document stores,
identifies and canonicalises it. Knowledge enters the graph only through
an explicit, capability-gated promotion.

## 3. What the graph may contain

**Two node kinds and one edge kind.** That is not a placeholder - it is
exactly what governed semantics produces.

| Node kind | Promoted from |
|---|---|
| `engineering_asset` | an `equipment_designation` entity |
| `engineering_quantity` | an `engineering_quantity` entity |

| Edge kind | Promoted from |
|---|---|
| `has_rated_power` | a `has_rated_power` semantic statement |

### Why not Voltage, Protection, Connection, Function, Location

The EPIC listed those as candidate concepts and then constrained them:
*"Only introduce concepts that already exist in governed semantics. Do
not invent engineering ontology."* The second instruction decides the
first.

| Concept | What it would need first |
|---|---|
| **Voltage** | A semantic rule. Voltage *evidence* exists and `engineering_semantics` deliberately refuses to interpret it: an associated voltage may be rated, test, insulation or busbar voltage, and the association does not say which. A `Voltage` node would assert a meaning no rule has assigned. |
| **Protection** | An evidence type, an entity type and a statement type. None exists. |
| **Connection** | A topology statement type. `HAS_ASSOCIATED_QUANTITY` is a same-line association, not a connection. |
| **Function** | A classification vocabulary and a rule that assigns it. The entity context refuses to classify for the same reason. |
| **Location** | Source *locations* are provenance (page, line, span), not engineering knowledge. A substation-location concept has no upstream at all. |

Each becomes promotable the day a semantic rule produces it: one member
in `graph_vocabulary` plus one mapping entry. Adding them now would be
node kinds no promotion can create, no query can return and no test can
cover.

**The graph also holds no `Transformer`, `Breaker` or `Cable`.** Deciding
that `TR1` names a transformer is a classification, and the entity
context refuses to make it. The graph inherits that refusal: it holds
what the documents *designate*, never what the equipment *is*.

## 4. Identity

**Derived from governed artefacts, never from a display label.**

```
node_id = sha256("substationos/governed-graph/node/v1" | kind | entity_key)
edge_id = sha256("substationos/governed-graph/edge/v1" | kind | statement_key)
```

Consequences, all of them deliberate:

- Promoting the same artefact twice produces the **same** id, so
  promotion is idempotent and a rebuild reproduces the graph exactly.
  Both ids are `UNIQUE` in the schema, so duplicate prevention is a
  constraint rather than a convention.
- An artefact re-derived under different rules gets a **different** id,
  so knowledge from two rule versions never silently merges.
- A label change re-identifies nothing.

### The stated limit: no cross-document entity resolution

`TR1` in document A and `TR1` in document B have different entity keys,
so they are **two nodes**. That is correct, and it is a limit rather than
a bug: deciding they are the same transformer is entity resolution across
documents, which no governed rule performs. Merging them here would be
exactly the label-matching the identity model exists to refuse - and it
would silently merge two different transformers that happen to share a
name in two drawings.

An upstream milestone would have to produce a governed cross-document
identity first. The graph would then promote *that*, unchanged in
principle.

## 5. Promotion

**One rule admits knowledge:**

```
current review decision == APPROVED
  AND applicability == APPLIES
  AND the statement type has a governed edge kind
  AND both endpoint entities have governed node kinds
      ↓
   PROMOTE
```

Full detail, refusal by refusal, in [promotion_rules.md](promotion_rules.md).

Two operations, **one rule**:

- **`promote_statement` / `promote_document`** - incremental. Visits what
  a review or a re-run could have changed and reconciles it.
- **`rebuild`** - recomputes the whole projection.

Both call `promotion_rules.evaluate`, so incremental and full can never
disagree about what is promotable. That divergence is the usual failure
mode of an incremental projection, and an architecture test asserts there
is only one definition.

Reconciliation runs in **both directions**: a document-level promotion
visits the statements that exist *and* the edges the graph holds for
statements that no longer do. Visiting only the first would leave
knowledge from a dropped statement sitting in the graph, current and
unvisited.

## 6. Lifecycle and revalidation

The EPIC offered four strategies - remove, disable, historical,
superseded - and required an explicit choice. **Historical is chosen**,
with a recorded reason.

```
                    promote
                       │
                       ▼
                    ACTIVE ──────────────── answers queries
                       │
     authorisation stops holding
                       │
                       ▼
                  HISTORICAL ─────────────  excluded from queries,
                       ▲                    still readable with provenance
                       │
                  re-approved
                       │
                    ACTIVE
```

| Rejected strategy | Why |
|---|---|
| Remove | Destroys the record of what the platform once asserted. An engineering system that silently forgets having claimed something cannot answer "what did the graph say when we ordered that transformer?". |
| Disable | A flag with no stated cause. Six months later nobody can tell a reversed judgement from a pipeline that outran it. |
| Superseded | Implies something replaced it. Usually nothing has: a rule version bump retires knowledge and produces no replacement until an engineer reviews the newly-derived statement. |

### Retirement reasons

| Reason | When |
|---|---|
| `review_reversed` | A later judgement is not an approval. |
| `requires_revalidation` | The pipeline was re-run under different bytes or rules; the reviewed statement is not in the new interpretation. |
| `orphaned` | No current interpretation to compare the review against. |
| `rebuild_reconciliation` | Found while recomputing the whole graph. |
| `no_remaining_relationships` | A node whose every edge retired. A node exists to be an endpoint of governed relationships; one with none represents nothing current, and leaving it active would let "every approved asset" return assets nothing is asserted about. |

**Never silently stale.** There is no path by which knowledge whose
review stopped being `APPROVED + APPLIES` remains `ACTIVE`. Re-approval
**reactivates the same edge** rather than creating a second one, so its
identity - and every reference to it - survives the round trip.

`REMOVED` exists for a rebuild that finds no promotable source for an
identity at all: `HISTORICAL` says *we know why this stopped being
current*, `REMOVED` says *nothing produces this any more*.

## 7. Rebuild, and what makes it exact

```
POST /knowledge-graph/rebuilds
```

Drops the graph and re-promotes every statement of every document. Safe
**only** because the graph is derived - and `clear()` exists on this
repository and on no other in the system, which an architecture test
asserts.

The projection is a **pure function of the statements and the reviews**.
Nothing in it depends on when promotion ran:

- identities are hashes of governed keys;
- `created_at` is taken from the **authorising review's** `recorded_at`,
  not from the clock. "When the graph learned this" is a fact about the
  knowledge, not about the run that wrote the row.

So two rebuilds over unchanged sources produce byte-identical content,
and a rebuild reports `unchanged` - the cheapest possible drift detector.
Three tests assert it, including one that never promotes incrementally at
all and lets the rebuild find the approval on its own.

## 8. Versioning: what "graph version" means

Versions live in **two places**, and the split is the point.

| Version | Where | Why |
|---|---|---|
| Generation number | `governed_graph_generations` | One per rebuild. Global. |
| Generation timestamp | same | When the rebuild ran. Global. |
| Promotion contract version | same | Which promotion rules admitted the knowledge. Global. |
| Semantic rule id + version | **each edge's provenance** | Differs per object. |
| Resolution / fact / semantic policy versions | each object's provenance | Differs per object. |
| Content checksum | each object's provenance | One graph spans many documents. |

Putting the per-object versions on the generation would record a single
value for something that genuinely varies, which is how a version field
becomes a lie. "Which rule versions is this graph built from?" is a query
over provenance, and it can honestly return several.

**Incremental promotions create no generation.** A generation says "this
is the projection as recomputed from scratch, under these rules";
promoting one statement recomputes nothing.

## 9. Provenance

Mandatory on every node and every edge, enforced at construction and by
`nullable=False` columns. An object whose origin cannot be stated is
**refused, not stored** - a missing answer is visibly missing, whereas an
untraceable one looks exactly like a good one.

Recorded: statement key, document, checksum, review id, reviewer, review
timestamp, rule id and version, contract version, the three policy
versions, support fingerprint, project.

**Not recorded:** the statement, the facts, the entities, the evidence,
or their text. The graph is a projection; the artefacts stay in the
pipeline, which remains their single account.

There is also **no confidence, score or weight** anywhere. Knowledge is
in the graph because an engineer approved it. A number expressing how
much to trust it would reintroduce exactly the ungoverned trust signal
ADR-0004 rejected, and an architecture test fails on such a column.

## 10. Queries

Resource-oriented REST. **No Cypher, no GraphQL, no SPARQL** - a governed
graph whose whole value is that every answer is explainable should not
first ship a way to ask questions whose answers nobody planned. A test
asserts no such path exists.

| Engineering question | Endpoint |
|---|---|
| Find an asset by designation | `GET /knowledge-graph/nodes?kind=engineering_asset&search=TR1` |
| Find its rated power | `GET /knowledge-graph/nodes/{node_id}` - relationships come with the node |
| Find upstream / downstream | the same, via `direction` on each relationship |
| All approved assets | `GET /knowledge-graph/nodes?kind=engineering_asset` |
| All governed relationships | `GET /knowledge-graph/edges` |
| Provenance / review | on every node and edge; `GET /knowledge-graph/edges/{edge_id}` for one |
| What did the Engineering Engine retrieve, and why? | `GET /projects/{id}/governed-retrieval/assets?designation=TR1` - see [governed_structured_retrieval.md](governed_structured_retrieval.md) |
| Is this statement promoted? | `GET /documents/{id}/engineering-semantics/{key}/promotion` |

Queries return **current knowledge by default**; `include_historical=true`
asks for what the graph used to assert.

`search` matches the governed label or normalized value - a substring
match over stored pipeline output. It is not a similarity search and it
never decides two nodes are the same thing.

## 11. Security

- Reading the graph needs `use_engineering_platform`.
- Promoting and rebuilding need **`promote_engineering_knowledge`**, a
  new capability. Separate from `record_engineering_review` on purpose:
  passing a judgement and publishing its consequence into the query model
  are different acts, and an installation may well want the second
  narrower.
- Every route is authenticated; the deny-by-default sweep covers them.
- Two audit actions: `knowledge_promoted`, `knowledge_graph_rebuilt`. A
  promotion that reconciled nothing is **not** audited - most statements
  are unreviewed most of the time, and an entry per no-op run would bury
  the ones that matter.

**Project visibility is filtering, not enforcement.** `project_id` is
carried on every node and edge and both list endpoints accept it, but
authorisation remains per-role: any authenticated engineer may read any
project's knowledge. That is inherited from EPIC 30.3 and is the same gap
the rest of the platform has - see §13.

## 12. Workspace integration

The Workspace remains the **inspection** interface. Selecting a semantic
statement now shows a graph panel beneath its review panel: whether the
statement is in the graph, its graph identity, the promotion metadata,
the provenance the graph recorded, and - when it is not promoted - **why
not**.

That last part is the point. "Not promoted" and "not promoted because
nobody has approved it" are different things to an engineer, so the panel
reports the refusal rather than the absence.

Retired knowledge is **marked, not hidden**: the panel says it was
retired and why, and the record stays readable.

## 13. Known limits

- **Two node kinds, one edge kind.** Governed semantics produces one
  statement type; see §3 for what each further concept needs first.
- **No cross-document entity resolution** - see §4.
- **Project visibility is not enforced** - see §11.
- **A rebuild is synchronous and unbounded.** It re-promotes every
  statement of every document in one request. Fine at current volumes; a
  background job is the answer when it stops being.
- **`_every_interpreted_document` reads every semantic set id.** Adequate
  now, and the first query to bound if the document count grows.
- **The graph is unversioned per project.** One generation covers the
  whole installation, so a rebuild triggered by one project's work
  renumbers globally.
- ~~Two graph implementations coexist.~~ **Closed by EPIC 31.4**: the
  Canonical Facts lineage is deleted and there is one runtime engineering
  graph. See §2 and
  [ADR-0028](adr/0028-retire-the-canonical-facts-graph.md).

---

## Files

| Concern | Location |
|---|---|
| Domain | `apps/backend/app/domain/governed_knowledge_graph/` |
| Persistence | `apps/backend/app/models/governed_knowledge_graph.py`, `app/infrastructure/governed_knowledge_graph/` |
| Promotion | `apps/backend/app/services/knowledge_promotion_service.py` |
| API | `apps/backend/app/routers/governed_knowledge_graph.py`, `app/schemas/governed_knowledge_graph.py` |
| Migration | `migrations/versions/d15a7c3e8b42_add_governed_knowledge_graph.py` |
| Frontend | `apps/frontend/components/workspace/GraphPanel.tsx`, `hooks/useStatementPromotion.ts`, `lib/contracts/graph.ts` |
| Tests | `tests/domain/test_governed_graph_domain.py`, `tests/api/test_governed_knowledge_graph_api.py`, `tests/architecture/test_governed_graph_boundaries.py`, `apps/frontend/tests/graph.test.tsx` |
