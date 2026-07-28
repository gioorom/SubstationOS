# Engineering Evidence

**Status:** As-built reference for the **Engineering Evidence Extraction**
layer introduced in Milestone 28.1. For the deterministic document
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
Future Entity Resolution           (not this milestone)
    |
    v
Future Knowledge Graph Population  (not this milestone)
```

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

Three shapes are recognised, each requiring letters and digits together:

| Shape | Matches | Does not match |
|---|---|---|
| letters then digits | `T1`, `TR1`, `QMT01`, `M1` | `TRASFORMATORE`, `AT`, `kV` |
| numeric function code | `52-Q1`, `189-SB1` | `145`, `20-30` |
| IEC 81346 aspect | `+E01`, `-QA1`, `+E01-QA1` | `+`, `-` |

Bare uppercase words, bare numbers, single letters and lower-case tokens
are all rejected. **The equipment category is never inferred from the
designation** - `QMT01` looks like a medium-voltage panel to an engineer,
and this layer records only that the designation-like text was observed.

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

## Known debt

The live Knowledge Graph upload path still performs ad-hoc LLM extraction
from assembled text; migrating it onto this layer is a later milestone,
and an architecture test pins the current absence of that dependency so
the change will be deliberate when it comes.
