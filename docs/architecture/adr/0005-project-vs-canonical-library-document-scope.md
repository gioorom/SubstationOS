# ADR-0005: Explicit PROJECT versus CANONICAL_LIBRARY Document Scope

## Status

Accepted. Implemented in the Project Lifecycle foundation milestone:
`app.domain.project.project_document_scope.DocumentScope` (`PROJECT` /
`CANONICAL_LIBRARY`) is now a first-class column (`documents.scope`,
default `PROJECT`) rather than an inference from a nullable
`project_id`. The upload endpoint (`POST /documents/upload`) rejects a
`PROJECT`-scoped upload without a `project_id`, and rejects a
`CANONICAL_LIBRARY`-scoped upload that supplies one. Everything else
this ADR anticipates for `CANONICAL_LIBRARY` governance (a separate
upload/review workflow, citation-only linkage into a Project's
knowledge) remains future work — this ADR ratifies only the scope
field and its Repository-rule enforcement at upload time.

## Context

Uploaded documents fall into two genuinely different categories: those
describing one specific real installation (functional schematics, cable
schedules, commissioning reports — the majority case) and those that are
reusable references shared across many projects (vendor manuals,
standards, internal specifications). `docs/architecture/project_intelligence_architecture.md`
§3 already treats Vendor Manuals and Standards differently from the other
document families for exactly this reason.

Today, `Document.project_id` is nullable. In practice this nullability is
being used, by accident of implementation rather than by deliberate design,
to represent "this document has no project." A nullable foreign key cannot
distinguish "not yet assigned" (an upload in progress, or an error) from
"deliberately global" (a vendor manual that will never have a project), and
it offers no way to query "every canonical-library document" as a
first-class concept.

## Decision

SubstationOS documents have an explicit, named scope:

- **`PROJECT`** — owned by exactly one Project; feeds that Project's
  Engineering Index and Project Knowledge Graph; requires a Project
  reference. This is the scope for every document family in
  `docs/architecture/project_intelligence_architecture.md` §3 except the
  two named next.
- **`CANONICAL_LIBRARY`** — reusable, owned by no single Project, governed
  by a separate process, and never a direct source for a Project Knowledge
  Graph node. It has no Project reference by design, not by nullable-field
  accident. A `CANONICAL_LIBRARY` document may be *cited* as corroborating
  context from within a Project's knowledge (per the Vendor Manuals
  treatment in §3 of the architecture document), but that citation points
  to the library document — it does not pull the library document into the
  Project's own scope.

A `PROJECT`-scoped document's Project reference becomes mandatory, not
optional; a `CANONICAL_LIBRARY`-scoped document's absence of one is an
explicit, intentional scope declaration.

## Consequences

- Delivered the schema change this ADR anticipated: `documents.scope`
  (`DocumentScope`, default `PROJECT`), with `project_id` conditionally
  required based on that scope, enforced at the upload endpoint.
- Enables clean, first-class queries and governance per scope (e.g. "list
  every canonical-library document," or restricting who may upload to
  `CANONICAL_LIBRARY` versus a specific Project) — the queries themselves
  remain future work; only the field and its upload-time invariant are
  delivered here.
- Removes the current architectural ambiguity between "unassigned" and
  "intentionally global" that the nullable field cannot express.
- Delivered as part of the Project Lifecycle foundation milestone, per
  `docs/architecture/project_intelligence_architecture.md`'s
  recommendation for Milestone 8 (Project Creation Workflow).

## Rejected Alternatives

- **Keep the nullable `project_id` as the de facto scope signal.** Rejected
  per this ADR's own reasoning above and per explicit direction at
  Architecture Freeze v1.0: nullability conflates "not yet set" with
  "intentionally scopeless," and cannot express future scope types beyond
  these two.
- **Model `CANONICAL_LIBRARY` documents as belonging to a synthetic
  "global" Project.** Rejected because it would force library documents
  through project-scoped machinery (Engineering Index, Project Knowledge
  Graph) that ADR-0001 and ADR-0002 establish specifically to be
  project-bounded — a synthetic global project would either need special-
  cased exemptions everywhere (recreating the hardcoding problem ADR-0001
  forbids) or would silently pollute project-scoped structures with
  non-project data.
