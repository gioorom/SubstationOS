# Performance Baseline — Project Knowledge Graph, Graph Query & Structured Retrieval

**Status:** Baseline measurement, established by Milestone 12 (Knowledge
Platform Hardening), extended by Milestone 13 (Structured Retrieval
Foundation), and extended again by Milestone 17 (LLM Invocation
Runtime) with its own, dataset-independent operations below. Context
Builder (Milestone 14), Prompt Builder (Milestone 15), and the LLM
Provider Abstraction Layer (Milestone 16) each added their own smoke
benchmark to `graph_performance_benchmark.py` and are exercised by
`test_graph_performance_benchmark_smoke.py`, but — a pre-existing,
unremediated gap this milestone does not expand its own scope to fix —
their numbers were never carried into this document's own Results
table; only Milestone 13's Structured Retrieval numbers were. This is
**not** a performance-optimization milestone — the
purpose of this document is to record deterministic, reproducible
numbers for the current dev adapter (SQLite via SQLAlchemy) so future
work has something concrete to compare against, and to name the
algorithmic risk areas already visible at this scale.

## Methodology

- Script: `apps/backend/scripts/benchmarks/graph_performance_benchmark.py`.
  Run directly for a full report:

  ```bash
  cd apps/backend
  python -m scripts.benchmarks.graph_performance_benchmark
  ```

- Smoke coverage only (small dataset, no timing assertions):
  `apps/backend/tests/benchmarks/test_graph_performance_benchmark_smoke.py`,
  picked up by the normal `python -m pytest` run. The medium dataset is
  **not** run by the normal test suite — only by invoking the script
  directly — so CI never depends on a multi-second benchmark or a
  wall-clock threshold.
- Fixtures are **synthetic and generated**, never production or
  confidential data: a fixed rotation of five domain-realistic entity
  types (`CABLE`, `TRANSFORMER`, `CIRCUIT_BREAKER`, `BUSBAR`,
  `DISCONNECTOR`) and three relationship types (`CONNECTED_TO`,
  `FEEDS`, `PROTECTED_BY`), wired with a seeded `random.Random(42)` so
  every run produces the identical graph shape (CLAUDE.md §16,
  Reproducibility). 5% of nodes are deliberately left unconnected so
  orphan detection has real orphans to find.
- Two dataset sizes, per the milestone's request:
  - **small** — 100 nodes / 200 relationships.
  - **medium** — 5,000 nodes / 10,000 relationships.
- Database: in-memory SQLite (`sqlite://` with `StaticPool`), the same
  recipe `tests/conftest.py`'s `db_session` fixture uses — not the
  on-disk dev database, never touched by this script.
- Two write paths are measured separately, and are not directly
  comparable to each other:
  1. **Store-level, per-operation calls** (`node_upsert`,
     `attribute_merge`, `relationship_upsert`) — calling
     `SqlAlchemyGraphStore` methods directly in a loop, one call per
     node/relationship, `flush()`-only, one `commit()` at the end. This
     isolates the cost of a single store operation.
  2. **`batch_execution`** — a full, realistic run of
     `graph_execution_service.execute_batch` over one
     `GraphOperationBatch` containing every node/attribute/relationship
     operation for the dataset, executed as a single atomic
     `GraphUnitOfWork` transaction (see
     [repository_transaction_conventions.md](repository_transaction_conventions.md)).
     This is the path a real document ingestion actually exercises.
- Read operations (`list_nodes`, `list_relationships`, `statistics`,
  `orphan_detection`, `attribute_filtering`, `one_hop_neighborhood`)
  are measured against the project populated by the store-level writes.
- **Structured Retrieval (Milestone 13)**: `run_structured_retrieval_benchmarks`
  populates its own project the same way, then times
  `structured_retrieval_service.retrieve` through a real
  `SqlAlchemyGraphQueryRepository` for the six modes named in the
  milestone: exact entity lookup (`retrieval_entity_lookup`),
  entity-type search (`retrieval_entity_type`), relationship-type
  search (`retrieval_relationship_type`), lexical search
  (`retrieval_lexical`, two terms, `ANY` mode), combined search
  (`retrieval_combined`, entity type + attribute name), and entity
  lookup with 1-hop neighborhood enrichment
  (`retrieval_with_neighborhood_enrichment`).
- **LLM Invocation Runtime (Milestone 17)**: `run_llm_invocation_runtime_benchmarks`
  is dataset-independent (no `SMALL_DATASET`/`MEDIUM_DATASET` parameter)
  since the runtime's own cost has nothing to do with graph size. It
  times `llm_runtime.run_invocation` against a self-contained,
  in-process `FakeLLMProviderAdapter` for a single successful attempt
  (`llm_invocation_fake_success`) and for one transient failure
  followed by a successful retry (`llm_invocation_transient_then_success`,
  using a no-op injected sleeper so no real backoff delay is ever
  measured or waited on), and times the Anthropic response mapper
  (`map_content`/`map_finish_reason`/`map_usage`) against a synthetic,
  locally constructed SDK `Message` object
  (`anthropic_response_normalization`) - never a real Anthropic call,
  never a real `httpx` request, in either measurement.

## Results (last recorded run)

Machine-specific, single-run, in-memory SQLite numbers — useful for
relative comparison across future runs on the same machine, not an
absolute SLA.

| dataset | operation            | units  | seconds | seconds/unit |
|---------|-----------------------|-------:|--------:|--------------:|
| small   | node_upsert            |    100 |  0.0358 |      0.000358 |
| small   | attribute_merge        |     40 |  0.0133 |      0.000333 |
| small   | relationship_upsert    |    200 |  0.1645 |      0.000822 |
| small   | list_nodes             |    100 |  0.0015 |      0.000015 |
| small   | list_relationships     |    200 |  0.0024 |      0.000012 |
| small   | statistics             |    300 |  0.0060 |      0.000020 |
| small   | orphan_detection       |    100 |  0.0021 |      0.000021 |
| small   | attribute_filtering    |    100 |  0.0008 |      0.000008 |
| small   | one_hop_neighborhood   |      1 |  0.0037 |      0.003680 |
| small   | batch_execution        |    340 |  0.2399 |      0.000705 |
| medium  | node_upsert            |  5,000 |  1.8162 |      0.000363 |
| medium  | attribute_merge        |  2,000 |  0.7049 |      0.000352 |
| medium  | relationship_upsert    | 10,000 |  8.5271 |      0.000853 |
| medium  | list_nodes             |  5,000 |  0.0399 |      0.000008 |
| medium  | list_relationships     | 10,000 |  0.1077 |      0.000011 |
| medium  | statistics             | 15,000 |  0.1247 |      0.000008 |
| medium  | orphan_detection       |  5,000 |  0.0950 |      0.000019 |
| medium  | attribute_filtering    |  5,000 |  0.0462 |      0.000009 |
| medium  | one_hop_neighborhood   |      1 |  0.0058 |      0.005827 |
| medium  | batch_execution        | 17,000 | 12.1700 |      0.000716 |
| small   | retrieval_entity_lookup       |      1 |  0.0003 |      0.000326 |
| small   | retrieval_entity_type         |     20 |  0.0012 |      0.000062 |
| small   | retrieval_relationship_type   |     66 |  0.0030 |      0.000046 |
| small   | retrieval_lexical             |    300 |  0.0039 |      0.000013 |
| small   | retrieval_combined            |     20 |  0.0019 |      0.000097 |
| small   | retrieval_with_neighborhood_enrichment |  1 |  0.0037 |     0.003661 |
| medium  | retrieval_entity_lookup       |      1 |  0.0004 |      0.000398 |
| medium  | retrieval_entity_type         |  1,000 |  0.0203 |      0.000020 |
| medium  | retrieval_relationship_type   |  3,333 |  0.1618 |      0.000049 |
| medium  | retrieval_lexical             | 15,000 |  0.1782 |      0.000012 |
| medium  | retrieval_combined            |  1,000 |  0.0934 |      0.000093 |
| medium  | retrieval_with_neighborhood_enrichment |  1 |  0.0056 |     0.005630 |
| n/a     | llm_invocation_fake_success            |      1 |  0.0010 |     0.001028 |
| n/a     | llm_invocation_transient_then_success  |      2 |  0.0006 |     0.000320 |
| n/a     | anthropic_response_normalization       |      1 |  0.0000 |     0.000011 |

## Observations

- **Reads scale well at this size.** `list_nodes`, `list_relationships`,
  `statistics`, `orphan_detection`, and `attribute_filtering` all stay
  under 0.13s at 5,000 nodes / 10,000 relationships, and their
  per-unit cost barely moves between small and medium — consistent
  with the fact that most of them are single SQL queries returning
  already-mapped ORM rows.
- **Writes are the dominant cost, and scale roughly linearly, not
  because of an algorithmic problem but because there is no batching.**
  `SqlAlchemyGraphStore.upsert_node`/`merge_node_property`/
  `upsert_relationship` each issue a `SELECT` before any `INSERT`
  (existence/uniqueness check), and `upsert_relationship` issues two
  further node-existence `SELECT`s before its own — three round-trips
  per relationship. `graph_execution_service._execute_operation` calls
  the store once per operation with no batching, so a batch of N
  operations issues on the order of 2N–4N individual SQL statements.
  At 17,000 operations this is ~12s even against in-memory SQLite; a
  real (disk-backed, networked) database would be materially slower.
  This is the clearest, lowest-risk candidate for a future
  optimization (e.g. bulk existence-check queries), but no such change
  is made in this milestone — see Non-Goals below.
- **`one_hop_neighborhood` is flat regardless of dataset size** because
  it depends only on the queried node's own degree, not on the
  project's total node count — but its *own* cost scales with that
  node's degree: `graph_query_service.get_neighborhood` calls
  `repository.get_node(...)` once per distinct neighbor in a Python
  loop (N+2 round-trips for a node with N distinct neighbors,
  `app/services/graph_query_service.py:220-227`). The benchmark
  deliberately queries the single busiest node in the synthetic graph,
  so this number already reflects a close-to-worst-case degree for
  each dataset.
- **Structured Retrieval's per-mode cost tracks exactly the Graph
  Query operation it plans.** `retrieval_entity_lookup` is a single
  `get_node` and stays flat (~0.0003-0.0004s) across both dataset
  sizes, same as Graph Query's own `entity_by_id`. `retrieval_lexical`
  and `retrieval_combined` (which both plan a full `list_nodes`/
  `list_relationships` scan) scale with dataset size the same way
  `list_nodes`/`list_relationships` themselves do - Structured
  Retrieval adds no new algorithmic complexity of its own on top of
  Graph Query's; it inherits Graph Query's existing cost profile
  exactly, then does its own in-memory matching/scoring pass over the
  already-fetched rows (`retrieval_lexical` at medium: 0.178s for
  15,000 nodes+relationships scanned, comparable in order of magnitude
  to `list_relationships`' own 0.114s over the same row count).
- **`retrieval_with_neighborhood_enrichment` is bounded, not
  unbounded**, because Milestone 13 enriches only the already-limited,
  final page of candidates (at most `request.limit` entities), not the
  full pre-limit candidate pool - its cost (~0.006s) is close to
  `one_hop_neighborhood`'s own cost, as expected, and does not grow
  with the size of the matched candidate set.
- **The LLM Invocation Runtime's own overhead (Milestone 17) is
  microseconds, independent of any dataset size** - expected, since
  `run_invocation` orchestrates a fake or mocked provider call, not a
  real network round-trip: `llm_invocation_fake_success` (a single
  successful attempt) and `llm_invocation_transient_then_success` (one
  retried attempt then success, timed with a no-op injected sleeper so
  the recorded time reflects only the runtime's own bookkeeping, never
  a real backoff delay) both complete in ~1ms;
  `anthropic_response_normalization` (mapping a synthetic SDK `Message`
  through the error/response mappers) completes in well under 0.1ms.
  These numbers characterize the runtime's own logic only - real
  end-to-end invocation latency is dominated entirely by the external
  provider's own response time, which this benchmark deliberately never
  measures (see Methodology below).

## Algorithmic risk areas identified (not fixed this milestone)

Per the milestone's explicit list, the following are Python-side
operations that read broader data than strictly needed and then filter
in Python — flagged as known scaling risks, not defects, since nothing
today has demonstrated a real performance problem at the sizes this
product currently targets:

1. **`list_nodes_with_attribute`** (backing `attribute_filtering`,
   `app/infrastructure/graph_query/sqlalchemy_graph_query_repository.py`)
   fetches **every** node for the project, then filters in Python
   (`attribute in record.properties`), because `properties` is stored
   as a JSON column with no attribute-level SQL predicate. Cost is
   O(all nodes in project) regardless of how selective the requested
   attribute is.
2. **`list_orphan_nodes`** (backing `orphan_detection`, and reused by
   `get_statistics`'s `orphan_count`) issues two unfiltered-by-degree
   queries — all nodes, all relationships — then builds a Python `set`
   of connected `(entity_type, canonical_id)` pairs and filters nodes
   against it. Cost is O(nodes + relationships) per call, paid again
   in full every time `get_statistics` is called even though it only
   needs a count.
3. **`get_neighborhood`'s per-neighbor `get_node` loop** (see
   Observations above) — N+2 round-trips for a node with N distinct
   neighbors, rather than one query fetching all N neighbor rows.
4. **No bulk/batch upsert exists anywhere in `SqlAlchemyGraphStore`.**
   Every operation in a `GraphOperationBatch`, however large, is one
   Python-level call and 1–3 SQL round-trips — the dominant cost
   observed above.
5. **JSON property filtering is inherently limited in SQLite** — even
   a SQL-side rewrite of (1) would still depend on `json_extract`-style
   predicates rather than an indexed column, so query-planner support
   is weaker than for a normal column; worth remembering if attribute
   filtering ever needs to scale much further.
6. **Structured Retrieval's `LEXICAL_SEARCH`/`COMBINED` modes and the
   value-only `ATTRIBUTE_SEARCH` shape always fetch the full node
   and/or relationship set for the project** (`RetrievalQueryOperation.ALL_ENTITIES`/
   `ALL_RELATIONSHIPS`, see `retrieval_query_planner.py`) - there is no
   SQL-side lexical index or attribute-value index to narrow the fetch,
   so these modes inherit risk (1) and (5) above directly, plus pay
   their own O(nodes + relationships) Python-side matching pass on top.
   Not a new risk Structured Retrieval introduces so much as the same
   Graph Query risk surfacing through a new caller - worth revisiting
   together if either is ever addressed.
7. **No bulk `get_node` exists for neighborhood enrichment** - `_enrich_with_neighborhood`
   calls `repository.get_node(...)` once per distinct neighbor, the
   same N+1 shape `graph_query_service.get_neighborhood` already has
   (risk 3 above), inherited rather than duplicated since Structured
   Retrieval reuses the same neighbor-id-collection logic.

None of these are changed in this milestone: no defect was
demonstrated (per the Change Discipline rule — "identify the concrete
defect... make the smallest coherent correction"), and the sizes
measured here comfortably meet current product needs. They are the
natural starting point for a future, dedicated performance milestone
if real usage ever demands it.

## Governed Structured Retrieval (EPIC 31.2)

`run_governed_retrieval_benchmarks` measures the five representative
governed operations against a synthetic governed graph of the same size
as the Canonical Facts dataset the legacy retrieval benchmarks use, so
the two are comparable rather than merely both present:

| Operation | What it does |
|---|---|
| `governed_designation_lookup` | Resolve a designation to governed assets |
| `governed_quantity_traversal` | Resolve, then follow governed relationships |
| `governed_relationship_lookup` | Every governed relationship of one kind, in one project |
| `governed_document_knowledge` | Everything one document produced |
| `governed_provenance_by_identity` | One governed object, by id |

On the small dataset (100 nodes / 200 relationships, 50 governed assets)
every operation completes in **single-digit milliseconds**, and
provenance-by-identity - a single indexed row read - is roughly an order
of magnitude cheaper than the four scoped operations. The smoke test in
`tests/benchmarks/` asserts the operations run and produce sane unit
counts and **never asserts wall-clock time**, per this document's
standing rule.

### The one algorithmic trade, stated

`governed_designation_lookup` filters by kind, state and project **in
SQL** - all covered by `ix_governed_graph_nodes_project_state` - and
then folds designations **in Python**.

That is deliberate and it is a determinism-over-speed trade:
`LOWER(label) = …` or `label ILIKE …` would make the answer depend on
the database's collation, so the same governed graph could answer
differently on SQLite and PostgreSQL. A retrieval contract that promises
reproducibility cannot rest on that.

The cost is one scan of the governed nodes in scope. At present the
governed graph holds only what somebody has approved, so the set is
small. **No index was added**, because adding a normalized-designation
column now would denormalize the governed model ahead of a measured
need - and the benchmark above is what makes the day that changes
visible rather than theoretical.

## Explicit non-goals of this baseline

No caching layer, Redis, Elasticsearch, Neo4j, materialized view, or
recursive/shortest-path graph algorithm was introduced or evaluated —
out of scope for Milestone 12 per its own Non-Goals list, and orthogonal
to what this baseline exists to measure (the current adapter's
behavior, not its replacement).
