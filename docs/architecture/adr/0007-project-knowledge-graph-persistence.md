# ADR-0007: Project Knowledge Graph Persistence — Execution Semantics, Database-Agnostic Store, and Deferred Neo4j

## Status

Accepted.

## Context

By Milestone 11.1, Graph Builder (`app/domain/graph_builder/**`) already
translates `APPROVED`, canonicalized `CanonicalFact`s into a deterministic,
deduplicated `GraphOperationBatch` — a plain, ordered list of `CREATE_NODE`,
`UPDATE_NODE`, and `CREATE_RELATIONSHIP` instructions. Graph Builder
persists that batch as its own artifact, but performs no execution: no
node or relationship is ever written to a graph. The architecture
(`project_intelligence_architecture.md` §7, ADR-0002) requires the Project
Knowledge Graph itself to be reviewed, versioned, and queryable — none of
which exists yet. Milestone 11.2 is the first component that actually
writes to, and reads from, that graph.

Two decisions had to be made before any code: what technology stores the
graph, and how "execute a batch exactly once, correctly, even under
retries and concurrent requests" is actually guaranteed.

## Decision

### 1. Graph Builder and Graph Persistence remain two separate bounded contexts

Graph Builder (`app/domain/graph_builder/**`) owns translation:
Canonical Fact → deterministic operation. Graph Persistence
(`app/domain/project_knowledge_graph/**`) owns execution and current
graph state: operation → node/relationship row. Graph Persistence never
canonicalizes raw values, interprets Proposed Claims, inspects Review
Workflow, rebuilds operations, or performs semantic inference — it only
applies the operations a `GraphOperationBatch` already contains, exactly
as ADR-0002's Index/Graph separation is extended by every later layer in
this pipeline: each stage trusts the stage before it completely, and
adds exactly one new responsibility.

### 2. The graph is project-centric; identity is a natural key, not a surrogate id

Every `ProjectGraphNode`/`ProjectGraphRelationship` belongs to exactly
one project (ADR-0001). A node's identity is
`(project_id, entity_type, canonical_id)` — the same triple Graph
Builder's own `GraphEntityId` already carries — never the row's
database-generated `id`. This is deliberate: `GraphEntityId` is
built exclusively from a Canonical Domain-normalized
`CanonicalEntityReference` (never a raw string), so two facts about
"Cable 295" in the same project always resolve to the same node,
and the same tag in two different projects never collides. No
project-instance-specific schema, no cross-project relationship, and no
hardcoded substation/cabin exists anywhere in this bounded context.

### 3. A relational reference adapter today; a `GraphStore` port so any store can replace it tomorrow

`GraphStore` (an `ABC`) defines every graph mutation and read this
milestone needs, in storage-agnostic terms — `upsert_node`,
`merge_node_property`, `upsert_relationship`, plus reads. Nothing above
this port knows or cares that `SqlAlchemyGraphStore` currently
implements it with three plain relational tables
(`project_graph_nodes`, `project_graph_relationships`, plus the
execution audit tables). **Neo4j, Cypher, and every other native graph
technology are intentionally deferred** — not because they are
unsuitable, but because this milestone's job was to prove the
execution *semantics* (idempotent upsert, atomic batch execution,
project-scoped identity) independently of any specific store, using the
simplest adapter that could prove them: the SQL infrastructure this
repository already runs on every other bounded context. Swapping in a
native graph database later is an adapter change behind `GraphStore`,
never a change to `GraphExecutionService` or the domain model — the
same "AI as a Service" replaceability discipline `CLAUDE.md` §3 and
ADR-0006 already apply to AI providers, applied here to storage.

### 4. Batch execution is atomic, via an explicit `GraphUnitOfWork` port

A batch's operations must all apply, or none must. `SqlAlchemyGraphStore`
and `SqlAlchemyGraphExecutionRepository` only `add`/`flush` within one
`execute_batch` call — they never `commit` on their own, unlike every
other repository in this codebase (Project, Engineering Index, Proposed
Claims, Review Workflow, Canonicalization, Graph Builder all commit
per-call). `GraphExecutionService` is the only thing that calls
`GraphUnitOfWork.commit()`/`.rollback()`, once, after every operation in
a batch has either succeeded or one has failed. This is a deliberate,
minimal exception to this codebase's usual per-repository-call commit
convention, introduced because this is the first bounded context whose
correctness requires a transaction spanning several repository calls —
not a general pattern change for every future context.

### 5. Idempotency is a deterministic content fingerprint, not a batch id

A `GraphOperationBatch`'s `id` identifies *that specific persisted
artifact*; it says nothing about whether its content has already been
applied. `graph_execution_fingerprint.compute_batch_fingerprint` hashes
`project_id`, `scope`, `scope_id`, and every operation's complete
semantic payload (entity ids, relationship type, attribute/value) —
deliberately excluding `source_fact_id` (which fact produced an
operation does not change its effect on the graph) and excluding every
random id and timestamp. `GraphExecutionRepository.get_successful_by_fingerprint`
is checked before any mutation runs: retrying the same batch, or
executing a *different* batch that happens to describe the identical
graph state, both return the existing `SUCCEEDED` execution unchanged.
A dedicated `graph_execution_fingerprints` table (fingerprint → the
execution that first succeeded with it) carries a plain, unconditional
database uniqueness constraint — correct without a partial index,
because a `FAILED` attempt never inserts a row there, which is exactly
what lets a failed batch be retried.

## Consequences

- Every graph read/write in this codebase can be exercised, tested, and
  reasoned about today without running or mocking a graph database —
  the entire test suite (domain, infrastructure, service, API) runs
  against SQLite, in-process, in milliseconds.
- Adopting Neo4j (or any other store) later requires one new adapter
  implementing `GraphStore`, plus its own migration of
  `project_graph_nodes`/`project_graph_relationships` data — the
  domain model, `GraphExecutionService`, and every API contract are
  unaffected by that choice, by construction.
- The relational adapter cannot express genuine graph-native
  operations (multi-hop traversal, path queries) efficiently — by
  design, this milestone implements none of those; Milestone 11.3
  (Knowledge Graph Query Foundation) works within this same
  constraint deliberately, not by accident.
- `GraphUnitOfWork` is a real, if small, deviation from this
  codebase's established "repository commits its own call" convention.
  Any future bounded context needing true multi-repository atomicity
  should follow this same seam rather than inventing a different one.
- A concurrent race between two writers upserting the same node, or
  recording the same fingerprint, surfaces as a database `IntegrityError`
  translated into `ConcurrentGraphMutationError`; the whole batch
  attempt rolls back and must be retried. This is correct and simple,
  but means a genuine high-concurrency race costs a full batch retry
  rather than a fine-grained recovery — acceptable at this milestone's
  scale (synchronous, single-request execution), revisited if async
  execution is introduced later.

## Rejected Alternatives

- **Adopt Neo4j (or another native graph database) now.** Rejected:
  this milestone's job was to define execution semantics — idempotent
  upsert, atomic batch application, project-scoped natural-key identity
  — independently of storage technology. Introducing a new external
  dependency and query language before those semantics were even
  proven would have coupled a genuinely separable decision (what
  runs the mutations) to a much larger one (what stores the graph
  long-term), exactly the kind of premature commitment `CLAUDE.md` §12
  (YAGNI) warns against.
- **Use the database-generated row id as node/relationship identity.**
  Rejected: it would make identity storage-dependent (meaningless
  across a future migration to a different store) and would require a
  lookup just to know "does this entity already exist" — the natural
  key `(project_id, entity_type, canonical_id)`, already fully known
  from a `GraphEntityId`, is both the semantically correct identity and
  the more efficient one to query by.
- **Let each repository commit its own call, as elsewhere in this
  codebase.** Rejected for this bounded context specifically: it would
  make "roll back the complete batch" impossible to guarantee — a
  `CREATE_NODE` succeeding and committing before a later
  `CREATE_RELATIONSHIP` in the same batch fails would leave a partially
  applied batch, which this milestone's requirements explicitly forbid.
- **Recover in place from a concurrent-write `IntegrityError` (catch,
  re-select, continue the same transaction).** Rejected: SQLAlchemy
  requires a rollback before a session is usable again after a failed
  flush, and a partial rollback mid-batch is not meaningfully different
  from a full one here — recovering by aborting the whole attempt and
  letting the caller retry is simpler, and the retry converges cleanly
  through the normal upsert path.
- **Fingerprint on batch id instead of content.** Rejected: it would
  make retries of the *same* batch idempotent but would not satisfy
  the explicit requirement that a *different* batch with identical
  semantic content also be treated as already executed — a real case,
  since Graph Builder can be asked to rebuild a batch for the same
  project twice and produce two distinct persisted `GraphOperationBatch`
  rows with the same operations.
