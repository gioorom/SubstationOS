# Engineering Facts

**Status:** As-built reference for the **Engineering Fact Construction**
layer introduced in Milestone 29.2. For the entities it consumes, see
[engineering_entities.md](engineering_entities.md); for the layer that
assigns meaning to these facts, see
[engineering_semantics.md](engineering_semantics.md); for where it sits
in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## The pipeline

```
Engineering Evidence
    |
    v
Engineering Entity Resolution
    |
    v
Engineering Fact Construction     deterministic, versioned, no LLM
    |
    v
Engineering Semantic Interpretation   (Milestone 30.1)
    |
    v
Future Knowledge Graph Population     (a later milestone)
```

## Four meanings, kept apart

| Layer | Says |
|---|---|
| Evidence | "I observed `TR1` at this location." |
| Entity | "These `TR1` observations refer to one document-scoped object." |
| **Fact** | "This designation entity and this quantity entity satisfy a declared association rule." |
| Graph edge *(later)* | "This equipment has this rated property." |

**A fact is a structured association, not a classified engineering
property.** It records that a rule was satisfied - nothing more.

> **`HAS_ASSOCIATED_QUANTITY` does not mean rated power, voltage or
> current.** It means two entities appeared together under a stated
> structural rule. A transformer data sheet listing a *test* voltage
> beside a designation would produce exactly the same predicate as one
> listing a rated voltage, because the line does not say which it is.
> Promoting a quantity into a role is a semantic milestone with its own
> rule, its own version and its own evaluation. Milestone 30.1 does
> exactly that for **power alone** - see
> [engineering_semantics.md](engineering_semantics.md) - and leaves
> voltage and current uninterpreted for precisely this reason.

## The predicate vocabulary

Two members, in one module:

```
HAS_ASSOCIATED_QUANTITY
HAS_LOCATION_ASPECT
```

Both are **structural**, which is the whole point of this vocabulary.
`HAS_ASSOCIATED_QUANTITY` says two entities appeared together under a
declared rule. `HAS_LOCATION_ASPECT` (EPIC 32.P1) says a compound
IEC 81346 reference designation was written **containing** that location
aspect - the `+E01` inside `+E01-QA1`. Neither says what the association
*means*; that is assigned one layer up by a reviewed semantic rule
(`HAS_RATED_POWER`, `IS_LOCATED_IN`).

Deliberately absent: `HAS_VOLTAGE`, `HAS_CURRENT`, `HAS_POWER`,
`HAS_CABLE_SECTION`, `CONNECTED_TO`, `PROTECTS`, `FEEDS`, `BELONGS_TO`,
`IS_A`. The first four are property roles this layer cannot prove; the
last five are topology and classification, which are not its subject
matter at all.

`BELONGS_TO` is the instructive one. It is what `HAS_LOCATION_ASPECT`
would have been called if this layer were allowed to say what a
containment *means* - and it is exactly the name an architecture test
forbids here.

The quantity's evidence type - voltage, current, power, cable section -
stays reachable through the fact's **support**, so a later milestone has
what it needs to promote a role. Reading the evidence type as a predicate
here would be that promotion happening by accident. An architecture test
asserts the enum stays closed and that nothing else in the context
declares a predicate.

## The construction rule catalogue

### `same_line_association` 1.0

A designation entity and a quantity entity are associated when
contributing observations of both occur on the **same document line** -
same page, same block, same line index.

### `compound_reference_designation` 1.0

A designation entity and a structural-location entity are associated
when contributing observations of both were produced from the **same
token**, which happens only for a compound IEC 81346 reference
designation such as `+E01-QA1`.

Scope `TOKEN`, cardinality `ONE_SUBJECT_ONE_OBJECT`. This is the
narrowest scope in the catalogue and the strongest co-occurrence this
pipeline can record: the two observations did not merely appear near each
other, they came from the same characters.

That is why the objection below - which rules out a paragraph rule -
does not apply to it. There is no window whose width depends on how the
parser blocked a page; the unit is one token.

A designation on the *same line* as `+E01-QA1` receives no location
fact from **this** rule. It was not written inside it.

### `same_line_location_association` 1.0

A designation entity and a structural-location entity are associated
when the line carries **exactly one of each** and the two were written
as **separate tokens** - `MORSETTIERA -E.AM +GSH002`.

Scope `LINE`, cardinality `ONE_SUBJECT_ONE_OBJECT`, token relation
`DISTINCT_TOKENS`. Introduced by EPIC 32.P2.

It exists because the compound form, which `compound_reference_designation`
requires, does not occur in the real drawings this repository holds. The
committed Italian DSO functional diagram carries 52 location aspects
across 171 pages and **no compound tokens at all**; every location is
written as its own token beside the designation it belongs to. So the
governed `IS_LOCATED_IN` relationship EPIC 32.P1 built had no reachable
real instance until this rule.

**Why it is not "same line means related".** It is the strictest shape a
line can carry. Two designations, or two locations, produce nothing -
there is no nearest-token fallback, no ordering tie-break, no distance
and no threshold, exactly as for `same_line_association`. What it adds
over that rule is a stricter cardinality, not a looser one.

**Why the token relation is declared.** `LINE` and `TOKEN` scope overlap
on a line whose only content is `+E01-QA1`: that line carries one
designation and one location, so a line rule would match what the
compound rule already recorded. Two facts for one association exceed the
semantic catalogue's one-location-per-subject policy, so the statement
would be **refused as a contradiction** and the P1 relationship would
disappear on exactly the evidence it was built for.

`DISTINCT_TOKENS` prevents that in the catalogue, where the precondition
belongs, rather than in a deduplication pass that would have to choose
which fact to keep and would cost the provenance of the one it dropped.
The compound rule stays authoritative for pairs written inside one
token; the line rule stands aside.

It is applied as an **eligibility filter on the unit's objects, before
the cardinality tests**. That order matters: an object this rule may not
associate is not an ambiguity it should report. On `Trasformatore TR1
nel quadro +E01-QA1` the only location is bound inside one of the two
designations, so the line rule has no business on that line at all -
testing cardinality first would have it announce that it could not tell
which designation the location belonged to, on a line where the compound
rule had already determined exactly that.

### Refusals are recorded

Both line-scoped refusals produce a diagnostic, never a fact with a
softer status:

| On one line | Diagnostic |
|---|---|
| two or more designations, at least one eligible object | `MULTIPLE_SUBJECTS` |
| one designation, two or more objects, under `ONE_SUBJECT_ONE_OBJECT` | `MULTIPLE_OBJECTS` |

`MULTIPLE_OBJECTS` was added by EPIC 32.P2 because the shape it names
became reachable for the first time. Under `ONE_SUBJECT_MANY_OBJECTS`
the same shape is a data-sheet line and is associated, not refused, so
no diagnostic is produced there.

### Why no paragraph rule

The milestone brief permits a paragraph-level rule only if the
repository's evidence proves it can be conservative. **It does not.**

The canonical parser makes each separately-placed run of text its own
block, so a "paragraph" here is sometimes exactly one line and sometimes
a wrapped run of several unrelated ones - a title bar, a column of a
table, a stack of data-sheet rows. A paragraph rule would behave as a
line rule on some documents and as a several-lines-wide cartesian join on
others, with nothing in the data to tell the two apart. A rule whose
strictness depends on how the parser happened to block a page is not
deterministic; it is a coin flip with a version number.

### What is deliberately not used

No token-distance scoring, no nearest-neighbour, no geometry, no
same-page association, no punctuation-based inference, no document-wide
proximity, no thresholds, no fuzzy matching, no embeddings. Each would
introduce a number nobody calibrated deciding which equipment a rating
belongs to. An architecture test asserts that no similarity library is
imported and that no distance, score or threshold is computed anywhere in
the construction path.

## Cardinality and ambiguity

The policy is **declared**, not implied:

| On one line | Result | Why |
|---|---|---|
| 1 designation, N quantities | N facts | `ONE_SUBJECT_MANY_OBJECTS` - a data-sheet line listing a designation and several ratings is a real shape |
| M ≥ 2 designations, ≥ 1 quantity | **no facts**, one diagnostic | the line does not say which designation the quantity belongs to |
| 0 designations, or 0 quantities | nothing | no candidates |

**Ambiguous layout must not become a confirmed fact.** `TR1 TR2 630 kVA`
produces nothing: guessing would put a rating on the wrong equipment,
which is invisible in a graph and expensive in a substation.

Distinct entities are counted, not observations: `Trasformatore TR1,
sigla TR1, 630 kVA` names one transformer twice, and both observations
become support for one fact rather than triggering a false ambiguity.

A pair declined on an ambiguous line may still be confirmed from a
different, unambiguous line. The rule was satisfied there; the diagnostic
still records where it was not.

### Diagnostics are not facts

An ambiguous line is recorded as a `FactConstructionDiagnostic` in its
**own table**. It names no subject and no object - which is which is
precisely what could not be determined - and it is structurally invisible
to anyone querying `engineering_facts`. It is not a fact with a softer
status.

## Fact status

Derived from the contributing entities, never invented:

| Status | Meaning |
|---|---|
| `CONSTRUCTED` | The rule was satisfied and both entities are resolved |
| `AMBIGUOUS` | The rule was satisfied - the association is real - and a contributing entity is itself ambiguous, typically a quantity whose number could not be read exactly |

Note the distinction: `AMBIGUOUS` is about the **value** being unsettled,
not about whether the association holds. A pairing that could not be
determined produces no fact at all.

No numerical confidence scores. A rule matched or it did not.

## Support and provenance

**Facts invent no provenance. They aggregate support.**

Every fact can answer, without a text search:

- which subject entity created it (by key);
- which object entity created it (by key);
- which observations support it (by evidence key, with role);
- which rule at which version constructed it;
- where those observations occur - page, paragraph, line, token range.

The character-level chain is **not duplicated**: it stays on the evidence
item, which remains the authoritative record, and is reachable through
the immutable evidence key. Support is recorded at construction time and
never reconstructed later by searching text.

The line is stored on the support deliberately: a same-line association
is only credible if the line it matched on can be re-checked, and an
unverifiable rule is an assertion.

## Identity

`fact_key` is a SHA-256 over the document, the content checksum, the
resolution policy version, the triple (subject, predicate, object), the
construction rule and version, and the fact contract version.

- The same entities under the same rules always yield the same key.
- A rule or contract version bump yields different keys, so a
  re-construction is a **new set** rather than a silent rewrite.

The **line is deliberately absent** from the key: a fact is identified by
what it asserts, not by where it was seen, and its support accumulates
every co-occurrence that produced it.

## Persistence

Four tables added by migration `86c866388a33`: `engineering_fact_sets`,
`engineering_facts`, `engineering_fact_support`,
`engineering_fact_diagnostics`.

The stored key is `(document_id, artifact_identity)`.

`artifact_identity` is the deterministic identity of the computation
that produced this fact set: a digest over the identity contract, the
artifact kind, **the identity of the artifact it was derived from**, and
the versions this stage owns. Re-running the same computation finds the
stored result; any change upstream, or in this stage's own contract, is
a different identity and therefore a new artifact stored **alongside**
the old one - so a facts set drawn under last year's rules stays
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

**Entities are referenced by key, not by foreign key.** A later
re-resolution produces a new entity set, and a foreign key would either
block it or cascade a historical fact set into nothing. Fact history must
survive newer entities, so the reference is the deterministic entity key.
An architecture test asserts those columns carry no foreign key.

Insert-only: nothing is overwritten.

## API

```
POST /documents/{document_id}/engineering-facts            construct or re-use
GET  /documents/{document_id}/engineering-facts            the current set
GET  /documents/{document_id}/engineering-facts/{fact_key} one fact
GET  /documents/{document_id}/engineering-facts/{fact_key}/support
```

Five outcomes are distinguishable: constructed, constructed with
ambiguities, nothing associable, an existing set reused, and failed.
Constructing nothing is a success, and so is declining an ambiguous line.
No ORM model is exposed.

## The realistic cases

| Document text | Facts | Why |
|---|---|---|
| `TR1 630 kVA` | 1 | one designation, one quantity, one line |
| `TR1 20 kV 630 kVA` | 2 | one designation, two quantities - the declared one-to-many policy |
| `TR1 TR2 630 kVA` | **0** | two designations: which one the rating belongs to is not stated |
| `TR1` / `630 kVA` | **0** | different lines; the rule is same-line |
| `TR1 — 630 kVA` | 1 | the dash is another token; punctuation carries no meaning here |
| `TR1 \| 630 kVA` | 1 | a pipe is not a separator this layer interprets |
| `TR1 630 kVA 20/0.4 kV` | 1 | `20/0.4` is not a number the extractor reads, so there is no second quantity to associate |

The rules were **not** broadened to make every example produce output.
Two of them deliberately produce none.

## What the Knowledge Graph must do later

**Graph population must consume governed facts rather than
reconstructing relationships from text.** A graph builder that read
canonical text, or re-associated entities itself, would be deciding what
counts as an association in a second place under no rule version - and
two answers about the same document would exist.

**Every fact must be explainable through its entity and evidence
support.** That chain - fact → entities → evidence → characters - is what
lets an engineer disputing a graph edge be shown the line it came from.

## Known debt

- **One rule, one predicate.** The layer is deliberately narrow. Its
  usefulness depends entirely on the semantic milestones that read the
  support and promote roles - Milestone 30.1 promoted power and nothing
  else, so most facts still say something true and thin.
- **Construction is unmeasured.** Milestone 28.2's evaluation framework
  measures *extraction*. There is no corpus of expected entities or
  facts, so grouping and association quality are asserted by unit test
  rather than measured against annotated documents. This is now the
  second layer built on unmeasured rules.
- **Multi-line data sheets associate nothing.** A designation on a header
  line with ratings beneath it - a common real layout - produces no
  facts, because no rule covers it conservatively. Closing that gap needs
  either a table-structure notion in the canonical layer or a rule with
  evidence behind it.
- **Cross-document facts do not exist**, following cross-document entity
  resolution not existing.
