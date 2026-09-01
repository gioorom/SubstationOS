# Engineering Semantics

**Status:** As-built reference for the **Engineering Semantic
Interpretation** layer introduced in Milestone 30.1. For the facts it
consumes, see [engineering_facts.md](engineering_facts.md); for where it
sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## The pipeline

```
Engineering Facts
    |
    v
Engineering Semantic Interpretation   deterministic, versioned, no LLM
    |
    v
Engineering Semantic Set              immutable, persisted, fact-supported
    |
    v
Future Knowledge Graph Population     (the next milestone)
```

Three responsibilities, deliberately separated:

- **Semantic Interpretation assigns engineering meaning.**
- **The Knowledge Graph stores interpreted knowledge.**
- **Reasoning consumes interpreted knowledge.**

This layer is the first of the three, and it stops when the meaning is
assigned.

## Five meanings, kept apart

| Layer | Says |
|---|---|
| Evidence | "I observed `630 kVA` here." |
| Entity | "These observations refer to one quantity." |
| Fact | "This designation and this quantity are structurally associated." |
| **Semantic statement** | "This designation **has rated power** this quantity." |
| Graph edge *(later)* | the same knowledge, stored for querying and reasoning |

Every layer beneath this one was built to say *less* than it might have.
This is where meaning is finally assigned - and **only** where a
declared, versioned rule says so.

## The statement vocabulary

Exactly one member, in one module:

```
HAS_RATED_POWER
```

Deliberately absent: `HAS_NOMINAL_VOLTAGE`, `HAS_NOMINAL_CURRENT`,
`HAS_CABLE_SECTION`, `CONNECTED_TO`, `PROTECTS`, `SUPPLIES`,
`IS_TRANSFORMER`, `IS_BREAKER`, `BELONGS_TO`, `IS_PRIMARY_EQUIPMENT`.

The voltage and current statements look like the natural next step and
are not. **A voltage beside a designation may be a rated voltage, a test
voltage, an insulation level, or the voltage of the busbar the equipment
connects to**, and the association alone does not distinguish them. Power
is interpreted first because a `kVA` figure beside a designation is a
rating far more reliably than a `kV` figure is - and even that is a
judgement, which is why it is declared in a catalogue with a version
rather than assumed.

The classification statements (`IS_TRANSFORMER`, …) are a different kind
of claim and need a governed equipment vocabulary that does not exist.

`CONNECTED_TO` deserves naming twice, because `IS_LOCATED_IN` (EPIC
32.P1) can look like a step towards it and is not. Two objects sharing a
location are in the same place, which is not a circuit. Connectivity
needs evidence that two objects are **joined**, and no rule in this
repository observes that.

## The semantic rule catalogue

### `rated_power_from_associated_power_quantity` 1.0

| Property | Value |
|---|---|
| supported fact predicate | `HAS_ASSOCIATED_QUANTITY` |
| required evidence type | `power_value` |
| max supporting objects | 1 |
| resulting statement | `HAS_RATED_POWER` |

A designation associated with **exactly one** power quantity has that
quantity as its rated power.

### `location_from_compound_reference_designation` 1.0

| Property | Value |
|---|---|
| supported fact predicate | `HAS_LOCATION_ASPECT` |
| required evidence type | `location_aspect` |
| max supporting objects | 1 |
| resulting statement | `IS_LOCATED_IN` |

Introduced by EPIC 32.P1, and the first rule here whose object is not a
quantity.

A designation written as a **compound IEC 81346 reference designation**
is located in the location its `+` aspect names: IEC 81346-1 assigns `+`
to the location aspect, so `+E01-QA1` designates an object in the
context of location `+E01`.

**This is a reading of a standard's syntax, not a proximity rule.** Its
supporting fact is scoped to a single *token* - the designation and the
location aspect were produced from the same characters, not from the
same line, page or drawing. There is no window to widen and no threshold
to tune. Two different location aspects for one subject produce no
statement: the document disagreed with itself, and this rule does not
choose.

It says where equipment is. It does **not** say what it is connected to,
which direction anything flows, what kind of place `+E01` is, or that
two assets sharing a location have anything to do with each other. See
[ADR-0030](adr/0030-governed-structural-relationship-semantics.md).

**No executable engineering rule exists outside this catalogue**, and an
architecture test asserts nothing else in the context constructs a
`SemanticRule`. A rule elsewhere would be an engineering judgement nobody
could find, version or review - while every stored statement cites a rule
version.

### Why the required evidence type is a declared string

`EvidenceType` lives in the Engineering Evidence context, and this layer
is **not permitted to depend on it**: only Engineering Facts cross the
boundary. The evidence type is already available on the fact's support,
where Milestone 29.2 recorded it, so the catalogue names the one it
requires as a literal and a test asserts it equals
`EvidenceType.POWER_VALUE`. Same discipline as `ClassifiedFormat` against
`DocumentFormat`: two contexts agreeing on a vocabulary without coupling,
with drift caught by test.

## Ambiguity

**Two associated power quantities produce no statement**, and one
diagnostic.

The reason is structural and worth stating: a fact carries entity
**keys**, not values. This layer cannot see whether `400 kVA` and
`500 kVA` agree - and reaching for the figures would mean depending on
entities, which is not its business. Interpreting either would be a coin
flip on an equipment rating.

A boundary that forces the conservative answer is a boundary in the right
place.

Diagnostics live in their **own table**, with no object and no
statement-type column, so an undecided meaning is structurally invisible
to anyone querying interpreted knowledge. An ambiguous subject is not a
statement with a softer status.

## Statement status

Derived from the supporting fact, never invented:

| Status | Meaning |
|---|---|
| `INTERPRETED` | The rule applied and the supporting fact is itself constructed |
| `AMBIGUOUS` | The rule applied and the supporting fact is ambiguous - typically a quantity whose figure could not be read exactly |

Interpretation adds meaning; it never adds certainty. A rated power read
from `1.250 kVA` is still a rated power statement, and still says the
figure is unsettled.

No numerical confidence. No probabilistic inference. A rule applied or it
did not.

## Support

**Semantic statements own no provenance.** The chain is:

```
Semantic Statement
   -> Engineering Fact          (by fact key)
        -> Engineering Entity   (by entity key)
             -> Engineering Evidence   (by evidence key)
                  -> Canonical Text    (page, paragraph, line, tokens)
                       -> Canonical PDF (span character ranges)
                            -> Original Document
```

Every link is a key into an immutable record, never a copy. That chain is
why an engineer disputing "TR1 has rated power 630 kVA" can be shown the
characters on the page that produced it - and it is walkable over the
API, endpoint by endpoint.

**No fact payload is duplicated**, and a statement carries **no value or
unit**: the figure lives on the quantity entity, and a copy here would be
a second source of truth for a rated value - the worst possible thing to
have two of.

## Identity

`statement_key` is a SHA-256 over the document, the whole upstream source
identity, the triple, and the rule and contract versions.

- The same facts under the same rule always yield the same key.
- A rule version bump yields different keys, so a reinterpretation is a
  **new set** rather than a silent rewrite.

## Failures

| Code | When |
|---|---|
| `fact_set_missing` | The document has no engineering facts |
| `unsupported_semantic_rule` | A statement cites a rule or version the catalogue does not declare |
| `unsupported_fact_version` | Facts built under a construction policy this interpreter does not know |
| `invalid_support` | A statement cites facts not in the source set, or facts relating different entities |
| `ambiguous_semantic_mapping` | A set contains two statements of one type for one subject - a defect, caught before storage |
| `semantic_validation_failure` | The set violates an invariant |
| `semantic_persistence_failure` | Interpreted, and could not be stored |
| `inconsistent_source_identity` | The facts describe a different document or version |

Ambiguity **within** a subject is not in this list: it produces a
diagnostic and the interpretation still succeeds.

## Persistence

Four tables added by migration `7300ff6a7531`:
`engineering_semantic_sets`, `engineering_semantic_statements`,
`engineering_semantic_statement_support`,
`engineering_semantic_diagnostics`.

The stored key is `(document_id, artifact_identity)`.

`artifact_identity` is the deterministic identity of the computation
that produced this semantic set: a digest over the identity contract, the
artifact kind, **the identity of the artifact it was derived from**, and
the versions this stage owns. Re-running the same computation finds the
stored result; any change upstream, or in this stage's own contract, is
a different identity and therefore a new artifact stored **alongside**
the old one - so a statements set drawn under last year's rules stays
explainable.

Nothing here restates the versions of the stages above: they reach this
identity through the upstream one. That is the whole point - the earlier
model copied them down by hand, and the copy drifted six times. See
[ADR-0032](adr/0032-upstream-identity-in-derived-set-reuse.md) and its
EPIC 32.E2.4 amendment.

Every explicit provenance column stays readable beside the digest -
which policy, which contract, which checksum. Identity compresses; it
does not replace explanation. Rows stored before the identity chain
existed carry `NULL`, can never satisfy a lookup, and are recomputed
rather than trusted.

`extraction_policy_version` is **provenance, not identity**. It records
which reading of the document these results ultimately rest on, so the
artifact can explain itself without anyone reversing a digest - but the
reuse decision is the identity above, which reaches the extraction
policy through the upstream chain rather than by naming it here. It was
added by migration `c1f80d54ea27` and is nullable for rows stored before
it existed.

Entities and facts are referenced by **deterministic key, not foreign
key**: upstream re-runs produce new sets, and a foreign key would either
block that or cascade a historical interpretation into nothing.
Insert-only.

## API

```
POST /documents/{document_id}/engineering-semantics                  interpret or re-use
GET  /documents/{document_id}/engineering-semantics                  the current set
GET  /documents/{document_id}/engineering-semantics/{statement_key}  one statement
GET  /documents/{document_id}/engineering-semantics/{statement_key}/facts
```

Outcomes are distinguishable: completed, completed with nothing meaning
anything, reused, and failed - with `has_ambiguities` reporting declined
subjects. No ORM model is exposed.

## The realistic cases

| Association | Statement | Why |
|---|---|---|
| `TR1` → `630 kVA` | `HAS_RATED_POWER` | the object is a power observation and the only one; the declared rule maps exactly this |
| `TR1` → `20 kV` | **none** | a voltage may be rated, test, insulation or busbar voltage - the association does not say which, so no rule ships |
| `TR1` → `240 mm²` | **none** | a cable section is not a property of the designation the association names, and no rule declares a meaning for it |
| `TR1` → `20 kV` **and** `630 kVA` | one statement | the voltage is ignored, not refused; the power is interpreted |
| `TR1` → `400 kVA` **and** `500 kVA` | **none** + diagnostic | which figure is the rating cannot be decided from keys alone |

The catalogue was **not** widened to give every association a meaning.

## What the Knowledge Graph must do next

Graph population consumes **semantic statements**, not facts, entities or
text. A graph builder that read any of those would be assigning meaning
in a second place, under no rule version - and two accounts of what a
document means would exist.

## Known debt

- **Two rules, two statement types.** Each is useful only in proportion
  to how often documents write in the shape it reads: a designation and
  its rating on one line, and a compound IEC 81346 reference
  designation.
- **The `+` reading is a judgement about documents.** A document using
  `+` for something other than a location produces a wrong statement.
  That is caught by review rather than by extraction - the correct place,
  but not a free one.
- **Only the location aspect is read.** `-QA1-XB2` (a product within a
  product) and the `=` function aspect are observable in principle and
  interpreted by nothing.
- **Interpretation is unmeasured.** Milestone 28.2's evaluation framework
  measures *extraction*. There is still no corpus of expected entities,
  facts or statements - so grouping, association and now **meaning** are
  all asserted by unit test rather than measured. This is the third layer
  built on unmeasured rules, and it is the one where being wrong is most
  expensive: a wrong rated power is an engineering claim, not a parsing
  slip.
- **The `kVA`-is-a-rating judgement is untested against real documents.**
  A data sheet can list a throughput, a loss or a short-circuit power in
  kVA. The rule assumes the common case and nobody has checked how common
  it is.
