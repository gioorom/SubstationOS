# The Canonical Knowledge Protocol

**The official constitution of SubstationOS Knowledge Engineering.**

This document defines the permanent engineering methodology by which raw
engineering documentation becomes trusted, versioned, machine-usable
knowledge inside SubstationOS. It governs every past, present, and future
extraction session, without exception.

This protocol has the same standing, within its domain, that `CLAUDE.md`
has for the codebase: when any prompt, template, tool, or extraction
session appears to contradict what is written here, that is a bug in the
prompt, template, tool, or session — not in this document. This protocol is
amended deliberately, with reasoning, the same way `CLAUDE.md` §14 requires
of the engineering manual itself — never bent quietly to make one
extraction session's output fit.

This protocol governs *methodology*. The mechanical infrastructure it
governs — prompts, templates, and staged output folders — already exists
under `knowledge/extraction/` (see [`knowledge/README.md`](../README.md)).
Where this protocol refines or extends that infrastructure's terminology,
the differences are called out explicitly rather than left implicit; see
the recommendations delivered alongside this document.

---

## 1. Knowledge Philosophy

### Why canonical knowledge exists

A substation is described by hundreds of documents, drafted over years, by
different disciplines, at different revisions, occasionally disagreeing
with each other. Without a single, deliberately-constructed layer that
says *"this, and only this, is what the domain model may trust,"* every
consumer of that documentation — human or AI — would have to independently
re-derive the same conclusions, inconsistently, forever. Canonical
Knowledge is that layer. It exists so that `app/domain/ontology/` never has
to ask "which document should I believe?" — that question has already been
answered, by a named engineer, before the ontology ever sees the fact.

Canonical Knowledge is not a cache, a convenience, or a performance
optimization. It is the load-bearing wall between *documentation* (many,
inconsistent, unversioned in the domain sense) and *domain model* (one,
consistent, versioned). Remove it, and the domain model inherits the
documentation's inconsistency directly — which defeats the purpose of
having a domain model at all.

### Why raw knowledge must never be modified

Raw extraction is evidence. Evidence that can be edited after the fact is
not evidence — it is opinion wearing evidence's clothes. If a raw record
could be changed once review begins, no future reader could ever again
distinguish "the AI originally misread this drawing" from "this drawing
was ambiguous from the start" — the two failure modes require completely
different fixes (a better prompt, versus a request for a clearer drawing
from the design office), and conflating them destroys the pipeline's
ability to improve itself.

This is the same immutability discipline `CLAUDE.md` §6 requires of the
domain's own value objects (`@dataclass(frozen=True, slots=True)`), applied
one layer upstream: the pipeline that will eventually *produce* immutable
domain objects must itself treat its own historical output as immutable.
Correction happens by adding a new, later record — never by rewriting an
earlier one. A raw record is annotated by review (its state changes, per
§6) and can be superseded by a later extraction session, but the text of
what the AI actually produced, at that moment, from that document, is
permanent.

### Why engineering review is mandatory

An extraction session — no matter how disciplined the prompt, no matter how
literal the instruction to avoid inference — cannot exercise engineering
judgment. It cannot know, from the document alone, that two differently
labelled symbols are the same physical breaker referenced twice. It cannot
know that a printed value contradicts physical reality because of a
drafting error. It cannot know which of two conflicting revisions is
current. Only a qualified engineer, reading the same document with domain
context the extraction step does not have, can make those calls.

Review is therefore not a quality gate that catches occasional mistakes —
it is the step that supplies the one ingredient extraction structurally
cannot: judgment. Making it mandatory, for every single extracted
statement rather than a sample, is what keeps `CLAUDE.md` §1's founding
claim — *"the domain is the product"* — true in the artifact this
methodology produces, not merely in intent.

### Why traceability is more important than AI output

AI output is cheap: a prompt can be re-run in minutes. Trust, once spent,
is not cheap to rebuild — and for the audiences SubstationOS serves
(utilities, TSOs, DSOs, EPC contractors operating assets for decades, per
`CLAUDE.md` §16), trust is the entire product. A Knowledge Graph that
cannot show, for any fact, exactly which document and page it came from,
who confirmed it, and when, is not a smaller version of a trustworthy
Knowledge Graph — it is a different, untrustworthy thing, regardless of how
complete or fluent its output reads.

Given a choice between an extraction that is impressively complete but
cannot fully show its work, and one that is sparse but perfectly
traceable, this protocol always chooses the latter. A gap marked
`Not specified` is safe: it tells the truth about what is not yet known.
An untraceable assertion is a liability: it tells a comfortable story that
cannot be checked. Every rule in this protocol is, in the end, in service
of this one priority.

---

## 2. Knowledge Lifecycle

```
Engineering Document
      ↓
Raw Extraction
      ↓
Engineering Review
      ↓
Canonical Knowledge
      ↓
Domain Concepts
      ↓
Ontology
      ↓
Attribute Definitions
      ↓
Equipment Definitions
      ↓
Python Domain Model
      ↓
Application
```

### Stage 1 — Engineering Document

The permanent source of truth: a PDF (single-line diagram, functional
schematic, cable schedule, protection settings sheet, commissioning
procedure, civil drawing) stored under `storage/documents/`. Nothing in
this pipeline ever modifies, annotates, or overwrites the source document
itself. Every downstream stage points back to it; it points to nothing.

### Stage 2 — Raw Extraction

An AI extraction session reads one Engineering Document against one
extraction level (§3) and produces candidate fact records: explicit,
exhaustive, and unreviewed. Every record starts in review state `RAW`
(§6). This stage never resolves ambiguity, never merges apparent
duplicates, and never picks between conflicting statements — it only
transcribes what the document explicitly states, with full metadata (§4)
and an honestly-assigned confidence tier (§5). Raw records are immutable
once written (§1).

### Stage 3 — Engineering Review

A qualified engineer evaluates every raw record against the source
document and assigns it a terminal review state — `APPROVED` or
`REJECTED` (§6) — or leaves it `UNDER_REVIEW` pending an open question.
Review may correct an inaccurate transcription, but the correction is
recorded as part of the reviewed record, with the original extracted text
still visible — review never silently rewrites history, it supersedes it
transparently. No record advances past this stage without an individually
assigned verdict; there is no batch or sampled approval.

### Stage 4 — Canonical Knowledge

Where multiple `APPROVED` records — from the same document or from several
documents — describe the same real-world entity, a named engineer makes
the canonicalization decision (§7, §8): exactly one canonical record is
produced per entity, versioned (§9), with every contributing source still
enumerated. Where records conflict, the conflict is preserved and the
resolution reasoning is recorded explicitly, never silently averaged or
decided by recency. Canonical Knowledge is the only stage output that the
next stage — Domain Concepts — is permitted to read from.

### Stage 5 — Domain Concepts

A modelling stage, performed by an engineer who understands both the
canonical knowledge just produced and the ontology as it already exists.
Here, a canonical fact is classified against SubstationOS's domain
vocabulary: *is this an attribute, an equipment type, a relationship
pattern, a signal class?* — and, critically, checked against
`app/domain/ontology/` for whether an equivalent concept already exists
under a different name, so the ontology never accumulates duplicate
concepts for the same idea. This stage produces a mapping decision, not
yet a committed artifact.

### Stage 6 — Ontology

The formal structure the mapped domain concepts are expressed through:
`AttributeDefinition`, `EquipmentDefinition`, and the rules that govern
them, as defined in `app/domain/ontology/` per `CLAUDE.md` §4.3. This
stage is where a Domain Concept becomes an ontology-shaped decision — which
fields an attribute needs, which category an equipment type belongs to —
still without yet touching version-controlled data.

### Stage 7 — Attribute Definitions

Concrete, version-controlled YAML instances of `AttributeDefinition`,
authored under `app/domain/ontology/attributes/*.yaml` following the shape
and rules in `CLAUDE.md` §7. Every field in this YAML must be traceable to
a specific canonical knowledge record from Stage 4. Attribute definitions
are authored before equipment definitions because, per the existing
factory code (`EquipmentDefinitionFactory.from_dict`), an equipment
definition's attributes are resolved against an already-loaded
`AttributeCatalog` — the dependency runs attributes-before-equipment, and
this protocol's stage order reflects that.

### Stage 8 — Equipment Definitions

Concrete, version-controlled YAML instances of `EquipmentDefinition`,
authored under `app/domain/ontology/equipment_definitions/**/*.yaml`,
referencing the attribute definitions from Stage 7 by `id`. As with Stage
7, every field must be traceable to Stage 4. Per `CLAUDE.md` §16, once an
`id` is published at this stage, it is a contract — renamed only via a
deliberate migration, never edited casually.

### Stage 9 — Python Domain Model

The existing, already-implemented domain layer —
`AttributeDefinitionFactory`, `EquipmentDefinitionFactory`,
`AttributeCatalog`, `EquipmentDefinitionCatalog`,
`AttributeDefinitionValidator`, `EquipmentDefinitionValidator`, and the
`*Engine` orchestration classes (`CLAUDE.md` §4.3) — loads, validates, and
serves the YAML definitions produced in Stages 7 and 8. This protocol does
not change that code; it exists to guarantee the data that code receives is
correct.

### Stage 10 — Application

Routers, services, and — eventually — the Knowledge Graph and substation
comprehension engine consume the validated domain model to answer
engineering questions. This is the payoff stage: everything upstream of it
exists so that, by the time a question reaches this stage, the answer is
already known to be sourced, reviewed, and true.

---

## 3. Extraction Levels

Extraction proceeds in a strict, dependency-ordered sequence. Each level
may reference entities identified at a lower level; no level may reference
a level that has not yet been extracted for the document in question. This
ordering exists because engineering documents are internally
cross-referential in exactly this order — you cannot correctly identify a
relationship before you have identified the equipment it connects, and you
cannot correctly extract a protection function before you know which
signals it consumes.

| Level | Name | Depends on | Captures |
|---|---|---|---|
| 0 | Document Metadata | — | The document itself: identity, project, revision, discipline, pagination. |
| 1 | Glossary | 0 | Terminology, abbreviations, and aliases defined or consistently used in the document. |
| 2 | Equipment | 0, 1 | Physical apparatus: transformers, breakers, disconnectors, instrument transformers, relays, cabinets, civil structures. |
| 3 | Attributes | 2 | Ratings, settings, and dimensions stated for equipment identified at Level 2. |
| 4 | Relationships | 2 | Stated connections, containment, and dependencies between Level 2 equipment. |
| 5 | Signals | 2, 4 | Measurements, commands, status/position feedback, and alarm/trip tags travelling along Level 4 relationships. |
| 6 | Protection Logic | 2, 4, 5 | Protection functions and interlocks: their trigger conditions (Level 5 signals) and resulting actions (on Level 2 equipment). |
| 7 | Commissioning | 2, 6 | Factory and site test procedures and acceptance criteria, verifying Level 2 equipment and Level 6 functions. |
| 8 | Engineering Rules | 0–7 | General, cross-cutting design rules and constraints that are not about one instance but about a class of equipment or the design as a whole. |

### Level 0 — Document Metadata

The ten (now eleven, per §4) administrative facts that identify the
document itself, independent of its content. Extracted first because every
other level's records cite back to it. This level corresponds to the
manifest already specified under
[`knowledge/extraction/manifests/`](../extraction/manifests/README.md).

### Level 1 — Glossary

Terminology, abbreviations, and equipment aliases, in whatever language the
document uses them. Extracted before Equipment because equipment tags
frequently use abbreviations that must be resolved (via a legend or
consistent usage) to classify the equipment correctly at Level 2 — you
cannot confidently say a symbol tagged "TA" is a current transformer until
you know what "TA" is defined to mean in that document.

### Level 2 — Equipment

Physical, individually-identifiable apparatus. Includes electrical
equipment and civil structures alike — both are, for traceability
purposes, the same kind of record: an identifiable physical asset with a
label and a location. This is the identity layer every higher level
depends on; nothing above Level 2 can exist without an equipment reference
to attach to.

### Level 3 — Attributes

Characteristics, ratings, and settings stated for Level 2 equipment.
Depends on Level 2 because an attribute value is only meaningful in
relation to a piece of equipment (even if, per extraction rules, the
specific equipment cannot always be determined with certainty and must be
recorded as `Not specified`).

### Level 4 — Relationships

Stated connections, containment, and dependency between two Level 2
equipment items — the substation's topology. Depends on Level 2 for the
obvious reason that a relationship needs two things to relate.

### Level 5 — Signals

Individually-tagged measurement, command, status, alarm, and trip points.
Depends on Level 2 (a signal has a source and destination equipment) and
Level 4 (a signal typically travels along, or corresponds to, a stated
connection).

### Level 6 — Protection Logic

Protection functions and interlocks. Depends on Level 2 (protected
equipment), Level 4 (the topology the function operates within), and Level
5 (the signals the function's trigger condition and resulting action are
expressed in terms of).

### Level 7 — Commissioning

Factory and site test procedures. Depends on Level 2 (equipment under
test) and Level 6 (protection functions whose behavior a test is often
designed to verify) — a commissioning procedure's acceptance criteria
frequently restate, in test form, exactly what a Level 6 record already
asserts a protection function should do.

### Level 8 — Engineering Rules

The most abstract level: general design rules, standards references, and
constraints that apply across a class of equipment or the design as a
whole, rather than to one labelled instance — for example, a drawing note
stating that a category of terminal blocks must be wired per a referenced
internal standard, applying uniformly to every instance of that equipment
category rather than to one specific tag. Extracted last because
recognizing something as a *rule*, rather than an isolated fact, typically
requires having already seen the pattern it governs recur across several
Level 2–7 records — an Engineering Rule is, in effect, an explicitly
stated generalization the documentation itself makes, never a
generalization the extraction session notices and states on the
documentation's behalf.

### Reconciling levels with extraction categories

The nine extraction *categories* already implemented under
[`knowledge/extraction/prompts/`](../extraction/prompts/) map onto these
levels as follows: `equipment` and `civil` → Level 2; `attributes` → Level
3; `relationships` → Level 4; `signals` → Level 5; `protections` → Level 6;
`commissioning` → Level 7; `glossary` → Level 1; `cables` → primarily
Level 2 (a cable is itself a physical asset) with its routing captured at
Level 4. No prompt yet exists for Level 0 (covered by the manifest
specification) or Level 8 (Engineering Rules) — see the recommendations
delivered alongside this protocol.

---

## 4. Mandatory Metadata

Every extracted fact, at every level, must be traceable to all eleven of
the following. Traceable, not necessarily re-transcribed: the five
document-level fields are recorded once, on the Level 0 manifest, and
every fact references its manifest rather than repeating those fields
verbatim on every line — repetition would invite drift between copies of
the same information, and a single authoritative home for each field is
what "traceable" actually requires.

| Field | Recorded at | Meaning |
|---|---|---|
| **Source Document** | Level 0 (manifest) | The document's own title, as printed on its title block. |
| **Project** | Level 0 (manifest) | The project or plant the document belongs to, as printed on its title block. |
| **Drawing Number** | Level 0 (manifest) | The drawing code exactly as printed — the stable identifier used throughout the pipeline for this document. |
| **Revision** | Level 0 (manifest) | The document's revision index and date, as printed on its title block. A manifest is tied to one specific revision. |
| **Discipline** | Level 0 (manifest) | The engineering discipline the document belongs to (Electrical, Civil, Protection & Control, Instrumentation, etc.). |
| **Page** | Per fact | The page number printed in the document's own internal numbering, not the PDF page index, since a fact's page can differ from every other fact extracted from the same document. |
| **Confidence** | Per fact | One of the three tiers defined in §5, assigned honestly at extraction and revisable only downward at review without new evidence. |
| **Extraction Session** | Per fact (inherited from the Raw Extraction run) | A stable identifier for the specific AI extraction run that produced this fact — e.g. a date-stamped session id — so that a future methodology change, or a suspected systematic extraction error, can be traced to every fact a given session produced. |
| **Reviewer** | Per fact, from Stage 3 onward | The name of the engineer who evaluated this fact. `Not yet assigned` before review begins — this is expected, not an error, for any record still in state `RAW`. |
| **Review Date** | Per fact, from Stage 3 onward | The date the reviewer's verdict (§6) was recorded. `Not yet assigned` before review. |
| **Canonical Version** | Per fact, from Stage 4 onward | The version identifier (§9) of the canonical entity this fact contributed to, once canonicalized. `Not yet assigned` before Stage 4. |

A fact record with a document-level field that cannot be resolved via its
manifest reference is incomplete and must not proceed past Raw Extraction.
A fact record with `Confidence`, `Extraction Session`, `Reviewer`, `Review
Date`, or `Canonical Version` missing outright (as opposed to legitimately
`Not yet assigned` for a stage it has not reached yet) is malformed and
must be corrected before it advances.

---

## 5. Confidence Policy

Confidence is a statement about **how directly** a fact is supported by the
source, not about how important or how useful the fact is. It is assigned
once, honestly, at extraction, using exactly three tiers — there is no
tier above 100% and no partial credit between tiers.

### 100% — Explicit statement

The fact is stated in words, in the document's own text (a table cell, a
labelled field, a printed note). No reading of a symbol, a drawn line, or a
diagram convention is required to establish it. This is the highest tier
because it requires the least interpretation of *any* kind — literal
transcription.

### 90% — Explicit engineering drawing

The fact is unambiguous, but it is expressed graphically rather than in
prose — a symbol, a drawn connection line, a label attached to a diagram
element, a position in a single-line diagram that engineering drawing
convention makes unambiguous. This is still an *explicit* statement of
fact — nothing is inferred from typical practice — but reading it correctly
requires literacy in engineering drawing conventions rather than plain
text comprehension, which is why it sits one tier below 100%.

### 70% — Derived from multiple explicit references

The fact is not stated in one place, but can be established with certainty
by combining two or more individually explicit references (100% or 90%
statements) — for example, a legend's explicit definition of an
abbreviation, combined with that abbreviation's explicit use as a tag on a
different sheet. **Derivation is not inference.** Derivation only ever
combines statements the document already makes explicitly, through pure
logical combination — it never adds anything the document does not itself
assert. If establishing the fact requires assuming typical practice,
filling a gap with engineering judgment, or reasoning about what is
*probably* true rather than what is *stated* to be true, it is inference,
it is forbidden at any confidence level, and it is not extracted at all.

### Below 70%

**Never enters Canonical Knowledge automatically.** A fact this uncertain
remains in Raw or Reviewed state indefinitely, explicitly flagged. It may
only be promoted to Canonical Knowledge through a documented, named
engineering override at Stage 4 (§7, §8) — for example, an engineer with
independent corroborating knowledge (a site visit, a conversation with the
original designer) explicitly choosing to canonicalize it and recording
that reasoning in the `Canonical decision` field. The system itself never
performs this promotion; only a named human, exercising and documenting
judgment, may.

### Revising confidence

A reviewer may lower a fact's assigned confidence at Stage 3 if closer
inspection reveals the original tier was too generous (e.g. what looked
like an explicit statement turns out to be genuinely ambiguous in the
source). A reviewer may not raise a fact's confidence without new
corroborating evidence — and if new evidence is what justifies the raise,
that is itself a derivation, and the resulting fact is re-classified per
the rules above, with the new evidence cited.

---

## 6. Review States

Every extracted fact is, at all times, in exactly one of five states.

```
        ┌──────────────────────────────────────────┐
        │                                            │
        ▼                                            │
      RAW ──────────► UNDER_REVIEW ──────────► APPROVED ──────────► SUPERSEDED
                            │                       ▲
                            │                       │
                            ▼                       │
                        REJECTED            (open question resolved,
                                              loops back to UNDER_REVIEW
                                              until a terminal verdict)
```

- **`RAW`** — the state every fact is created in at Stage 2. No human has
  evaluated it yet. A `RAW` fact may never be cited by Canonical Knowledge.

- **`UNDER_REVIEW`** — a reviewer has begun evaluating the fact but has not
  yet reached a terminal verdict, most commonly because it carries an
  unresolved open question. A fact stays `UNDER_REVIEW` — it does not
  advance to `APPROVED` or `REJECTED` — until that question is answered.
  This state also signals to other reviewers that work on this fact is
  already in progress, preventing duplicated effort.

- **`APPROVED`** — the reviewer has confirmed the fact accurately reflects
  the source document, possibly after correcting the originally extracted
  text (the correction is recorded as part of the approved record; the
  original extracted text remains visible, never deleted). Only `APPROVED`
  facts may be cited by Canonical Knowledge.

- **`REJECTED`** — the reviewer has determined the fact should not proceed:
  it was mis-extracted, it was inferred rather than stated, or it is
  otherwise invalid. Rejected facts are never deleted; they remain a
  permanent record of what extraction got wrong, valuable for diagnosing
  and improving prompts.

- **`SUPERSEDED`** — a previously `APPROVED` fact (or an entire canonical
  entity built from one) has been replaced — by a newer document revision,
  by a corrected engineering understanding, or by a canonicalization
  decision. The original record's state changes to `SUPERSEDED`; it is
  never deleted and always links forward to whatever replaced it.

### Transition rules

1. Every fact starts `RAW`.
2. `RAW → UNDER_REVIEW` when a reviewer begins evaluating it.
3. `UNDER_REVIEW → APPROVED` when the reviewer reaches a positive terminal
   verdict.
4. `UNDER_REVIEW → REJECTED` when the reviewer reaches a negative terminal
   verdict.
5. `UNDER_REVIEW → UNDER_REVIEW` (a self-loop, not a new state) for as long
   as an open question remains unresolved.
6. `APPROVED → SUPERSEDED` when a later fact, document revision, or
   canonicalization decision replaces it.
7. **No state ever reverts.** `APPROVED` never returns to `RAW` or
   `UNDER_REVIEW`; if an approved fact later turns out to be wrong, it is
   marked `SUPERSEDED` by a corrected fact — the error and its correction
   both remain permanently visible, rather than the error being erased.
8. `REJECTED` and `SUPERSEDED` are otherwise terminal. If new evidence
   later resurrects a rejected idea, that produces a fresh `RAW` fact
   referencing the rejected one for context — the original rejected record
   is never reopened or edited.

---

## 7. Conflict Resolution

**Never overwrite. Never merge automatically. Store every conflicting
statement. Engineering review decides.**

A conflict exists whenever two or more facts — whether `RAW`, `APPROVED`,
or already canonical — appear to describe the same real-world entity,
attribute, relationship, or signal, but assert different values. Conflicts
are expected, not exceptional: they are the natural result of a
documentation set drafted across years, revisions, and disciplines, and
this protocol treats them as first-class data, not as errors to be
silently smoothed over.

### The complete workflow

1. **Detection.** A conflict may be noticed during Stage 3 review (a
   reviewer processing one document's facts notices a value that differs
   from an already-`APPROVED` fact from a different document) or during
   Stage 4 canonicalization (multiple `APPROVED` facts, being consolidated
   into one canonical entity, disagree). Either way, detection is a human
   act — the pipeline does not attempt automatic conflict detection by
   fuzzy-matching values.

2. **Preservation.** Every conflicting statement is kept as its own
   complete fact record, with its own full metadata chain (§4) and its own
   review state (§6). Nothing is overwritten in place. Nothing is averaged,
   ranged, or otherwise numerically combined. Both (or all) conflicting
   values remain individually readable, forever.

3. **Flagging.** Once a conflict is identified, it is recorded explicitly
   — as an `Open questions` entry cross-referencing every conflicting fact
   by its source document, page, and drawing number — so a future reader
   discovers the conflict immediately, rather than by chance comparison. A
   fact with an unresolved conflict flag stays `UNDER_REVIEW` (§6); it is
   not force-approved to keep a batch moving.

4. **Resolution authority.** Only a named engineer may resolve a conflict,
   and resolution happens exclusively at Stage 4 (Canonical Knowledge),
   never earlier. A fact can be individually `APPROVED` — confirming it
   accurately transcribes its own source document — while the
   cross-document conflict it participates in remains unresolved; approval
   confirms accurate transcription, not truth across sources.

5. **Resolution outcomes.** A named engineer resolving a conflict must
   reach one of three explicit outcomes, recorded in the resulting
   `Canonical decision` field:
   - **One source is authoritative**, for a stated reason (e.g. "the site
     as-built drawing S-031 supersedes the design-stage drawing S-025 for
     this value, per Engineer X, dated Y").
   - **Both are correct**, because closer analysis shows they describe two
     genuinely distinct entities that extraction (correctly, per its
     rules) had not yet distinguished — in which case two canonical
     entities are created, not one, and the earlier apparent conflict is
     recorded as resolved-by-disambiguation.
   - **Unresolved** — the conflict cannot yet be adjudicated with available
     information. In this case, **no canonical record is created**. The
     entity remains un-canonicalized, the conflicting facts remain
     `APPROVED` at the fact level, and the open question is carried
     forward rather than forced to a premature answer.

6. **Documentation of the decision.** Whichever outcome, the reasoning and
   the deciding engineer's name are recorded in `Canonical decision`. A
   canonical record that resolves a conflict without this explanation is
   incomplete, per §8.

7. **Permanence.** Even after resolution, every conflicting statement that
   was not chosen remains in the record, its state moved to `SUPERSEDED`
   (§6) and linked to whatever was chosen instead — never deleted. A future
   reader must always be able to see that a conflict existed and exactly
   how it was resolved, not just the winning answer.

---

## 8. Canonical Rules

Canonical Knowledge contains only fact records that are, simultaneously
and without exception:

- **Reviewed.** Built exclusively from facts that completed Stage 3. A
  `RAW` or `UNDER_REVIEW` fact contributes to nothing canonical.
- **Approved.** Every contributing fact's review state (§6) is `APPROVED`.
  `REJECTED` facts, and facts still carrying unresolved open questions, are
  excluded by construction — canonicalization does not "work around" an
  unresolved state, it waits for one.
- **Traceable.** Every canonical record's `References` field enumerates
  every `APPROVED` fact — and, transitively, every source document and
  page — it derives from. A canonical record with a broken, partial, or
  implied (rather than enumerated) reference chain is not valid canonical
  knowledge, regardless of how confident the underlying facts were.
- **Versioned.** Every canonical record carries an explicit `Canonical
  Version` (§9). Canonical Knowledge is never edited in place; a change
  produces a new version, and the prior version is preserved, marked
  `SUPERSEDED`, and permanently linked.
- **Engineering knowledge.** A canonical record represents a fact the
  engineering documentation actually asserts about the substation as
  designed or built — not an opinion, not a marketing description, not a
  speculative future state, and not a fact about the documentation process
  itself (which belongs in a manifest or review annotation, not a
  canonical engineering record).

### Explicit exclusions

The following never enter Canonical Knowledge, without exception:

- Any fact below the 70% confidence tier, unless accompanied by a
  documented, named engineering override (§5).
- Any fact still carrying an unresolved open question or unresolved
  conflict (§7).
- Any fact whose review state is `REJECTED` or `SUPERSEDED`.
- Any canonicalization spanning multiple sources that lacks an explicit
  `Canonical decision` explanation.

---

## 9. Versioning Strategy

Canonical Knowledge evolves; it is never silently rewritten. Every
canonical entity carries its own independent version counter — versioning
is per-entity, not a single global knowledge-base version, because
unrelated entities change for unrelated reasons at unrelated times, and
forcing them to "version together" would communicate nothing true.

### Version 1

The first canonicalization of a given entity. Created the moment a named
engineer makes the initial canonical decision from one or more `APPROVED`
facts (§7, §8). Its `Canonical Version` is `1`. Its `References` enumerate
every fact that contributed to it at that time.

### Version 2 (and beyond)

Created only when the **asserted engineering fact itself changes** for an
already-canonical entity — a new document revision arrives with a
different value, a previously unresolved conflict is now resolved, or an
engineer corrects an earlier canonical decision on new evidence.
Re-confirming an existing canonical record from the same evidence, with
nothing new, does not mint a new version — it is simply noted (e.g. as part
of a periodic audit) without version churn. When a new version is minted:

- The prior version's record is not deleted or edited; its state becomes
  `SUPERSEDED` and it gains a `Superseded by: <new version>` reference.
- The new version's record gains a `Supersedes: <prior version>` reference.
- The new version's `Canonical decision` field states exactly what changed
  and why — never just that a change occurred.

### Superseded knowledge

A superseded canonical record remains permanently readable at its original
location. It is never removed from the repository, never overwritten, and
never made harder to find than the version that replaced it — superseded
knowledge is not an embarrassment to hide, it is the historical record that
makes the current version's correctness demonstrable.

### Historical traceability

The practical payoff of this discipline: at any future date, an engineer
can ask *"what did SubstationOS record about this equipment's rated
voltage in 2026, and why did that change by 2028?"* and receive a complete,
dated, reasoned answer from the versioned canonical files alone — no need
to reconstruct history from git archaeology, memory, or a phone call to
someone who has since left the project. This is `CLAUDE.md` §16's
"Traceability" and "Long-term over short-term" principles, made concrete
in the shape of the knowledge itself, not just the code that serves it.

---

## 10. Engineering Principles

The permanent, non-negotiable principles of SubstationOS Knowledge
Engineering. Where a future decision is unclear, these principles resolve
it before any other consideration.

1. **Source before interpretation.** No fact is recorded before its source
   is. A statement without a citation is not a fact in this system — it is
   an unverified claim, and it is treated as one.
2. **No hallucinations.** If it is not in the document, it does not exist
   in the knowledge base. There is no tier, no exception, and no shortcut
   that permits recording something the source does not state.
3. **No inferred engineering decisions.** This protocol records what the
   documentation says, never what an engineer would probably have decided
   given typical practice. Probability is not evidence.
4. **Everything must be reproducible.** Given the same document and the
   same extraction rules, two independent extraction sessions should
   arrive at materially the same raw facts. A divergence is a signal that
   the rules are ambiguous, not an acceptable source of variance.
5. **Every fact must be auditable.** Any canonical statement can be traced
   by a human, in a finite number of steps, back to a specific page of a
   specific document — without needing to trust the AI session that
   originally produced it.
6. **Knowledge precedes software.** The domain model is written to match
   the knowledge; the knowledge is never adjusted to fit a shape that is
   merely convenient for the software. This is `CLAUDE.md` §1's claim that
   the domain is the product, applied to this pipeline's own priorities.
7. **Silence is not consent.** The absence of a stated fact is recorded
   explicitly as `Not specified`. It is never treated as implicit
   confirmation of a default, a typical value, or an assumption.
8. **Confidence is earned, not assumed.** A fact defaults to the lowest
   applicable tier, never the highest. Certainty must be demonstrated by
   the source; it is never presumed by the extractor for convenience.
9. **Human judgment is the only authority that canonicalizes.** No
   automated process ever promotes a fact into Canonical Knowledge. A named
   engineer always does, and always leaves a record of having done so.
10. **History is never erased.** Superseded, rejected, and conflicting
    facts remain in the record permanently. Correction in this system is
    additive — it never overwrites, it always adds a new, dated layer on
    top of what came before.
11. **One entity, one canonical record — many sources.** Multiple documents
    may describe one real thing. Canonicalization exists precisely to
    resolve "many sources, one truth" without ever discarding any of the
    many sources that contributed to that truth.
12. **A gap is safer than a guess.** An incomplete domain model that
    honestly says "not yet known" is more valuable, and categorically more
    trustworthy, than a complete one that quietly contains an invented
    value.
13. **The methodology outlives any single extraction session.** This
    protocol is amended deliberately, with reasoning recorded, the same way
    `CLAUDE.md` is amended — never bent quietly so that one session's
    output happens to fit.
14. **Documents are permanent; interpretations of them evolve.** The source
    PDF never changes. What engineers understand it to mean can change over
    time — and when it does, that evolution is versioned (§9), never
    silently substituted in place of what was previously believed.

---

*This protocol is the constitution. The prompts, templates, and staged
output folders under [`knowledge/extraction/`](../extraction/README.md)
are its implementation. When the two disagree, this document governs, and
the implementation is corrected to match it.*
