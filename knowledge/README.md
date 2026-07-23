# Knowledge — SubstationOS Knowledge Extraction System

This directory is the **front door** of SubstationOS's Digital Twin. It is where
raw engineering documentation (PDF single-line diagrams, functional schematics,
cable schedules, commissioning procedures) becomes governed, traceable,
machine-usable knowledge — before a single line of that knowledge is allowed to
enter the Python domain model described in `CLAUDE.md`.

`knowledge/` is **not code**. It contains no Python and no YAML domain
definitions. It contains the methodology, prompts, templates and staged
outputs that produce the *inputs* to `app/domain/ontology/**` (see
`CLAUDE.md` §4.3). Everything here is Markdown: human-readable,
diff-friendly, and reviewable by an electrical engineer who has never opened
a Python file.

## Why this exists

SubstationOS's core claim, per `CLAUDE.md` §1, is that **the domain is the
product**. A Knowledge Graph built on a hallucination, an unchecked
inference, or a silently-merged conflict is worse than no Knowledge Graph at
all — per `CLAUDE.md` §16, *"a wrong answer is worse than a visible error in
this domain."* This directory exists to make that guarantee structural, not
aspirational: no fact reaches the ontology without a document, a page, a
confidence level, and — eventually — a human engineer's sign-off.

## Where this fits in the larger pipeline

```
Engineering PDF
      ↓
AI Extraction        ─┐
      ↓                │  this directory
Engineering Review     │  (knowledge/extraction/**)
      ↓                │
Canonical Knowledge   ─┘
      ↓
Ontology              (app/domain/ontology/**)
      ↓
YAML Definitions      (app/domain/ontology/attributes/*.yaml,
      ↓                app/domain/ontology/equipment_definitions/**/*.yaml)
Python Domain Model   (app/domain/ontology/*.py — factories, catalogs,
      ↓                validators, engines — already built, see CLAUDE.md §4.3)
Application           (app/services, app/routers)
```

Full detail on every stage, including the non-negotiable extraction rules,
lives in [`extraction/README.md`](extraction/README.md). The permanent
methodology those rules implement — the constitution this whole directory
answers to — lives in
[`protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`](protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md).

## Directory map

| Path | Responsibility |
|---|---|
| [`protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md`](protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md) | The constitution: knowledge philosophy, the full 10-stage lifecycle, the 9 extraction levels, mandatory metadata, confidence policy, review states, conflict resolution, canonical rules, versioning, and the permanent engineering principles. Read this before `extraction/README.md`. |
| [`extraction/README.md`](extraction/README.md) | The pipeline as currently implemented: stages, extraction rules, naming conventions, traceability philosophy. |
| [`extraction/prompts/`](extraction/prompts/) | One extraction prompt per knowledge category (equipment, attributes, relationships, signals, protections, cables, commissioning, civil, glossary). These are the instructions a future AI extraction session must follow. |
| [`extraction/templates/`](extraction/templates/) | The Markdown shape every extracted fact must be recorded in, per knowledge category. |
| [`extraction/outputs/raw/`](extraction/outputs/raw/) | Unreviewed AI extraction output. Never trusted, never cited by the ontology. |
| [`extraction/outputs/reviewed/`](extraction/outputs/reviewed/) | Engineer-annotated output: corrected, confirmed, or rejected. Still not canonical. |
| [`extraction/outputs/canonical/`](extraction/outputs/canonical/) | The only knowledge trusted as a source for YAML domain definitions. |
| [`extraction/manifests/`](extraction/manifests/) | One manifest per processed source document — the paper trail. |

## What this task did and did not do

This directory was created as **infrastructure only**. No engineering PDF in
`storage/documents/` has been read for the purpose of populating this
pipeline, and `extraction/outputs/**` contains no extracted content — only
the README that documents what each stage is for. Populating this pipeline
with real extractions is a separate, future task.

## Governing rule

`protocol/CANONICAL_KNOWLEDGE_PROTOCOL.md` is the constitution;
`extraction/**` is its implementation. If a change to the methodology is
ever needed, amend the protocol deliberately, with reasoning, the same way
`CLAUDE.md` §14 requires for the engineering manual itself — then bring
`extraction/**` into alignment with it. Do not let an extraction session
quietly drift the rules, and do not let the implementation and the
constitution disagree — the rules are what make the resulting Knowledge
Graph trustworthy.
