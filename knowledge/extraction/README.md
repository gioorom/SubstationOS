# Extraction Pipeline

This document specifies how SubstationOS turns an engineering document into
knowledge a Project's own Knowledge Graph is allowed to trust. It is the
implementation of the methodology defined in
[`../protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`](../protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md)
— the constitution — and must never contradict it (see
[`../README.md`](../README.md), "Governing rule"). Every prompt in
`prompts/`, every template in `templates/`, and every manifest in
`manifests/` exists to enforce what is written here. If any of those files
ever appears to contradict this README, this README wins for matters of
pipeline mechanics; if this README ever appears to contradict the Protocol,
the Protocol wins and this file is corrected — per `CLAUDE.md` §11 ("when
code and documentation disagree, that is a bug").

## 1. Purpose

An HV/MV substation is described across dozens to hundreds of PDFs per
project: single-line diagrams, functional/wiring schematics, cable
schedules, protection settings, commissioning procedures, civil drawings.
These documents are authoritative, dense, cross-referencing, and frequently
**inconsistent with each other** (different revisions, different disciplines,
occasional drafting errors). SubstationOS's Digital Twin is only as good as
its ability to turn that corpus into a queryable model without silently
discarding nuance, inventing facts, or resolving disagreements a machine has
no authority to resolve.

This pipeline exists to do that turning **safely**: every fact that survives
to the canonical stage is provably traceable back to an exact document and
page, was never inferred, and — where two documents disagree — was resolved
by a named engineer, not by an algorithm.

## 2. The complete workflow

**Aligned to Architecture Freeze v1.0.** This workflow describes the
*routine* path a document takes: one Project's engineering document,
processed into that Project's own knowledge. It is not the path by which
the shared Canonical Domain vocabulary itself grows — see
[§2.1](#21-how-this-relates-to-the-canonical-knowledge-protocols-own-lifecycle)
for exactly how the two relate; nothing below contradicts the Canonical
Knowledge Protocol, but earlier wording in this file blurred the two paths
together, and that is corrected here.

```
Engineering Document
      ↓  (1)
Raw Extraction
      ↓  (2)
Engineering Review
      ↓  (3)
Project Canonical Knowledge
      ↓  (4)
Domain Mapping
      ↓  (5)
Project Knowledge Graph
      ↓  (6)
Query Services
      ↓  (7)
Application
```

### Stage 1 — Engineering Document

The source of truth: a PDF, Excel sheet, DWG drawing, image, or other
supported document family (see
`docs/architecture/project_intelligence_architecture.md` §3), living in a
Project's Document Repository under `storage/documents/`. Never modified by
this pipeline. A document is never "consumed" or deleted — it remains the
permanent reference every downstream fact points back to.

### Stage 2 — Raw Extraction

An AI session reads one source document, using one prompt from
[`prompts/`](prompts/) at a time (one prompt per knowledge category — an
extraction pass for "equipment" does not also extract "signals"). The
output is a Markdown file per category, following the matching template
from [`templates/`](templates/), written into
[`outputs/raw/`](outputs/raw/README.md). Every entry starts in review state
`RAW`, per the Canonical Knowledge Protocol §6.

This stage produces **candidate** knowledge only, scoped to one Project. It
is exhaustive but unreviewed, and it is explicitly disallowed from
resolving any ambiguity — see [§4 Extraction Rules](#4-extraction-rules).
Nothing in `outputs/raw/` is ever cited by the domain model, and nothing
this stage produces ever creates or edits a Canonical Domain concept — see
[§2.1](#21-how-this-relates-to-the-canonical-knowledge-protocols-own-lifecycle).

### Stage 3 — Engineering Review

A qualified engineer reads the raw extraction alongside the source document
and assigns each entry a formal review state, per the Canonical Knowledge
Protocol §6:

- `UNDER_REVIEW` — evaluation has started but not reached a verdict (most
  often because an open question is unresolved).
- `APPROVED` — the entry accurately reflects the source, possibly after a
  correction (the correction is recorded; the original extracted text
  stays visible).
- `REJECTED` — the entry should not proceed (mis-extraction, inferred
  rather than stated, or otherwise invalid).

Reviewed files are written to [`outputs/reviewed/`](outputs/reviewed/README.md),
preserving the same filename as the raw file they originate from so the two
can always be diffed. `SUPERSEDED` is not assigned at this stage — it only
ever applies to a fact that was already `APPROVED` and is later replaced
(Protocol §6, §9).

Review is mandatory for every extracted statement, not spot-checked. A file
with any entry still in `RAW` or `UNDER_REVIEW` has not completed this
stage.

### Stage 4 — Project Canonical Knowledge

Once `APPROVED`, an engineer (or a designated knowledge owner) makes the
**project-level canonicalization decision**: when multiple documents, or
multiple reviewed entries *within this Project*, describe the same
real-world entity, exactly one canonical record is produced for that
Project, with every contributing source still listed in its `References`
field. Conflicting values are never silently averaged, picked by recency,
or picked by confidence score — the decision and its reasoning are written
into the template's `Canonical decision` field by name, per the Protocol's
Conflict Resolution workflow (§7 of that document).

Canonical files live in [`outputs/canonical/`](outputs/canonical/README.md).
This canonicalization is scoped to one Project — it is a distinct
step from, and never modifies, the shared Canonical Domain
(`app/domain/ontology/**`). See
[§2.1](#21-how-this-relates-to-the-canonical-knowledge-protocols-own-lifecycle).

### Stage 5 — Domain Mapping

Project canonical facts are mapped onto **existing** Canonical Domain
concepts — `EquipmentDefinition`, `AttributeDefinition`, and (once
implemented) the Relationship Vocabulary and Domain Constraints described
in `docs/architecture/project_intelligence_architecture.md` §1 — by
reference (`id`), never by authoring a new concept. This is a modelling
step: *which existing canonical concept does this project fact
instantiate?*

If a project fact does not match any existing canonical concept, this stage
does **not** invent one. The fact is recorded with an explicit open
question (no matching canonical concept) and carried forward unmapped —
extending the Canonical Domain is a separate, rare, deliberately
human-governed process (§2.1), never an automatic consequence of mapping
one project's facts.

### Stage 6 — Project Knowledge Graph

Successfully mapped, approved, project-canonical facts become nodes and
edges in that Project's Knowledge Graph — conceptually specified in
`docs/architecture/project_intelligence_architecture.md` §7. This is the
**only** stage output the next stage may query. Every node and edge still
carries its full traceability chain back through Stages 1–4 (§6 below).

### Stage 7 — Query Services

The Semantic Query Engine (`docs/architecture/project_intelligence_architecture.md`
§8) answers natural-language questions by querying the Project Knowledge
Graph — never by asking an AI model to recall or infer an answer. Every
result carries the traceability record (Project, Document, Drawing, Page,
Revision, Confidence) forward to the next stage.

### Stage 8 — Application

The AI Assistant and any other consuming surface present query results to
the user, always with their traceability record attached. Out of scope for
`knowledge/` itself.

### 2.1 How this relates to the Canonical Knowledge Protocol's own lifecycle

The Canonical Knowledge Protocol (§2 of that document) defines a *ten*-stage
lifecycle ending in `Domain Concepts → Ontology → Attribute Definitions →
Equipment Definitions → Python Domain Model → Application`. That is
**not** a contradiction of the eight-stage workflow above — it is a
different, rarer path, and both share the same first three stages
(Engineering Document → Raw Extraction → Engineering Review) exactly.

- **The path above (routine, this file):** taken every time a document is
  processed for a Project. It ends by *mapping* facts onto the Canonical
  Domain as it already exists, and by populating that Project's own
  Knowledge Graph. It never authors new canonical YAML.
- **The Protocol's own path (rare, `CANONICAL_KNOWLEDGE_PROTOCOL.md` §2):**
  taken only when Stage 5 (Domain Mapping) surfaces a genuinely new
  concept with no existing canonical match, and a human deliberately
  decides the Canonical Domain itself should be extended. That decision is
  never made inside a routine extraction session — it is its own,
  separately governed process, using the Protocol's Stages 5–10 verbatim.

An earlier version of this file described only one lifecycle, ending in
`Ontology → YAML Definitions → Python Domain Model`, as if that were the
routine outcome of processing project documents. It was not: routine
project extraction was always meant to enrich one Project's knowledge, not
to author shared vocabulary. That conflation is what this section, and the
renamed Stages 4–7 above, correct.

## 3. Directory responsibilities

### `prompts/`

One Markdown file per knowledge category. Each file is a self-contained set
of instructions for an AI extraction session: what to look for, what fields
to fill, what counts as in-scope for that category, and a restatement of the
rules in §4 that matter most for that category. A prompt file is read
**before** an extraction session, not during — it is the brief, not a
running commentary.

Categories, and what each one is scoped to:

| Prompt | Extracts |
|---|---|
| `equipment.md` | Physical apparatus: transformers, breakers, disconnectors, instrument transformers, relays, cabinets — anything that would get an `EquipmentDefinition`. |
| `attributes.md` | Reusable characteristics of equipment: ratings, dimensions, settings — anything that would get an `AttributeDefinition`. |
| `relationships.md` | How equipment connects to, contains, feeds, or depends on other equipment. |
| `signals.md` | Measurements, commands, status/position feedback — analog and digital I/O points named on functional schematics. |
| `protections.md` | Protection functions, ANSI device numbers, trip/alarm logic, interlocks. |
| `cables.md` | Cable schedules: identifiers, routing, cross-section, conductor count, terminations. |
| `commissioning.md` | Factory and site test procedures, acceptance criteria, commissioning steps. |
| `civil.md` | Civil works: buildings, foundations, fencing, drainage, oil containment. |
| `glossary.md` | Terminology, abbreviations, and aliases (including non-English field terms, e.g. Italian) used across the document set. |

### `templates/`

One Markdown template per record type produced during extraction and
review. A template is a **blank shape with instructions**, not an example —
every field carries a one-line description of what belongs in it and what
does not. Extraction and review output is always a filled copy of a
template, never a freeform note.

### `outputs/raw/`, `outputs/reviewed/`, `outputs/canonical/`

The three staged output directories, one per pipeline stage 2–4. Each has
its own README describing exactly what may and may not be written into it.
See [§5 Naming Conventions](#5-naming-conventions) for how files are
organized within them.

### `manifests/`

One manifest per source PDF processed through the pipeline, regardless of
how many knowledge categories were extracted from it. The manifest is the
audit record: which document, which revision, who reviewed it, when, and
what extraction categories have been run against it. See
[`manifests/README.md`](manifests/README.md) for the full specification.

## 4. Extraction Rules

These rules are absolute. A prompt, a template, or a reviewer that violates
one of these has a bug, per `CLAUDE.md` §14's standard for the codebase
itself.

1. **No AI inference is allowed.** An extraction may only record what a
   document states explicitly, in the terms the document uses. If a value
   must be calculated, interpreted, or read "between the lines" of a
   diagram to be produced, it is not an extraction — it does not go in
   `outputs/raw/`.
2. **Every statement must reference its source document.** By file name or
   drawing code, exactly as printed on the document's own title block —
   never abbreviated or renamed by the extractor.
3. **Every statement must reference a page number.** Use the page number
   printed in the document's own title block (its "Foglio" or equivalent),
   not the PDF file's page index, since the two can differ (cover sheets,
   scanned inserts). If a document has no internal page numbering, state
   that explicitly and use the PDF page index as a documented fallback.
4. **Uncertainty must be explicitly marked.** Every extracted statement
   carries a `Confidence` value of `High`, `Medium`, or `Low` (see each
   template's `Confidence` field for the precise criteria). A statement with
   no clear confidence is `Low`, never omitted.
5. **Assumptions are forbidden.** If a fact is not explicitly stated, the
   corresponding field is filled with the literal text `Not specified` — it
   is never left blank (which reads as "not extracted yet") and never
   filled with a plausible-sounding guess.
6. **Duplicated knowledge must not be merged automatically.** If the same
   entity appears to be described in two places — even within the same
   document, even by the same extraction pass — both extractions are kept
   as separate entries with their own source references. Merging is a
   Stage 4 (Project Canonical Knowledge) decision made by a named engineer,
   never an automatic step of Stage 2 or Stage 3.
7. **Conflicts between documents must be preserved for review.** If two
   documents state different values for what might be the same fact, both
   values, both sources, and the apparent conflict are recorded explicitly
   — most naturally as an `Open questions` entry — and carried forward
   unresolved into Stage 3. No extraction step ever picks a "winner"
   between conflicting sources.

## 5. Naming Conventions

**Document identifiers.** Use the drawing code exactly as printed on the
document's own title block (e.g. `AA00-XXX-YYY-ZZ00.1.000000-0-S-025`) as
the stable identifier for that document everywhere in this pipeline —
manifest file name, raw/reviewed output folder name, and every `Source
document` field.

**Manifests.** `manifests/<document-code>.md`, one file per source PDF. See
[`manifests/README.md`](manifests/README.md).

**Raw and reviewed outputs.** Organized **by document, then by category**,
because Stage 2 and Stage 3 work one document at a time:

```
outputs/raw/<document-code>/<category>.md
outputs/reviewed/<document-code>/<category>.md
```

Example: `outputs/raw/AA00-XXX-YYY-ZZ00.1.000000-0-S-027/protections.md`.
The reviewed file is always the same relative path under `reviewed/` as its
raw counterpart under `raw/`, so the two can be diffed directly to see
exactly what review changed.

**Canonical outputs.** Organized **by category, then by canonical entity
id** — not by document — because Stage 4 (Project Canonical Knowledge)
output describes real-world entities, which may be attested by several
documents at once:

```
outputs/canonical/<category>/<entity-id>.md
```

Example: `outputs/canonical/equipment/power-transformer-tr-rosso.md`. The
`entity-id` is a short, stable, kebab-case slug chosen by the reviewer at
canonicalization time; once published, per `CLAUDE.md` §16, it is a
contract and is not renamed casually.

**Categories.** Always the nine names used by the prompt files:
`equipment`, `attributes`, `relationships`, `signals`, `protections`,
`cables`, `commissioning`, `civil`, `glossary`. The same nine names are used
as sub-folder names under `outputs/canonical/`.

## 6. Traceability Philosophy

Every fact in the Project Knowledge Graph must answer, without ambiguity:
*"how do we know this, and how sure are we?"*

That answer is a chain, and every link in the chain must be inspectable by a
human, forever:

```
Project Knowledge Graph node/edge (Stage 6)
  → cites →  Project canonical entity file (Stage 4, outputs/canonical/)
                → cites →  Reviewed entry (Stage 3, outputs/reviewed/)
                              → cites →  Raw extraction (Stage 2, outputs/raw/)
                                            → cites →  Source document + page (Stage 1)
```

(On the separate, rare canonical-domain-extension path — §2.1 — the
equivalent chain ends one stage further, in a YAML field under
`app/domain/ontology/`, per the Canonical Knowledge Protocol §2.)

Nothing is permitted to break this chain. A canonical entity with no
`References` back to a reviewed entry, or a reviewed entry with no
`Engineering review` verdict, is an incomplete record, not a shortcut — the
pipeline has no concept of "trust it anyway."

This is the same principle `CLAUDE.md` §16 states for the ontology itself
("Auditability of the domain model... so domain experts can review it
without reading Python") pushed one layer further upstream: a domain expert
must be able to audit not just the ontology, but *why the ontology says what
it says*, using nothing but Markdown files and the original PDFs.

Traceability is not a feature to add later. A record that cannot be traced
is not knowledge in this system — it is a draft, and it stays in
`outputs/raw/` or `outputs/reviewed/` until it can be.
