# Engineering Evidence

**Status:** As-built reference for the **Engineering Evidence Extraction**
layer introduced in Milestone 28.1 and the **Engineering Evidence
Evaluation Framework** introduced in Milestone 28.2. For the deterministic document
pipeline that feeds it, see
[document_management.md](document_management.md); for where it sits in
the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## The pipeline

```
Canonical Text
    |
    v
Deterministic Evidence Rules       versioned, findable, no LLM
    |
    v
Engineering Evidence Set           immutable, persisted, provenance-rich
    |
    v
Engineering Evidence Evaluation    measured against a reference corpus
    |
    v
Engineering Entity Resolution      Milestone 29.1 - see engineering_entities.md
    |
    v
Knowledge Graph Population         (a later milestone)
```

Evidence is an **observation**; an entity is a **deterministic grouping
of observations**; a graph node is neither, and will later be generated
from entities. See
[engineering_entities.md](engineering_entities.md).

> **Every new extraction rule must be evaluated against the reference
> corpus before it becomes part of the supported deterministic
> engineering pipeline.** A rule that has not been measured is a rule
> nobody knows the cost of: it may raise recall and quietly halve
> precision, and the first place that would surface is an engineer
> disputing an entity months later. Evaluation is not a one-off exercise
> or a test-suite detail - it is a product capability with its own API,
> its own persisted history, and its own version.

## Four statements this layer is built on

These are not aspirations. Each is enforced by the shape of the model, by
an architecture test, or by both.

1. **Evidence is an observation, not an entity.** An item says "the
   characters `20 kV` appeared on page 3, paragraph 2, line 1, tokens
   4-5, matched by rule `voltage_value` version 1.0". It does not say a
   transformer exists, or which one. Two documents may write the same
   designation for different equipment, and one piece of equipment may
   appear under several designations; deciding that is entity
   resolution, and it is a later milestone with its own review
   obligations.
2. **A quantity next to a designation is not yet a property
   relationship.** `Trasformatore T1 630 kVA` yields *two independent
   observations*. Adjacency is a fact about ink; attribution is a
   judgement. There is no field on an evidence item, and no column in the
   evidence schema, in which "belongs to" could be recorded.
3. **Graph population must not consume document text directly in the
   future.** When the Knowledge Graph is migrated, it reads evidence
   through `EngineeringEvidenceRepository`. A graph builder that read
   canonical text would be re-deciding what counts as an observation, in
   a second place, under no rule version - and two answers about the same
   document would exist.
4. **Provenance and rule version are mandatory for every item.** An
   observation whose source cannot be located is not evidence; it is an
   assertion. Both fields are non-nullable in the schema.

## The supported catalogue

Deliberately small. Only types that can be extracted honestly and
deterministically from this repository today.

| Type | Example | Rule |
|---|---|---|
| `DESIGNATION` | `T1`, `QMT01`, `52-Q1`, `+E01-QA1` | `designation_generic` 1.0 |
| `VOLTAGE_VALUE` | `20 kV`, `400 V` | `voltage_value` 1.0 |
| `CURRENT_VALUE` | `1250 A`, `16 kA` | `current_value` 1.0 |
| `POWER_VALUE` | `630 kVA`, `40 MVA` | `power_value` 1.0 |
| `CABLE_SECTION_VALUE` | `240 mm²` | `cable_section_value` 1.0 |

### Why `MANUFACTURER_NAME` is absent

Recognising a manufacturer requires a list of manufacturers, and this
repository has none: `ontology/attributes/manufacturer.yaml` declares a
free-text string attribute with **no enumerated values**, and no vendor
vocabulary exists anywhere else. Writing one - ABB, Siemens, Schneider,
… - would be an arbitrary, incomplete dictionary presented as a
deterministic rule, and every document naming a vendor outside it would
be silently wrong. The type is omitted until a governed vendor vocabulary
exists.

## Designation recognition

Conservative on purpose. **Not every capitalised token is a
designation**, and the cost of being wrong is asymmetric: a missed
designation is a gap a later milestone can fill, while a false one
becomes an entity somebody has to disprove.

Five shapes are recognised. The first three shipped with Milestone 28.1
and required letters and digits together; the last two were added by
**EPIC 32.E2** after measuring 41,739 tokens of a single Italian DSO's
HV/MV functional diagrams, where product-aspect designations turned out
not to obey that rule.

| Shape | Matches | Does not match |
|---|---|---|
| letters then digits | `T1`, `TR1`, `QMT01`, `M1` | `TRASFORMATORE`, `AT`, `kV` |
| numeric function code | `52-Q1`, `189-SB1` | `145`, `20-30` |
| IEC 81346 compound | `+E01-QA1` | `+`, `-` |
| product aspect | `-E`, `-E1`, `-X`, `-TA` | `-`, `-SCHEMA` |
| dot-qualified product | `-E1.L`, `-E.AM`, `-EV.TVL` | `-.L`, `-E1.L.X` |

Bare uppercase words, bare numbers, single letters and lower-case tokens
are all rejected. **The equipment category is never inferred from the
designation** - `QMT01` looks like a medium-voltage panel to an engineer,
and this layer records only that the designation-like text was observed.

### Why the product-aspect shapes need no digit

`-E`, `-X` and `-TA` are real terminal blocks, observed 28 times in the
real set. The `-` **is** the distinguishing mark: IEC 81346 assigns it to
the product aspect, so unlike a bare word the token does not need a digit
to be recognisable. Length is bounded at four letters, which is what
keeps `-SCHEMA` out and covers every observed real form.

### The dot is lexical, not hierarchical

`-E1.L` is recorded as **one atomic designation**. It does not decompose
into `-E1` and `L`, creates no second asset, and authorises no
parent/child relationship of any kind.

**The decisive reason is the absence of positive evidence.** No source
available to this platform establishes that the leading lexical segment
denotes the parent engineering object of the dot-qualified designation.
A governed relationship needs evidence *for* it; nothing here provides
any.

A second observation points the same way without proving anything on its
own: the real drawings place `-E` at `+GSH001` and `-E.AM` at `+GSH003`.
That divergence is evidence against a naive **physical containment**
reading, and it is consistent with a sibling naming-family
interpretation. It does **not** prove that no reference-designation
hierarchy exists - a reference-designation hierarchy need not imply
co-location, and this platform has established no such invariant.

The interpretation is **provisional**. Authoritative Italian DSO
designation documentation, or a domain expert, may revise it; if a
future authoritative source defines different semantics for the dot,
that is new evidence and may trigger a governed architecture revision.
It is not a general claim about IEC 81346.

### Location aspects

A location aspect is recognised in both forms the real documents write:

| Form | Example | Note |
|---|---|---|
| inside a compound | `+E01` of `+E01-QA1` | Milestone 32.P1; span narrowed to the location characters |
| standalone | `+GSH002`, `+DQ1910`, `+TELAIO`, `+CELLA`, `+Z` | EPIC 32.E2 |

The standalone form is overwhelmingly the commoner one: 268 occurrences
against zero compounds across the real set. Word forms such as `+TELAIO`
(frame) and `+CELLA` (cubicle) are ordinary location **designations** -
the platform records the value and assigns no equipment class, exactly as
it refuses to read `QMT01` as a panel.

**A standalone location aspect is not also a designation.** The
designation rule declines it, so the token is observed once, as what it
is. Recording 268 places as equipment assets would have been the largest
single misclassification in the pipeline.

### Substance notation

`SF6` is sulphur hexafluoride and appears only in running prose -
"ALLARMI SF6", "BASSA PRESSIONE SF6 (P1 GAS)". It matches
letters-then-digits and is observed as a designation **16 times across
the real document set. This is a known false positive, and it is
measured rather than suppressed.**

No grammar can separate it: it is structurally identical to the real
designations `MI1`, `MO2` and `Q8` in the same documents.

Two suppressions were built and removed on review:

- **A token catalogue** (`SUBSTANCE_NOTATION`) encodes "SF6 is never an
  engineering designation" as universal truth. Nothing stops a real
  installation designating an object `SF6`, and the catalogue would make
  it permanently invisible. A present false positive is visible and
  disputable; that future false negative would be neither.
- **A source-context rule** rejecting the token after `ALLARMI` or
  `PRESSIONE`. Its entire evidence base is two words, on four lines, in
  two documents, in one language - and it would miss `GAS SF6`, a bare
  `SF6` table cell, and any non-Italian phrasing. That is a heuristic
  with a version number.

The honest fix is upstream and is not an extractor concern: a **governed
substance vocabulary**, reviewed like every other domain catalogue in
`app/domain/ontology`, which the rule could then consult as
source-authoritative classification rather than as a hand-curated list.
Until that exists the false positive stands, and the reference corpus
measures it: three of its annotations' worth of `SF6`, reported in
precision rather than hidden.

## Quantities and units

Both forms are kept for every quantity: the **original text** as written,
and a **typed value**.

`Decimal` throughout, never `float`, in the domain and in the schema
(`Numeric`). A rated voltage that read back as 20.000000000000004 kV
would be a defect nobody could explain to an engineer.

### The unit catalogue

One module declares every unit, its accepted textual variants, its
compatible evidence type and - only where the conversion is exact - its
base unit:

| Canonical | Variants | Base |
|---|---|---|
| `V` | `V`, `v`, `Volt`, `volt`, `VOLT` | - |
| `kV` | `kV`, `KV`, `kv` | `V` (×1000) |
| `A` | `A`, `Ampere`, `ampere`, `AMPERE` | - |
| `kA` | `kA`, `KA`, `ka` | `A` (×1000) |
| `VA` | `VA`, `va` | - |
| `kVA` | `kVA`, `KVA`, `kva` | `VA` (×1000) |
| `MVA` | `MVA`, `Mva`, `mva` | `VA` (×1000000) |
| `mm²` | `mm²`, `mm2`, `MM²`, `MM2` | - |

- **No case folding.** `mV`, `kV` and `MV` are three different
  quantities; folding case would silently turn a millivolt into a
  megavolt. `400 mV` is therefore *not* extracted - `mV` is not declared.
- **No inferred units.** A bare `630` beside the word "potenza" is a
  number beside a word, not a power value.
- **No universal conversion engine.** `mm²` has no base unit because
  there is nothing exact to convert it to.
- **`mm²` and `mm2` map to one canonical unit**, declared here rather
  than inferred - and each item still records the spelling its document
  used, so the two remain distinguishable.

### The separator policy

European and Anglo-Saxon documents disagree about `1.250`, and both
appear in real substation documentation.

| Written | Read as | Status |
|---|---|---|
| `630` | 630 | `OBSERVED` |
| `12,5` / `12.5` | 12.5 | `OBSERVED` |
| `1.250` / `1,250` | - | `AMBIGUOUS` |
| `1.234,5` | - | `AMBIGUOUS` |

The three-digit case is genuinely undecidable without the document's
locale, which this system does not know. It is recorded as `AMBIGUOUS`
and **carried without a normalised value**: a reviewer can settle it, and
a guess could not be un-guessed once it had become a rated value in the
graph.

## Evidence status

| Status | Meaning | Persisted |
|---|---|---|
| `OBSERVED` | Rule matched, validation satisfied | yes |
| `AMBIGUOUS` | Rule matched, result not statable unambiguously | yes, without a value |
| `REJECTED` | Rule matched, validation refused | **no** - a diagnostic only |

Categorical, deliberately not a percentage. A numerical confidence would
have to be calibrated against something, and there is nothing here to
calibrate it against: a regular expression either matched or it did not.
Inventing "0.85" would dress a boolean up as a measurement.

## Provenance

Every item carries:

```
page -> section -> paragraph -> block -> line -> token range -> span character ranges
```

A caller can answer, without searching for text anywhere: which page,
which paragraph, which line, which tokens, which characters of which
spans, and under which rule at which version.

- **Character ranges exclude trimmed punctuation.** `400 V,` yields
  evidence whose range covers `400 V` and not the comma. Trimming without
  narrowing the range would be a small, permanent lie about where the
  observation came from.
- **An observation may cite more than one span.** `20` and `kV` in
  different styles is one quantity drawn from two spans, and both
  references are recorded - a single range across two spans would
  describe characters that exist in neither.
- **An observation never crosses a line.** Rules see one line's tokens at
  a time, so a value split across a line or paragraph boundary is simply
  not extracted rather than recorded with an approximate location.
- **Provenance is recorded at match time, never reconstructed.** Nothing
  is ever located later by searching for text, which is how provenance
  quietly becomes approximate.

## Normalisation safety

The extractor reads **original token text**, never the NFKC-normalised
form. Canonical text stores both (Milestone 27.1); the normalised form
folds `mm²` into `mm2` and `I₁` into `I1`, and matching on it would
silently promote a subscripted signal name to a designation and degrade
the engineering symbols an evidence item records.

Regression tests cover `mm²`, `m³`, `Ω`, `Δ`, `φ`, `±`, `°`, `≤`, `×`
and `I₁`.

The canonical text normalisation model itself is unchanged - no blocker
was found that required redesigning it.

## Rules are findable

One pattern catalogue, one unit catalogue, one rule catalogue. Architecture
tests assert that no other module in the context calls `re.compile`,
constructs a `UnitDefinition`, or writes a unit spelling as an executable
string literal. The extractor **orchestrates** rules and contains no
matching logic of its own - an inline `if` there would be a rule nobody
could find, version or review, while every stored item cites a rule
version.

## Idempotency

The stored key is
`(document_id, content_checksum, extraction_policy_version)`. Re-running
finds the existing set and re-uses it - reported as `reused: true` with
`200` rather than `201`. A changed document (new checksum) or a changed
catalogue (new policy version) produces a **new** set alongside the old
one, so a conclusion drawn under last year's rules stays explainable.

Each item additionally carries a deterministic `evidence_key` - SHA-256
over document, checksum, rule, type and provenance - which makes a
duplicate observation impossible to insert.

## Failures

| Code | When |
|---|---|
| `canonical_text_missing` | The document has not been segmented |
| `unsupported_canonical_text_version` | Segmentation contract this extractor does not know |
| `invalid_provenance` | An item's location could not be verified against the source |
| `invalid_extraction_rule` | An item cites a rule or version the catalogue does not declare |
| `rule_execution_failure` | A rule raised - the one genuinely unknown cause |
| `invalid_engineering_quantity` | An observed quantity carries no value |
| `unsupported_unit` | A unit the catalogue does not declare |
| `evidence_validation_failure` | The assembled set violates a model invariant |
| `evidence_persistence_failure` | Built, and could not be stored |
| `inconsistent_source_identity` | The canonical text describes a different document version |

## Persistence

Three tables added by migration `24d9fadeeb4c` (purely additive):
`engineering_evidence_sets`, `engineering_evidence`,
`engineering_evidence_spans`. Spans are a child table because an
observation may draw on more than one.

Nothing here references or modifies canonical text, the document row, the
Engineering Index or the Knowledge Graph.

## API

```
POST /documents/{document_id}/engineering-evidence   extract or re-use
GET  /documents/{document_id}/engineering-evidence   read with provenance
```

Four outcomes are distinguishable:

| `succeeded` | `reused` | `found_evidence` | Means |
|---|---|---|---|
| true | false | true | extraction completed |
| true | false | false | completed, nothing supported found |
| true | true | either | an existing set was reused |
| false | - | - | extraction failed; `failure` names the typed cause |

Finding nothing is a success, not a failure: a document may simply
contain nothing these rules recognise. No ORM model is exposed - no row
id, no foreign key, no timestamp.

## Evaluation (Milestone 28.2)

The framework that measures whether these rules are any good. The
extractor cannot grade itself, so quality is defined by a
**version-controlled reference corpus**: documents whose evidence a human
wrote down by hand.

### The reference corpus

`app/domain/evidence_evaluation/corpora/*.yaml` - domain data beside the
domain that defines it, exactly as the ontology's YAML is. A corpus
declares its documents' text, the observations a human asserts are in
them, and the rule versions it was annotated against.

Expected observations are built from the **same Engineering Evidence
value objects** the extractor produces - `EvidenceType`,
`EvidenceStatus`, `EvidenceProvenance`, `EngineeringQuantity`,
`DesignationValue`. A parallel annotation model would drift from the
evidence model, and an annotation format able to express something the
evidence model cannot is an annotation nobody can ever satisfy.

Corpora are **immutable at runtime**: there is no `save` on the corpus
port, asserted by test. Changing what "correct" means is an edit to a
reviewed file and a bump of the corpus version, so evaluations recorded
against the old version stay valid statements about the old definition.

A reference document's text is turned into canonical text through the
**real segmenter** - a corpus that hand-built its own tokens would keep
passing on the day segmentation changed.

### Classification

Documents are paired with expectations by **location** - page,
paragraph, line, token range - and a pair is a `TRUE_POSITIVE` only when
everything agrees: evidence type, observed text, status, typed value and
provenance.

Anything else is **both** a `FALSE_POSITIVE` and a `FALSE_NEGATIVE`: the
extractor said something that is not so, *and* failed to say something
that is. There is deliberately no "near miss" outcome, which would let a
rule that puts values in the wrong place look almost right.

**Provenance is verified, not assumed.** An observation with correct text
and incorrect provenance is not a match - a consumer that trusted its
location would be reading the wrong part of the document. Two named
policies exist: `EXACT` (the default, comparing the full chain including
span character ranges) and `LOCATION_ONLY` (coarser, for a corpus
annotated before offsets were recorded). The policy used is recorded on
every report, so a comparison between two evaluations can never be a
comparison between two definitions of "match".

Approximate *text* matching is absent. If it is ever introduced it must
be a named, versioned policy on the report, exactly as the provenance
policy already is.

### Metrics

Exact `Decimal`, quantised to six places, computed per corpus, per
document, per evidence type and per rule:

- **precision** - of what the extractor claimed, how much was right;
- **recall** - of what is there, how much it found;
- **F1** - computed from the counts as `2·TP / (2·TP + FP + FN)`, which
  avoids rounding twice; deriving it from already-quantised inputs loses
  a digit, and two evaluations differing only in that digit would read as
  a regression;
- the three **counts**, which are the primary record - "precision 0.75"
  says nothing about whether that was 3 of 4 or 300 of 400.

**Undefined is reported as `null`, never 0 or 1.** When the extractor
made no predictions, precision is not a number - it is a question that
was never asked. Reporting 0 would claim it was wrong about things it
never said; reporting 1 would claim it was right about them.

No probabilistic metrics: a deterministic extractor over a fixed corpus
produces the same counts every time, and dressing exact counts in
statistics would suggest an uncertainty that does not exist.

### Regression detection

Two reports are compared into a regression report that names **the exact
items**, not just the movement: new false positives, new false negatives,
and the ones a change resolved. "Precision fell from 0.94 to 0.91" is not
actionable; "these three observations became false positives, all from
rule `designation_generic` at 1.1, all on page 4" is.

Rule version changes are reported beside the metrics, so "which rule
changed?" is answerable from two reports alone. A comparison across
corpus versions is flagged `comparable: false` - still produced, because
it is often what you want, but a metric that moved when the corpus grew
has not told you anything about the rules.

### Persistence

Four tables added by migration `58327939f9a5`. Reports are
**insert-only**: a new rule version produces a new report and nothing is
overwritten, because the history is what regression detection is made of.

Evaluation never modifies engineering evidence - it runs the extractor
over corpus documents rather than reading stored evidence, because an
evaluation against stored evidence would measure what was stored on some
past day rather than what the current rules produce.

### API

```
GET  /evidence-evaluation/corpora
POST /evidence-evaluation/corpora/{corpus_id}/evaluate
GET  /evidence-evaluation/corpora/{corpus_id}/reports
GET  /evidence-evaluation/reports/{report_id}
GET  /evidence-evaluation/reports/{baseline}/compare/{candidate}
```

### The measured baseline

Against `substation_reference` version 1.0, at extraction policy 1.0:

| Metric | Value |
|---|---|
| True positives | 17 |
| False positives | 0 |
| False negatives | 1 |
| Precision | 1.000000 |
| Recall | 0.944444 |
| F1 | 0.971429 |

The single miss is `TR-1` in `designation_variants`: the designation
patterns recognise letters-then-digits, a numeric function code and an
IEC 81346 aspect, but **not** letters-hyphen-digits. An engineer reading
that document would call `TR-1` a designation. It is annotated in the
corpus so the gap is measured rather than forgotten, and so the milestone
that closes it can show recall rising rather than merely asserting an
improvement.

## Known debt

- The live Knowledge Graph upload path still performs ad-hoc LLM
  extraction from assembled text; migrating it onto this layer is a later
  milestone, and an architecture test pins the current absence of that
  dependency so the change will be deliberate when it comes.
- **The reference corpus is now part real** (EPIC 32.E2). Three of its
  eight documents are transcribed verbatim from a single Italian DSO's
  drawings and carry the document code, page and file checksum; the other
  five were written to exercise the rules. `ReferenceDocument.source`
  keeps the two distinguishable, so a metric cannot quietly measure the
  extractor against strings written to make it pass.
- **The real source set is dominated by functional diagrams.** Ten real
  documents, ~1,050 pages, nine of them functional diagrams plus one
  cable list. No single-line diagram, wiring diagram, equipment list,
  nameplate table, technical specification or bay data sheet. Extraction
  quality is measured on that family and should not be generalised
  beyond it.
- **Several real documents are effectively image-only.** Four yield under
  2,200 characters over 100+ pages. Their designations are not
  text-extractable at all, and **absence of extracted text is not
  evidence of absence of designations** - no OCR is performed and none is
  inferred.
- **Slash- and hyphen-qualified designations are not yet observed.** The
  real set writes `Q6/A`, `Q31/SB`, `A/COM`, `M-SA`, `X-VAC` and
  `Q9-1` - a further real family, measured and deliberately out of scope
  for 32.E2, which targeted the dot-qualified, bare-product and location
  families.
