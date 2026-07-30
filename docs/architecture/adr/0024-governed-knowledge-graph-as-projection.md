# ADR-0024: The Governed Knowledge Graph is a rebuildable projection

## Status

Accepted.

## Context

EPIC 31 introduces the Knowledge Graph: the authoritative query model
over approved engineering knowledge. By this point the platform has a
deterministic pipeline producing immutable semantic statements
(EPIC 30.1), a Workspace that makes their provenance inspectable
(EPIC 30.2), authenticated identity (EPIC 30.3), and an append-only
record of engineering judgement (EPIC 30.4).

The graph is where those meet a reader. Four decisions in it are
hard to reverse - changing any later means re-identifying every node and
edge already stored - and are recorded here.

The context that constrains all four: **the platform's value rests on
knowing why it believes something.** A graph that could not answer that
would be a faster way to be wrong.

There is one further constraint, particular to this repository: two
earlier graph implementations already exist, both fed from the legacy
Canonical Facts lineage, and [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md)
records that neither satisfies the review gate it requires.

## Decision

### 1. The graph is a projection, never a source of truth

Every node and edge is computed from a semantic statement and its current
review. Nothing originates in the graph. It may be dropped and rebuilt at
any time, and the repository has a `clear()` that no other repository in
this system has - or may acquire.

Two consequences are load-bearing rather than incidental. The projection
is a **pure function of the statements and the reviews**: identities are
hashes of governed keys, and `created_at` comes from the authorising
review's timestamp rather than from the clock, so nothing in the stored
content depends on when promotion ran. And **the pipeline never learns it
is projected** - the moment a rule could consult the graph, engineering
output would depend on what somebody had approved, and determinism would
be gone.

### 2. Only `APPROVED + APPLIES` is promoted

The sole admission rule, with every refusal named and tested
([promotion_rules.md](../promotion_rules.md)). Rejected statements,
inconclusive ones, judgements awaiting revalidation and orphaned reviews
**never** become graph knowledge.

Knowledge whose authorisation stops holding becomes `HISTORICAL` with a
recorded reason - not removed, not disabled, not superseded. It is
excluded from queries and stays readable with its provenance.

### 3. Rebuildability is a first-class property, and is asserted

Not a recovery procedure - a **design property that tests check**. Three
of them: that a rebuild reproduces identical content, that rebuilding
twice is stable, and that a rebuild finds approvals on its own without
ever having been promoted incrementally.

Incremental promotion and full rebuild call the **same** rule function.
Neither re-implements it, so the two cannot disagree about what is
promotable - which is the usual failure mode of an incremental
projection, and the reason incremental projections are usually not
trustworthy.

### 4. Provenance is mandatory and structural

Every node and every edge carries the statement key, the document, the
checksum, the review id, the reviewer, the rule id and version, the
contract version, the three policy versions and the support fingerprint.
Construction **raises** without them, and the columns are
`nullable=False`.

There is no confidence, score or weight anywhere, and an architecture
test fails on such a column. Knowledge is in the graph because an
engineer approved it; a number expressing how much to trust it would
reintroduce exactly the ungoverned trust signal ADR-0004 rejected.

### 5. Identity derives from governed keys, never from labels

`node_id` from the entity key, `edge_id` from the statement key, both
namespaced and versioned, both `UNIQUE`.

### 6. A new bounded context, not an extension of the existing graphs

`governed_knowledge_graph` is created alongside `project_knowledge_graph`
and the legacy path, and neither of those is modified.

## Consequences

**Positive**

- Every graph answer is explainable, by construction rather than by
  convention.
- The graph can be dropped, migrated, re-sharded or moved to another
  store with no data loss, because it holds nothing that is not derived.
- A rule change, a re-ingestion or a reversed judgement cannot leave
  stale knowledge answering queries.
- The pipeline and Human Review stay unaware of the graph, so neither
  acquires a dependency on what has been published.
- `unchanged` on a rebuild is a free drift detector.

**Negative**

- **A third graph implementation now exists in the repository.** Three
  graphs is a genuine cost and a genuine trap; `knowledge_graph.md` §2
  states the relationship and recommends the retirement path, and this
  EPIC performs none of it.
- A rebuild is synchronous and unbounded - every statement of every
  document in one request. Adequate now; a background job when it is not.
- Storing provenance on every node and edge duplicates a dozen columns
  across two tables. Accepted deliberately: a join to reconstruct why the
  graph believes something is a join somebody eventually skips.
- Reconciliation must run in both directions, so a document-level
  promotion reads the graph's edges as well as the document's statements.
- Promotion is a separate act from review, so approving a statement does
  not publish it. That is intentional - see Rejected Alternatives - but
  it does mean an installation must decide who runs promotion, and when.

**Neutral**

- The graph holds two node kinds and one edge kind, because governed
  semantics produces two entity types and one statement type. It grows
  when the semantics do.
- Project visibility is filtering, not enforcement: authorisation remains
  per-role, inherited from EPIC 30.3.

## Rejected Alternatives

**Extending `project_knowledge_graph` instead of creating a new
context.** Rejected because it accepts `GraphOperationBatch`es built from
Canonical Facts, and the EPIC requires that no source other than approved
semantics may insert engineering knowledge. Extending it would have meant
either admitting a second, ungoverned source into the same tables - the
precise failure ADR-0004 describes - or removing a capability two shipped
milestones depend on, which is a different milestone's work. Its identity
model is also derived from canonical references rather than from entity
keys, so a shared node table would have had two incompatible notions of
what a node *is*.

**Making the graph the source of truth, with the pipeline feeding it
once.** Rejected outright. It would make engineering knowledge editable
in the graph, unrebuildable, and impossible to reconcile with a re-run -
and it is what the legacy path already does, to the tune of an ADR
recording that it must not.

**Promoting on review, automatically.** Rejected: publishing is a
separate act from judging, and an installation may reasonably want the
capability to promote to be narrower than the capability to review.
Coupling them would also have made Human Review import the graph context,
which an architecture test now forbids.

**Storing the current graph state as mutable rows updated in place, with
no rebuild path.** Rejected because it makes every guarantee unverifiable:
without a rebuild there is nothing to compare the incremental result
against, and incremental projections drift silently.

**Promoting statements with a confidence score instead of a review
gate.** Rejected as ADR-0004's original error in a new costume. It shifts
the burden of judging trustworthiness onto every reader of every answer.

**Merging nodes that share a label across documents.** Rejected: `TR1` in
two drawings may be two transformers, and deciding otherwise is
cross-document entity resolution that no governed rule performs. The
graph holds two nodes and says so; `knowledge_graph.md` §4 records the
limit.

**Modelling Voltage, Protection, Connection, Function and Location
nodes.** Rejected because no governed semantics produces them - and for
voltage specifically, the semantics context *deliberately refuses* to
interpret it, since an associated voltage may be rated, test, insulation
or busbar voltage. Adding the node kinds would let the shape of the model
imply knowledge the system does not have.

**Shipping a graph query language - Cypher, GraphQL or SPARQL.**
Rejected for this milestone. A governed graph whose whole value is that
every answer is explainable should not first ship a way to ask questions
whose answers nobody planned; the queries an engineer asks are exposed as
resources, and more are added as more are needed.

**Publishing graph events to a subscriber.** Rejected as infrastructure
nothing needs: the promotion service knows everything that happened,
because it is what made it happen, and it returns the events to its
caller.

## Related

- `docs/architecture/knowledge_graph.md`, `docs/architecture/promotion_rules.md`
- [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) - reviewed
  facts only. This EPIC is the first implementation that satisfies it.
- [ADR-0009](0009-legacy-knowledge-graph-isolation.md) - the legacy path
  this context does not touch and recommends retiring.
- [ADR-0007](0007-project-knowledge-graph-persistence.md) - the earlier
  graph, fed from the Canonical Facts lineage.
- [ADR-0023](0023-human-review-append-only-judgement.md) - the judgements
  this graph is authorised by.
