# ADR-0025: Retire the legacy Knowledge Graph

## Status

Accepted.

## Context

EPIC 31 delivered the Governed Knowledge Graph: a rebuildable projection
over deterministic semantic statements and the human reviews that
approved them. It was the first implementation in this repository to
satisfy [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md).

That left the repository holding **three graph implementations**, from
two different lineages:

| | Source | Consumers |
|---|---|---|
| Legacy (`project_entities`, `entity_relations`) | LLM extraction, written straight from upload | Three deprecated read routes, one frontend page |
| Canonical Facts (`project_graph_nodes`, …) | Canonical Facts, from Proposed Claims | Graph Query → Structured Retrieval → Engineering Engine |
| Governed (`governed_graph_*`) | Approved semantics | The Workspace, the graph API |

The legacy one is the problem ADR-0004 named in 2026 and
[ADR-0009](0009-legacy-knowledge-graph-isolation.md) tracked without
fixing: `ingest_document` wrote AI-extracted entities into the queryable
graph on **every upload**, with no reviewer, no review date, no
provenance beyond a filename, and a bare `confidence` float as the only
trust signal. Both ADRs recorded that this must not happen and that it
was happening anyway.

Two things changed that made it removable rather than merely wrong: a
governed replacement now exists, and an audit proved nothing else depends
on it.

## Decision

### 1. The legacy Knowledge Graph is deleted, not deprecated

Removed entirely: `services/knowledge_graph.py`,
`routers/knowledge_graph.py`, `schemas/knowledge_graph.py`,
`models/knowledge_graph.py`, `services/entity_extractor.py`,
`services/ai/**` and `services/topology/**`. The tables
`project_entities` and `entity_relations` are dropped by migration
`e28b91f4c073`.

Deprecation was rejected. The routes had carried `deprecated: true` in
OpenAPI since Architecture Freeze v1.0 and it changed nothing - a
deprecated endpoint that still serves ungoverned data is still serving
ungoverned data, and a deprecated writer still writes.

### 2. Ingestion writes no graph at all

`upload_document` injected `ingest_document` as the pipeline's
downstream consumer. The consumer is now `None`. Uploading a document
produces canonical artefacts and nothing else.

**Promotion remains explicit**, and this is where that becomes true
rather than aspirational: knowledge enters the graph only through a
capability-gated promotion of a statement an engineer approved. An
architecture test asserts the consumer is `None` and that no ingestion
router touches the graph.

### 3. The Canonical Facts lineage is retained, and documented as retained

`graph_builder`, `project_knowledge_graph` and `graph_query` stay. They
are read at runtime by Structured Retrieval and therefore by the whole
Engineering Engine answering stack (Milestones 13-23).

**They are not proven unused, so they are not removed.** The EPIC's own
instruction was to remove only what is proven unused, and removing a live
retrieval substrate to satisfy a headline count would have broken six
milestones of working functionality.

The consequence is stated plainly rather than glossed: **the repository
still contains two graph implementations.** One is the governed
engineering knowledge model; the other is the retrieval substrate of the
LLM stack. §"Remaining work" below says what closing that requires.

### 4. Backwards compatibility: routes removed, one route repointed

The three legacy read routes are **removed**, not stubbed:

```
GET /projects/{id}/knowledge-graph        removed
GET /projects/{id}/entities               removed
GET /projects/{id}/entities/{entity_id}   removed
```

A `410 Gone` shim was considered and rejected: it preserves a URL whose
only honest answer is "that data should never have been queryable", and
it leaves a route to maintain and to explain.

The frontend route `/projects/{id}/knowledge-graph` **survives and is
rewritten** against the governed graph. Engineers have it bookmarked; the
address stays, what it shows does not. It now lists governed concepts and
their relationships, each with the provenance that authorised it.

### 5. Data is dropped, with a documented export and a rollback

The migration drops both tables. `downgrade()` recreates them with their
original columns, indexes and foreign keys - **empty**, which is stated
in the migration rather than discovered by running it.

The rows are not migrated anywhere, because there is nowhere governed to
put them: the governed graph accepts only statements an engineer
approved, and manufacturing approvals for unreviewed AI output would be
the exact fraud this platform exists to prevent. An operator who wants
the rows exports them first; the migration docstring carries the SQL.

## Consequences

**Positive**

- The ADR-0004 violation is over. It is no longer possible to get
  engineering knowledge into a queryable graph without a named engineer
  approving it.
- Uploading a document is now cheap and predictable: no LLM call, no
  extraction, no graph write. It stores, identifies and canonicalises.
- One less trust model to explain. "Is this reviewed?" has one answer.
- The `EntityType` schema name collision disappeared, so the frontend
  contract stops carrying a fully-qualified workaround name.
- ~2,000 lines of unreachable code removed, including an entire second
  LLM client (`services/ai/**`) that predated the governed provider
  abstraction.

**Negative**

- **Existing installations lose the legacy rows on upgrade.** Mitigated
  by the documented export, and by the fact that those rows were never
  engineering knowledge by this platform's own definition - but it is a
  real loss and an operator must be told before upgrading.
- The upload response's `analysis.entities_found` is now always `0`. The
  field survives its cause, at zero, rather than being removed - removing
  it is a breaking response change this milestone did not need to make.
- Two graph implementations remain. See below.

**Neutral**

- The dropped tables' data is not reconstructible. Neither is it
  reproducible, since it came from non-deterministic LLM extraction over
  bytes that may since have changed - which is itself part of why it was
  never trustworthy.

## Remaining work

Retiring the Canonical Facts lineage requires Structured Retrieval to
read the governed graph instead. That is a real milestone, not a cleanup:

- `graph_query` returns nodes with **property bags**, and
  `structured_retrieval` matches on them. The governed graph deliberately
  has no property bags ([ADR-0024](0024-governed-knowledge-graph-as-projection.md)),
  so the matching strategies need rewriting against typed fields.
- The governed graph holds two node kinds and one edge kind; the
  Canonical Facts graph holds whatever the canonicalisation vocabulary
  produced. Retrieval quality would change, and that change needs
  measuring rather than assuming.
- Forcing property bags into the governed graph to ease the migration
  would undo ADR-0024's central decision, and must not be the answer.

## Rejected Alternatives

**Deprecate the legacy routes for a release instead of removing them.**
Rejected: they had already been deprecated since Architecture Freeze
v1.0, and deprecation had changed nothing. A deprecation that has already
failed to cause removal is not a plan.

**Keep the legacy tables and stop writing to them.** Rejected because it
leaves a queryable store of ungoverned claims in the database with no
owner and no reader - the worst of both, since anybody with SQL access
still finds it and has no way to know it was never reviewed.

**Migrate the legacy rows into the governed graph.** Rejected outright.
Every governed edge requires an approving review; there is none. Creating
synthetic approvals would attribute judgements to nobody and defeat the
entire point of the governed model.

**Retire the Canonical Facts lineage in this milestone too.** Rejected
because it is demonstrably in use: `structured_retrieval_service` reads
it through `GraphQueryRepository`, and the Engineering Engine reads that.
"Only remove code proven unused" is the instruction, and this is proven
*used* - an architecture test now asserts that it still is, so the day it
stops being read is a day this repository notices.

**Return `410 Gone` from the retired routes.** Rejected: it keeps a URL
alive whose only honest answer is that the data behind it should never
have been served, and it is a route to maintain forever. The frontend
route that engineers actually use survives and now serves governed
knowledge, which is the compatibility that matters.

## Related

- [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) - the
  decision this milestone finally satisfies in full.
- [ADR-0009](0009-legacy-knowledge-graph-isolation.md) - the isolation
  that held the line until a replacement existed. Now superseded in
  practice: there is nothing left to isolate.
- [ADR-0024](0024-governed-knowledge-graph-as-projection.md) - the
  governed graph that made retirement possible.
- `docs/architecture/knowledge_graph.md` §2 - the current graph
  inventory.
