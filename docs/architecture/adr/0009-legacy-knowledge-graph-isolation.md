# ADR-0009: Legacy Knowledge Graph Isolation

## Status

Accepted.

## Context

`app/models/knowledge_graph.py` (`ProjectEntity`, `EntityRelation`,
`EntityType`, `RelationType`), `app/services/knowledge_graph.py`
(`ingest_document`, `get_or_create_entity`, `create_relation`, ...),
`app/routers/knowledge_graph.py` (`GET /projects/{id}/knowledge-graph`,
`GET /projects/{id}/entities`, `GET /projects/{id}/entities/{entity_id}`),
and `app/schemas/knowledge_graph.py` predate the governed pipeline this
project has built since Milestone 8 (Documents → Engineering Index →
Proposed Claims → Review Workflow → Canonicalization → Graph Builder →
Project Knowledge Graph → Graph Query). `ingest_document` extracts
entities with an AI provider and writes them directly into
`ProjectEntity`/`EntityRelation` — queryable graph storage — with no
review gate of any kind. This is a live violation of
[ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) ("Reviewed
Facts Only in the Queryable Project Knowledge Graph").

This violation has been known and consciously not remediated
throughout every milestone since the governed pipeline began — the
governed pipeline was built as a parallel, correct replacement rather
than a rewrite of the legacy path in place, precisely so that
ADR-0004's guarantee could be established for new work without first
having to solve AI-extraction review for the old path. Milestone 12
requires this to finally be traced and classified precisely rather
than left as tribal knowledge: is this code still used, by what, and
is it safe to remove?

Direct code tracing (not assumption — CLAUDE.md's "do not assume
similarly named files are equivalent" applies doubly to legacy code)
confirms: `app/routers/documents.py`'s `upload_document` endpoint calls
`ingest_document` directly on **every** PDF uploaded to a project,
wrapped in a `try`/`except` so upload succeeds even if extraction
fails, tracking the outcome in a `knowledge_graph_status` field. This
is not dead code. It cannot be deleted this milestone without removing
functionality the milestone is explicitly forbidden from touching
("do not introduce new extraction behavior" cuts both ways — it also
means not silently removing existing behavior).

Two further root-scratch files were traced as part of this inventory:
`migrate_project_documents.py` (a standalone, ad hoc `sqlite3`
column-backfill script, not imported by any application code,
superseded in spirit by Alembic — see [ADR-0008](0008-database-migration-governance.md))
and `test_claude.py`/`test_ingest.py` (manual smoke scripts exercising
`extract_entities`/`ingest_document` directly; not under `pytest.ini`'s
`testpaths = tests`, so never auto-discovered by the test suite, but
still meaningful manual tooling for the still-active legacy path).

## Decision

### 1. The legacy Knowledge Graph code is retained, not deleted, and marked deprecated

`app/models/knowledge_graph.py`, `app/services/knowledge_graph.py`,
`app/routers/knowledge_graph.py`, and `app/schemas/knowledge_graph.py`
all now carry a module-level docstring stating: that the file is
legacy, why (it predates the governed pipeline and violates ADR-0004
by design), and who its remaining consumers are
(`documents.py::upload_document`, and the router itself). The router's
FastAPI tag changed from `"Knowledge Graph"` to
`"Knowledge Graph (Legacy)"`, and it now declares `deprecated=True` —
visible in the generated OpenAPI schema and Swagger UI, verified by
`tests/api/test_openapi_integrity.py::test_legacy_router_is_marked_deprecated`.

### 2. The governed graph path may never import legacy Knowledge Graph code, enforced by an automated test

`tests/architecture/test_bounded_context_dependencies.py::test_governed_graph_path_does_not_import_legacy_knowledge_graph_code`
statically checks (via Python's `ast` module — see
[system_overview.md](../system_overview.md) / the test file itself)
that no file under Graph Builder, Project Knowledge Graph, or Graph
Query (domain, infrastructure, service, or router layers) imports
`app.models.knowledge_graph`, `app.services.knowledge_graph`,
`app.routers.knowledge_graph`, or `app.schemas.knowledge_graph`. This
is the enforcement mechanism the model file's own docstring refers to.

### 3. URL namespaces are deliberately separate, not renamed to "fix" the near-collision

The legacy router serves bare `/projects/{id}/knowledge-graph`,
`/projects/{id}/entities`, and `/projects/{id}/entities/{entity_id}`.
The governed routers serve `/projects/{id}/knowledge-graph/nodes...`
(Project Knowledge Graph, Milestone 11.2) and `/projects/{id}/graph/...`
(Graph Query, Milestone 11.3) — different namespaces, confirmed by
direct route inspection to have zero exact `(path, method)` collisions
(`tests/api/test_openapi_integrity.py::test_legacy_and_governed_knowledge_graph_paths_do_not_collide`).
The near-collision between `/entities` and `/graph/entities` is
genuinely confusing to a reader of the OpenAPI schema, but Milestone
12's own instruction is explicit: "do not rename public endpoints
casually... only change when there's clear inconsistency... prefer
documenting non-critical inconsistencies over breaking changes." This
is documented here, and in both routers' docstrings, rather than
silently ignored or fixed via a rename that would break any existing
caller of the legacy endpoints.

### 4. Nothing legacy is deleted this milestone

`migrate_project_documents.py` is retained as a superseded-but-harmless
migration tool (not imported by application code, not run by any
process, kept for historical/manual reference). `test_claude.py` and
`test_ingest.py` are retained as manual smoke tooling for the
still-active legacy extraction path — neither is proven dead, and per
Milestone 12's own Legacy Handling Rules, only *proven-unreferenced*
code may be removed, and only with import/reference analysis and
tests. No file met that bar this milestone.

## Consequences

**Easier:**
- Any future engineer reading `app/models/knowledge_graph.py` or its
  router immediately sees, in the module docstring itself, that it is
  legacy, why, and what still depends on it — no need to reconstruct
  this history from git blame or tribal knowledge.
- The forbidden-dependency test makes ADR-0004's boundary
  self-enforcing going forward: a future contributor cannot
  accidentally wire the governed pipeline into the unreviewed legacy
  path without a failing test catching it immediately.
- OpenAPI consumers (Swagger UI, generated clients) now see the legacy
  endpoints marked `deprecated` automatically, rather than
  indistinguishable from current, governed endpoints.

**Harder / unresolved:**
- The core violation (unreviewed AI extraction written directly to
  queryable storage) is not fixed — only isolated, documented, and
  proven not to spread. `upload_document` still calls
  `ingest_document` on every upload. Remediating this properly (either
  routing legacy extraction through Proposed Claims/Review Workflow,
  or removing it once callers migrate to the governed pipeline) is
  real product work, not a hardening task, and is recorded as
  remaining technical debt for a future milestone.
- The `/entities` vs `/graph/entities` naming proximity remains
  genuinely confusing in the OpenAPI schema — accepted as documented
  debt rather than a breaking rename.

## Rejected Alternatives

- **Delete the legacy code now.** Rejected: `documents.py`'s upload
  flow depends on it directly; deleting it would remove working
  product functionality (AI-assisted entity extraction on upload),
  which this hardening milestone is explicitly forbidden from doing.
- **Merge the legacy path into the governed pipeline this milestone**
  (e.g. route `ingest_document`'s output through Proposed Claims).
  Rejected: this is new product behavior/redesign, explicitly out of
  scope ("do not perform open-ended redesign... do not introduce new
  extraction behavior").
- **Rename the legacy endpoints to reduce the `/entities` naming
  collision risk.** Rejected: a public API rename is a breaking change
  for any existing caller, and the milestone's own API Consistency
  Audit rules require "no architectural boundary break... compatibility
  impact documented" before any such rename — the near-collision is
  real but not "clear enough" to justify breaking backward
  compatibility for it today.
