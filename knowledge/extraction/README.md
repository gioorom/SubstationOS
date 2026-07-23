# Extraction Pipeline

This document is the authoritative specification of how SubstationOS turns an
engineering PDF into knowledge the ontology is allowed to trust. Every prompt
in `prompts/`, every template in `templates/`, and every manifest in
`manifests/` exists to enforce what is written here. If any of those files
ever appears to contradict this README, this README wins — fix the other
file, per `CLAUDE.md` §11 ("when code and documentation disagree, that is a
bug").

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

```
Engineering PDF
      ↓  (1)
AI Extraction
      ↓  (2)
Engineering Review
      ↓  (3)
Canonical Knowledge
      ↓  (4)
Ontology
      ↓  (5)
YAML Definitions
      ↓  (6)
Python Domain Model
      ↓  (7)
Application
```

### Stage 1 — Engineering PDF

The source of truth. Lives in `storage/documents/`. Never modified by this
pipeline. A PDF is never "consumed" or deleted — it remains the permanent
reference every downstream fact points back to.

### Stage 2 — AI Extraction

An AI session reads one source PDF, using one prompt from
[`prompts/`](prompts/) at a time (one prompt per knowledge category — an
extraction pass for "equipment" does not also extract "signals"). The
output is a Markdown file per category, following the matching template from
[`templates/`](templates/), written into
[`outputs/raw/`](outputs/raw/README.md).

This stage produces **candidate** knowledge only. It is exhaustive but
unreviewed, and it is explicitly disallowed from resolving any ambiguity —
see [§4 Extraction Rules](#4-extraction-rules). Nothing in `outputs/raw/` is
ever cited by the domain model.

### Stage 3 — Engineering Review

A qualified engineer reads the raw extraction alongside the source PDF and
fills in the template's `Engineering review` field for every entry: confirm,
correct, reject, or flag as an open question. Reviewed files are written to
[`outputs/reviewed/`](outputs/reviewed/README.md), preserving the same
filename as the raw file they originate from so the two can always be
diffed.

Review is mandatory for every extracted statement, not spot-checked. A file
with any entry still lacking an `Engineering review` verdict has not
completed this stage.

### Stage 4 — Canonical Knowledge

Once reviewed, an engineer (or a designated knowledge owner) makes the
**canonicalization decision**: when multiple documents, or multiple
reviewed entries, describe the same real-world entity, exactly one canonical
record is produced, with every contributing source still listed in its
`References` field. Conflicting values are never silently averaged, picked
by recency, or picked by confidence score — the decision and its reasoning
are written into the template's `Canonical decision` field by name.

Canonical files live in [`outputs/canonical/`](outputs/canonical/README.md)
and are the **only** artifacts in `knowledge/` the next stage is allowed to
read from.

### Stage 5 — Ontology

Canonical knowledge is mapped onto SubstationOS's Electrical Ontology
concepts as defined in `CLAUDE.md` §4.3 (`app/domain/ontology/`):
`AttributeDefinition`, `EquipmentDefinition`, and their relationships. This
is a modelling step — deciding which canonical facts become which ontology
concepts — done by an engineer familiar with both the canonical knowledge
and the existing ontology, to avoid duplicating a concept that already
exists under a different name.

### Stage 6 — YAML Definitions

Ontology concepts are authored as YAML domain data, following the shapes
and rules in `CLAUDE.md` §7, under `app/domain/ontology/attributes/*.yaml`
and `app/domain/ontology/equipment_definitions/**/*.yaml`. Every field in
that YAML must be traceable to a canonical knowledge file, which is in turn
traceable to a source PDF and page. This is the first stage where this
pipeline's output touches version-controlled domain data — and, per
`CLAUDE.md` §16, once an `id` is published here it is a contract.

### Stage 7 — Python Domain Model

The existing Python domain layer (`AttributeDefinitionFactory`,
`EquipmentDefinitionFactory`, `AttributeCatalog`, `EquipmentDefinitionCatalog`,
`AttributeDefinitionValidator`, `EquipmentDefinitionValidator`, the
`*Engine` classes — all already implemented per `CLAUDE.md` §4.3) loads,
validates and serves the YAML definitions produced in Stage 6. This
pipeline does not modify that code; it only feeds it correct data.

### Stage 8 — Application

Routers, services, and eventually the Knowledge Graph and comprehension
engine consume the domain model. Out of scope for `knowledge/`.

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
   Stage 4 (Canonical Knowledge) decision made by a named engineer, never an
   automatic step of Stage 2 or Stage 3.
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
id** — not by document — because Stage 4 output describes real-world
entities, which may be attested by several documents at once:

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

Every fact in the eventual Knowledge Graph must answer, without ambiguity:
*"how do we know this, and how sure are we?"*

That answer is a chain, and every link in the chain must be inspectable by a
human, forever:

```
YAML field (Stage 6)
  → cites →  Canonical entity file (Stage 4, outputs/canonical/)
                → cites →  Reviewed entry (Stage 3, outputs/reviewed/)
                              → cites →  Raw extraction (Stage 2, outputs/raw/)
                                            → cites →  Source document + page (Stage 1)
```

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
