# Architecture Freeze v1.0 — Checklist

**This checklist does not declare Architecture Freeze v1.0 complete.** It
records the actual state of the repository against the architecture
defined in `project_intelligence_architecture.md`, the
`knowledge/protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`, and
`knowledge/extraction/README.md`, as of the date this checklist was last
updated. A freeze may only be declared once every item below is `READY`,
by whoever owns SubstationOS's architecture — not by this document.

**Status legend**

- `READY` — the requirement is implemented in the repository today, and
  matches the documented architecture. Verifiable, not aspirational.
- `PARTIAL` — the requirement is designed (and may be partially
  implemented), with a clear, unblocked path to finishing it. Nothing
  unresolved is preventing work from starting or continuing.
- `BLOCKED` — a decision, dependency, or prerequisite is genuinely
  unresolved, and must be settled before implementation can even be
  scheduled with confidence.

Every `PARTIAL` and `BLOCKED` item is explained below with what exists,
what is missing, and — for `BLOCKED` items — what specifically must be
resolved first.

---

## Checklist

| # | Item | Status |
|---|---|---|
| 1 | Project-centric boundaries | `PARTIAL` |
| 2 | Canonical Domain / Project Knowledge separation | `PARTIAL` |
| 3 | Document ownership (`PROJECT` / `CANONICAL_LIBRARY`) | `READY` |
| 4 | Engineering Index / Project Knowledge Graph separation | `PARTIAL` |
| 5 | Mandatory review gate | `PARTIAL` |
| 6 | Traceability | `PARTIAL` |
| 7 | Versioning | `PARTIAL` |
| 8 | AI replaceability | `READY` |
| 9 | No project-specific hard-coding | `PARTIAL` |
| 10 | Scalability assumptions | `PARTIAL` |

**Overall: NOT READY for Architecture Freeze v1.0.** No item is `BLOCKED`
any longer — the Project Lifecycle foundation milestone accepted and
implemented ADR-0005 (item 3), removing the one open decision that had no
unblocked path forward. The remainder are `PARTIAL` — designed, partly
implemented, with the single highest-priority gap being item 5 (see
below). Two items, AI replaceability and Document ownership, are
genuinely `READY` today.

---

## 1. Project-centric boundaries — `PARTIAL`

**Implemented:** `Project` model (`app/models/project.py`) with unique
`code`, business metadata, and status; `Document`, `ProjectEntity`, and
`EntityRelation` all key their rows by `project_id`; routers scope reads
and writes by project. ADR-0001 formally records this as a binding
architectural rule, not just an implementation convention. The Project
Lifecycle foundation milestone added an explicit **record lifecycle**
(`app.domain.project.project_lifecycle.ProjectLifecycleState`:
`DRAFT`/`ACTIVE`/`ARCHIVED`/`DELETED`, soft delete only, enforced by a
strict state machine) on top of the pre-existing, orthogonal delivery-
phase `ProjectStatus`, plus a `ProjectRepository` port, application
services (`CreateProject`, `ActivateProject`, `ArchiveProject`,
`RestoreProject`, `DeleteProject`, `UpdateMetadata`, `GetProject`,
`ListProjects`), and REST endpoints, following the ontology bounded
context's reference pattern (`CLAUDE.md` §4.3). Project creation
provisions the Project record only — no Document Repository, Engineering
Index, Project Knowledge Graph, or Traceability infrastructure exists yet
to actually provision (see items 4, 5, 6), so today "provisioning" means
the Project's `id`/`code` exist as the scoping key those future
components will key off, per ADR-0001.

**Not implemented:** No automated check exists anywhere in the codebase
or CI that would catch a future component hardcoding a specific project's
name, code, or identifying data. Document ownership itself is no longer a
gap here — see item 3, now `READY`.

## 2. Canonical Domain / Project Knowledge separation — `PARTIAL`

**Implemented:** `app/domain/ontology/**` is structurally isolated from
`apps/backend`'s project-scoped models by `CLAUDE.md`'s dependency rule —
the domain layer has zero knowledge of `Project`, `Document`, or any
project-scoped concept. `EquipmentDefinition` and `AttributeDefinition`
exist as real, validated, versioned-by-git YAML data. ADR-0003 formally
records the separation as a binding rule.

**Not implemented:** Relationship Vocabulary and general Domain Constraints
(beyond the existing uniqueness/shape validators) are **designed, not
implemented** as canonical-domain concepts. More importantly, no runtime
enforcement mechanism exists: `ingest_document`'s AI extractor assigns
free-text `EntityType` values with no reference to, or validation against,
the canonical `EquipmentDefinition`/`AttributeDefinition` catalogs at all.
The separation is real at the code-layering level; it is not yet enforced
at the data-flow level.

## 3. Document ownership (`PROJECT` / `CANONICAL_LIBRARY`) — `READY`

**Implemented:** ADR-0005 is `Accepted`. `documents.scope`
(`app.domain.project.project_document_scope.DocumentScope`: `PROJECT` /
`CANONICAL_LIBRARY`, default `PROJECT`) is a first-class column, not an
inference from `Document.project_id` being null. `POST /documents/upload`
enforces the invariant at the boundary: a `PROJECT`-scoped upload without
a `project_id` is rejected (422), and a `CANONICAL_LIBRARY`-scoped upload
that supplies one is rejected (422). Uploads to a `PROJECT`-scoped,
non-mutable (`ARCHIVED`/`DELETED`) project are also rejected (409), per
the Project Lifecycle's read-only rule.

**Not implemented:** `CANONICAL_LIBRARY`-specific governance (a separate
review/upload workflow, restricting who may upload to it) and the
citation-only linkage of library documents into a Project's knowledge
(`project_intelligence_architecture.md` §3's Vendor Manuals treatment)
remain future work — this item covers only the scope field and its
upload-time invariant.

## 4. Engineering Index / Project Knowledge Graph separation — `PARTIAL`

**Implemented:** Nothing. The Project Knowledge Graph's storage and query
layer (`app/models/knowledge_graph.py`, `app/services/knowledge_graph.py`,
`app/routers/knowledge_graph.py`) exists and works, but today it is fed
directly by unreviewed extraction — see item 5 — which is exactly the
Engineering Index's role, misapplied to the Graph's storage.

**Not implemented:** The Engineering Index itself does not exist as a
distinct concept anywhere in the codebase — no model, no service, no
router. ADR-0002 and `project_intelligence_architecture.md` §5 fully
specify what it should be. This is designed, zero-percent built, with a
clear (if substantial) implementation path.

## 5. Mandatory review gate — `PARTIAL`, highest-priority gap

**This is the most important open item in this checklist and is
deliberately not fixed by this task.**

**Implemented:** The Canonical Knowledge Protocol fully specifies the
review-state machine (`RAW`/`UNDER_REVIEW`/`APPROVED`/`REJECTED`/
`SUPERSEDED`) and the mandatory-review principle. `EntityRelation` has a
bare `confidence: float` field.

**Not implemented, and currently violated:** `app/services/knowledge_graph.py`'s
`ingest_document` function **writes AI-extracted entities and relationships
directly into the queryable graph storage, with no engineering review gate
of any kind.** There is no review-state field, no reviewer field, no review
date, and no code path that could block an unreviewed fact from being
returned by a query. This is a direct, currently-active violation of
ADR-0004, and it is preserved here explicitly, not silently described as
implemented or fixed — per this task's own instruction, it is not
remediated in this pass.

## 6. Traceability — `PARTIAL`

**Implemented:** `Document.revision` exists as a field. `EntityRelation`
and `ProjectEntity` carry a `source_document` reference and a
`confidence` float. The full 11-field Mandatory Metadata schema is fully
specified in `CANONICAL_KNOWLEDGE_PROTOCOL.md` §4, and
`project_intelligence_architecture.md` §9 maps it onto the Project scope.

**Not implemented:** Drawing Number (as distinct from filename), Discipline,
per-fact Page, Extraction Session, Reviewer, Review Date, and Canonical
Version have no corresponding fields anywhere in the current persistence
model. An answer generated today could not, in practice, supply most of
the six fields §9 requires.

## 7. Versioning — `PARTIAL`

**Implemented:** `CANONICAL_KNOWLEDGE_PROTOCOL.md` §9 fully specifies
per-entity canonical versioning (Version 1, Version 2+, `Supersedes`/
`Superseded by` links, permanent retention). No corresponding field or
mechanism exists in the persistence model today (no `canonical_version`,
no supersession links, on `ProjectEntity` or elsewhere).

**A distinct sub-question, now a documented extension point rather than
undesigned:** how the **Canonical Domain itself** (`app/domain/ontology/**`,
as a whole package) should be versioned — so that a Project can be bound,
at creation, to a specific version of the vocabulary it instantiates (per
`project_intelligence_architecture.md`'s Milestone 8 recommendation 1).
The Project Lifecycle foundation milestone added
`Project.canonical_domain_version` (a plain string, defaulting to the
documented sentinel `UNVERSIONED_CANONICAL_DOMAIN = "unversioned"` in
`app.domain.project.project_models`) as the binding point every Project
now carries — but the actual versioning *scheme* (semantic version, git
tag, dated release, ...) for `app/domain/ontology/**` itself is still not
designed. Project-knowledge versioning (the Protocol's §9) remains
`PARTIAL` in the sense used throughout this checklist; Canonical Domain
versioning has moved from no field existing at all to a real, typed field
with an explicit "not yet versioned" sentinel — still `PARTIAL`, no longer
`BLOCKED`-adjacent. Choosing the actual scheme should still be resolved,
likely via its own ADR, before Milestone 8 is considered complete.

## 8. AI replaceability — `READY`

**Note (EPIC 31.1):** the modules named in this item were deleted with
the legacy Knowledge Graph path; the governed equivalent is
`app/infrastructure/llm/**`. The text below is the freeze-time record and
is left unedited.

**Implemented:** `app/services/ai/base.py` defines an `AIProvider` ABC
port; `app/services/ai/claude_provider.py` is a real, working adapter
against it. This is the actual swappable seam ADR-0006 requires, and it is
already used by the current (if not-yet-review-gated) extraction pipeline.
Only one adapter (Claude) exists today, but the port's existence and
correct use is what this item verifies — adding a second provider is
additive work, not architectural rework.

## 9. No project-specific hard-coding — `PARTIAL`

**Implemented / verified:** No hardcoded project name, code, or
installation-specific identifier was found anywhere in the reviewed
codebase (`app/services/**`, `app/routers/**`, `app/models/**`). The
literal requirement — "never hardcode project-specific assumptions" — is
met.

**A related, narrower gap:** `app/services/topology/transformer_bay.py`
hardcodes one specific equipment **topology template** (a transformer bay
plus three protection relays) and its expected aliases. This is not a
project-specific hardcoding (it names no project), but it is a hardcoded
*engineering pattern* that limits generalization across future disciplines
— relevant to item 10 (Scalability) more than to this item strictly, but
recorded here since it is the closest thing to a hardcoding concern found.

## 10. Scalability assumptions — `PARTIAL`

**Implemented:** `project_intelligence_architecture.md` §10 documents a
specific, named mechanism for each of the five required scalability
properties (thousands of projects, millions of facts, future document
types, future AI models, future disciplines).

**Not implemented / not validated:** None of the five mechanisms have been
implemented in a form that could be load-tested. `services/topology/*`'s
single hardcoded topology template (see item 9) is a concrete example of
something that would need to generalize into a data-driven pattern library
before "future engineering disciplines without architectural redesign"
could be considered demonstrated rather than merely designed.

---

## Blockers before Architecture Freeze v1.0

In priority order:

1. **Close the mandatory review gate violation (item 5).** Until
   `ingest_document` stops writing directly into queryable graph storage,
   every other traceability and versioning guarantee in this checklist is
   moot — an unreviewed fact with perfect metadata is still an unreviewed
   fact.
2. **Design Canonical Domain versioning (item 7's open sub-question).**
   Needed before Milestone 8 can safely bind a Project to a specific
   vocabulary version. `Project.canonical_domain_version` now exists as
   the binding field; the scheme it should hold values from is still
   undecided.
3. **Build the Engineering Index (item 4)** as the landing zone that makes
   closing item 1 possible without losing the fast-browsability benefit
   ADR-0002 exists to preserve.
4. **Implement the Mandatory Metadata fields (item 6)** — Drawing Number,
   Discipline, per-fact Page, Extraction Session, Reviewer, Review Date,
   Canonical Version — so that traceable answers are actually possible in
   practice, not just in specification.

**Resolved by the Project Lifecycle foundation milestone:** ADR-0005
acceptance and implementation (previously blocker #2) — see item 3, now
`READY`.

## Known documentation debt (not blocking, but tracked)

- `docs/decisions/0005-electrical-ontology.md` remains an empty file at a
  competing location/numbering sequence to `docs/architecture/adr/`. Needs
  reconciliation (move, retire, or formally adopt as a second sequence with
  a stated reason) in a future pass.
- `knowledge/extraction/outputs/{raw,reviewed,canonical}/README.md` and the
  extraction templates under `knowledge/extraction/templates/` still use
  the earlier informal review vocabulary (`Confirmed`/`Corrected`/
  `Rejected`/`Open question` and `Pending`) rather than the formal
  `RAW`/`UNDER_REVIEW`/`APPROVED`/`REJECTED`/`SUPERSEDED` states now used in
  `knowledge/extraction/README.md`. This task's explicit scope was limited
  to `knowledge/extraction/README.md`; the outputs' READMEs and templates
  were intentionally left unedited and should be aligned in a follow-up
  pass, or they will read as contradicting the file that governs them.
