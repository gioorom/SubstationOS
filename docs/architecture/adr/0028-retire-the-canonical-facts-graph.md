# ADR-0028: Retire the Canonical Facts graph

## Status

Accepted.

Completes the retirement [ADR-0025](0025-retire-the-legacy-knowledge-graph.md)
deferred, under the conditions
[ADR-0026](0026-governed-structured-retrieval.md) §9 and
[ADR-0027](0027-governed-context-assembly.md) set.

---

## A naming warning, first

Two different things in this repository are called "Canonical Facts", and
this ADR is about exactly one of them.

| Name | What it is | Disposition |
|---|---|---|
| **`canonical_facts` (the table)** | Human-authored engineering claims. An engineer wrote a Proposed Claim, another approved it in the legacy `review_workflow`, and Canonicalization normalised it into a fact row. **Source records.** | **Retained.** Its four routes still serve. |
| **The Canonical Facts *graph*** | A graph-shaped **projection computed from** those rows: `graph_builder` turned them into operations, `graph_executions` wrote nodes and relationships with JSON property bags, `graph_query` read them back, legacy `structured_retrieval` matched on them. | **Retired by this ADR.** |

Everything below concerns the second. Nothing an engineer typed is
deleted; what is deleted is the computed shape that was derived from it.

## Context

### What the projection was, and why it existed

Milestones 11.1 and 11.2 built it. At the time it was the only way to
ask an engineering question of a project: approved claims went in, a
queryable graph came out, and Milestone 13's Structured Retrieval
matched designations against the `properties` JSON bag on each node.
Six milestones of question-answering were built on that substrate.

It was never the graph
[ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) asked for -
its governance came from the legacy claim-review workflow, over
hand-entered claims, not from deterministic interpretation of a document
that an engineer then approved. But it was reviewed, and it worked, and
nothing better existed yet.

### Why it survived three milestones

Each retirement stopped at a different, honestly-stated obstacle:

| Milestone | Why it stayed |
|---|---|
| **31.1** | The Engineering Engine read it. ADR-0025: *"they are not proven unused, so they are not removed."* Removing a live retrieval substrate to win a headline count would have broken six milestones of working functionality. |
| **31.2** | The engine stopped reading it - but four route groups still served it, and one compatibility adapter still spoke its vocabulary. ADR-0026 §9 recorded the gate: ten conditions, three failing, all three the same blocker. |
| **31.3** | The adapter went, and with it the `structured_retrieval → graph_builder` coupling in the governed path. ADR-0027 recorded the second condition met and the first unchanged: *"the remaining blocker is entirely a product decision."* |

That decision has now been taken.

### The objective retirement conditions

ADR-0026 §9 and ADR-0027 between them set two:

1. **The four legacy route groups are withdrawn**, so nothing reads the
   projection.
2. **`structured_retrieval`'s value objects stop referencing
   `graph_builder`**, so the packages can be deleted independently.

Condition 2 was met by EPIC 31.3. Condition 1 is met here.

## Decision

### 1. The route inventory was **20**, not 15

The audit that opened this milestone re-enumerated the live route table
rather than trusting the earlier count, and found five more routes than
the four route groups implied - because one router served eight routes,
of which only two carried a `/graph-executions` path.

| Group | Routes |
|---|---:|
| `/graph-builder/*` | 3 |
| Project Knowledge Graph router | 8 |
| `/projects/{id}/graph/*` (Graph Query) | 7 |
| `/projects/{id}/structured-retrieval/*` | 2 |
| **Total** | **20** |

### 2. Six of them were one character from the governed surface

The Project Knowledge Graph router served these, and they are the reason
re-enumeration mattered:

```
GET /projects/{id}/knowledge-graph/nodes
GET /projects/{id}/knowledge-graph/nodes/{graph_entity_id}
GET /projects/{id}/knowledge-graph/nodes/{graph_entity_id}/incoming
GET /projects/{id}/knowledge-graph/nodes/{graph_entity_id}/outgoing
GET /projects/{id}/knowledge-graph/relationships
GET /graph-operation-batches/{batch_id}/executions
```

The governed graph serves `/knowledge-graph/nodes`. The retired
projection served `/projects/{id}/knowledge-graph/nodes`. **The
difference between governed and ungoverned engineering knowledge was a
path prefix**, on endpoints returning superficially similar shapes.

Nobody had confused them - the frontend used only the governed routes -
but the arrangement was one careless integration away from doing so, and
that is now impossible rather than merely unlikely.

### 3. Withdrawn routes return **404**, not 410

No `410 Gone` shim, following the precedent ADR-0025 set for the legacy
graph routes and for the same reason:

> it preserves a URL whose only honest answer is that the data behind it
> should never have been served, and it is a route to maintain forever.

A `410` would additionally be a lie about durability here: it implies a
resource that once existed at a stable address and was deliberately
sunset. These were internal engineering endpoints with no external
consumer, no published contract in `public_api.md`, and no frontend
caller. A `404` says what is true - there is nothing at this address.

The routers are **deleted**, not unregistered. A deregistered router is
a router somebody re-registers.

### 4. `RetrievalMode` was moved, not aliased

`retrieval_bridge` is live and authoritative: it serves
`POST /projects/{id}/engineering-requests/prepare`, and its output feeds
the **governed** Engineering Engine. It imported one enum,
`RetrievalMode`, and four numeric bounds from the retiring package.

An alias re-exporting `RetrievalMode` from a retired module would have
made this milestone a rename. Instead the enum is **defined outright**
at `app/domain/retrieval_bridge/retrieval_mode.py`, and the bounds are
stated in `retrieval_bridge_validation.py` - which its own docstring had
always claimed ("restated rather than imported") without it being true.

The concept outlived the package that first defined it. A prepared
request declares what shape of retrieval it asks for; that is a fact
about the request, and the bridge is its owner now. All eight live
imports point at the bridge, proven by inspection rather than asserted.

One stale docstring was corrected in the same edit:
`_mode_agreement_errors` described itself as guarding against *the
engine* re-deriving a different mode. The engine has derived no mode
since EPIC 31.2. The rule survives and is still valuable - it now
protects the **caller**, who reads the declared mode - so the reason was
rewritten rather than the rule removed.

### 5. `canonical_facts`, `proposed_claims` and `review_workflow` survive

These hold **unique, human-authored records**: a claim somebody wrote, a
review candidate, an approval, and the history of that review. They are
the *input* the retired projection was computed from, and they are not
graph-shaped queryable engineering knowledge.

They keep their own routes and their own tables. Deleting them would
destroy engineering and audit information that nothing else records,
which §16 of the milestone forbids and which no architectural goal
requires: the invariant is about **queryable graph-shaped engineering
knowledge projections**, not about every relational table that relates
two things.

After `graph_builder` went, Canonicalization's only remaining consumer
outside its own routes is `retrieval_bridge/designation_extraction.py`,
which uses `normalize_entity_reference` - a pure normalisation function,
not the graph.

### 6. Seven tables dropped by migration `f4a90c27b615`

```
graph_execution_fingerprints
graph_execution_operation_results
project_graph_relationships
project_graph_nodes
graph_operations
graph_executions
graph_operation_batches
```

Dropped dependants-first, because the foreign keys dictate the order and
an engine that enforces them would reject any other.

**Upgrade** on an existing installation drops exactly these seven and
touches nothing else. Verified against a representative pre-retirement
database seeded with a project, a batch, an execution, a fingerprint and
a projection node: after upgrade the legacy tables are gone and the
governed graph, semantic statements, reviews, documents, audit events,
`canonical_facts`, `proposed_claims` and `review_candidates` are all
intact.

**Fresh installation** reaches HEAD with 45 tables and none of the seven
- the baseline creates them and this migration drops them, which is the
cost of not editing an applied migration.

### 7. Downgrade restores the schema, **never the rows**

`downgrade()` recreates all seven tables with their original columns,
indexes, unique constraints and foreign keys - **empty**. Verified: after
downgrade the shape is back and `project_graph_nodes` holds zero rows.

This is stated here, in the migration's own docstring, and in
`operational_reliability.md`, rather than discovered by an operator
mid-rollback. **A rollback returns the shape, not the contents.** An
installation that may want the rows takes the export the migration
documents *before* upgrading.

### 8. No legacy row became governed knowledge, and no review was fabricated

Every dropped row was **derived**: nodes and relationships are a
projection of `canonical_facts`; operations are the instructions that
produced them; executions and fingerprints are the record of running
them. The unique input survives in the tables §5 retains.

Loading the projection into the Governed Knowledge Graph was never an
option. Every governed edge requires an approving review of a *semantic
statement the deterministic pipeline derived from a document*, and none
of these rows has one. Manufacturing that approval would attribute a
judgement to a named engineer who never made it - the precise fraud
ADR-0004 exists to prevent, and the reason ADR-0025 refused the same
migration for the legacy graph.

**No `engineering_reviews` row was created by this milestone.**

## Consequences

**Positive**

- **One runtime engineering knowledge graph**, asserted structurally:
  `graph_contexts == ["governed_knowledge_graph"]`.
- **ADR-0004 has nothing left behind it.** A claim approved in the legacy
  workflow now reaches no queryable graph at all - not "a different graph
  disagrees", but "there is nowhere else to ask". A test asserts exactly
  that.
- The `/knowledge-graph` path prefix now means one thing.
- ~60 runtime modules, 20 routes and 7 tables removed; 26 test modules
  that existed only to test them go with them.
- Attack surface reduced: no endpoint can reach the retired tables, and
  no dependency-injection path constructs a retired repository.

**Negative**

- **Capability removals with no successor**, stated rather than papered
  over:
  - *Attribute/property-bag search.* Legacy retrieval could find every
    node with an attribute called X. The governed graph has no property
    bag (ADR-0024) and no governed query reproduces this.
  - *Broad lexical search.* Legacy matching swept canonical ids, entity
    types, attribute keys and every string attribute value. Governed
    matching compares a designation against the governed label and the
    pipeline's normalized value.
  - *Building and executing a graph from approved claims.* The claims
    remain; the projection does not.
- **Existing installations lose the projection rows on upgrade**,
  mitigated by the documented export and by the rows being derived.
- A downgrade returns an empty schema (§7).

**Neutral**

- A pre-existing defect surfaced during the search sweep and was fixed in
  passing, because the same edit had to repoint the file: the LLM
  invocation smoke-test script built its synthetic prompt with
  `project_id = 0`, which Context Assembly has always rejected. It could
  never have reached a provider. It now uses a valid id and an empty
  governed result.

## Preventing a parallel knowledge path

Architecture tests, not prose:

| Test | Proves |
|---|---|
| `test_there_is_exactly_one_runtime_engineering_graph_context` | One domain package holds graph-shaped engineering knowledge. |
| `test_no_retired_lineage_package_survives_anywhere_in_runtime` | All six layers gone - a context keeping one layer is one somebody rebuilds. |
| `test_no_runtime_module_imports_the_retired_lineage` | Import-level, not filename-level. This is the check that would have caught `retrieval_bridge`. |
| `test_no_route_serves_the_retired_lineage` | Live route table, naming `/projects/{id}/knowledge-graph` explicitly. |
| `test_the_retired_graph_tables_are_not_in_the_orm_metadata` | The mapper decides what a fresh database gets. |
| `test_only_governed_promotion_authors_queryable_knowledge` | One **application service** may write the projection. Repository methods are storage; authority is a service-layer concern. |
| `test_no_pipeline_or_review_module_writes_any_graph` | Ingestion, canonicalisation, the pipeline stages, Human Review, `review_workflow` and `proposed_claims` all reach no graph. Before this milestone only the governed half could be asserted. |

`test_no_governed_module_reaches_the_retired_lineage` names each governed
context individually, so a failure says which boundary was crossed.

## Rejected Alternatives

**Return `410 Gone` for a release.** Rejected - see §3, and ADR-0025's
identical reasoning.

**Keep the tables and stop writing them.** Rejected for the reason
ADR-0025 gave: it leaves a queryable store of ungoverned engineering
claims in the database with no owner and no reader, which is the worst
of both - anybody with SQL access still finds it and has no way to know
what it was.

**Migrate the projection into the governed graph.** Rejected outright.
See §8.

**Delete `canonical_facts` and the legacy review workflow too.**
Rejected: they hold unique human-authored records and serve their own
API. Retiring a projection is not a reason to delete its inputs, and the
milestone's own instruction was to be exact about which bounded context
owns each model.

**Re-export `RetrievalMode` from the retired package.** Rejected: an
alias would keep the retired module importable and reduce the milestone
to a rename.

**Retire `retrieval_bridge` along with the enum it imported.** Rejected:
it is a live capability that prepares requests for the *governed*
engine. Deleting it because of one misplaced import would have removed
working functionality to satisfy a search result.

## Related

- [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) - the rule
  that now has no exception behind it.
- [ADR-0007](0007-project-knowledge-graph-persistence.md) - the
  persistence decision this retires. **Superseded.**
- [ADR-0010](0010-structured-retrieval-foundation.md) - legacy Structured
  Retrieval. **Superseded** by ADR-0026.
- [ADR-0024](0024-governed-knowledge-graph-as-projection.md) - the
  governed graph that made retirement possible.
- [ADR-0025](0025-retire-the-legacy-knowledge-graph.md) - the retirement
  that deferred this one, and the 404-not-410 precedent.
- [ADR-0026](0026-governed-structured-retrieval.md) §9 - the retirement
  gate this satisfies.
- [ADR-0027](0027-governed-context-assembly.md) - the second condition,
  met.
- `docs/architecture/knowledge_graph.md` - the as-built inventory.
