# ADR-0001: Project-Centric Architecture

## Status

Accepted.

## Context

SubstationOS serves many real, physically and legally distinct
installations — primary substations, transmission substations, and
potentially other engineering disciplines in the future (per
`docs/architecture/project_intelligence_architecture.md` §2). Every piece
of engineering knowledge the platform holds — a document, an extracted
fact, a graph node — describes one specific installation, never a
generality. The existing `Project` persistence model (`app/models/project.py`)
already implements identity (`id`, unique `code`), business metadata
(customer, EPC, location, status), and a `documents` relationship; the
existing `Document`, `ProjectEntity`, and `EntityRelation` models already
key their rows by `project_id`. `docs/ARCHITECTURE.md` already states, as a
"single source of truth" principle, that a document belongs to a project
via `project_id`.

What was not yet stated as a binding architectural rule, only as an
implementation convention, is that this boundary is absolute and that
nothing above it may hardcode assumptions about any specific project.

## Decision

SubstationOS is project-centric: every engineering fact, document, index
entry, and graph node belongs to exactly one Project, identified by its
stable `code`. No component in the pipeline — Document Classification, the
Engineering Index, Knowledge Extraction, the Project Knowledge Graph, or
the Semantic Query Engine — may reference a specific project by name, code,
or any other identifying value in its logic, prompts, or code. Project
identity is always runtime data flowing through the existing `project_id`
boundary, never a compile-time or prompt-time assumption.

## Consequences

- Enables scaling to thousands of projects without per-project code
  branches, special cases, or configuration files.
- Every new component built on top of this architecture must explicitly
  thread a Project scope through its inputs and outputs; a component that
  cannot state which Project it is operating on is a defect.
- Cross-project queries (e.g. "which projects use equipment type X") remain
  possible precisely because the boundary is explicit data, not implicit
  structure — a benefit of this decision, not a constraint it imposes.
- Requires closing the one place this boundary is currently ambiguous:
  `Document.project_id` is nullable, which does not yet distinguish "no
  project assigned" from "deliberately not project-scoped" — resolved
  conceptually by ADR-0005, with schema implementation left as future work.

## Rejected Alternatives

- **A single shared, global installation model.** Rejected because real
  installations are physically and legally distinct; a shared model would
  either force one substation's facts to leak into another's answers or
  require every query to carry ad hoc filtering logic reinvented at every
  call site instead of enforced once, structurally, at the data boundary.
- **Implicit project scoping via naming conventions or folder structure
  only** (e.g. inferring a project from a document's filename or upload
  path). Rejected because it cannot be validated, cannot be enforced by the
  data model, and invites exactly the "hardcoded project name" anti-pattern
  this architecture forbids — a convention silently violated is worse than
  no convention, because it looks safe until it isn't.
