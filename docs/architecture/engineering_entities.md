# Engineering Entities

**Status:** As-built reference for the **Engineering Entity Resolution**
layer introduced in Milestone 29.1. For the evidence it consumes, see
[engineering_evidence.md](engineering_evidence.md); for where it sits in
the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## The pipeline

```
Engineering Evidence
    |
    v
Engineering Entity Resolution     deterministic, versioned, no LLM
    |
    v
Engineering Entity Set            immutable, persisted, evidence-backed
    |
    v
Future Knowledge Graph Population (a later milestone)
```

## Evidence, entity, node - three different things

This is the distinction the whole layer exists to make, and it is worth
stating in one place:

| Artefact | Says | Example |
|---|---|---|
| **Evidence** | "I observed this, here, under this rule." | `T1` appeared on page 1, paragraph 0, tokens 1-2 |
| **Entity** | "These observations refer to the same engineering object." | those three `T1` observations are one thing |
| **Graph node** *(later)* | "This object exists in the installation, and relates to others." | not this milestone |

An entity is a **deterministic hypothesis**: it follows from a stated
rule at a stated version, and it can be recomputed from the same evidence
at any time. It is not yet a node in the Project Knowledge Graph, and
nothing in this milestone writes one. A later milestone will generate
graph nodes from entities - from these, and from nothing else.

### What entity resolution does not answer

- "this object feeds another";
- "this object protects another";
- "this object belongs to a bay";
- "this quantity is that object's rating";
- "this designation names a transformer".

Every one of those is a claim about the *installation* rather than about
the document, and each belongs to a stage that can be reviewed as
reasoning. There is no field in the model and **no column in the schema**
in which any of them could be written, and an architecture test asserts
both stay that way.

## The supported catalogue

Deliberately minimal:

| Entity type | Is | Is not |
|---|---|---|
| `EQUIPMENT_DESIGNATION` | a designation-like string observed one or more times in a document | a transformer, a breaker, a CT, a VT, a relay or a cable |
| `ENGINEERING_QUANTITY` | a quantity observed in a document | a property *of* anything |

There is no transformer, breaker, current transformer, voltage
transformer, relay or cable class. Deciding that `T1` names a transformer
is a **classification**, and a classification needs a rule somebody
reviewed and a vocabulary somebody governs. Naming those classes now
would let the shape of the model imply knowledge the system does not
have.

## Resolution rules

One catalogue, versioned, and every stored entity cites the rule that
produced it.

### `designation_grouping` 1.0

Designation observations resolve to one entity when they share:

1. **the normalised designation** - the thing being named;
2. **the evidence status** - an `AMBIGUOUS` observation and an `OBSERVED`
   one are different claims about how much is known, and merging them
   would launder the uncertainty away;
3. **the extraction rule version** - two observations recognised under
   different definitions are not interchangeable, and treating them as
   one would hide a rule change inside an entity.

Deliberately *not* part of the key: the observed text. `(T1),` and `T1`
normalise to the same designation and are the same object - that is what
normalisation is for.

Grouping is **within one document**. Two documents writing `T1` may mean
two different transformers; deciding otherwise is cross-document
resolution, which this milestone does not perform.

### `quantity_identity` 1.0

Each quantity observation resolves to its own entity. **Nothing merges
two quantities.** Two observations of `630 kVA` in one document may be
one transformer's rating written twice, or two transformers with the same
rating; the document does not say, and neither does this resolver.
Merging them would be a guess that arrives downstream as one piece of
equipment where there were two.

> **`630 kVA` beside `TR1` is not yet a transformer rating.** It is two
> entities that do not know about each other. Adjacency is a fact about
> ink; attribution is a judgement, and it belongs to a later milestone.

### No fuzzy matching, anywhere

No edit distance, no embeddings, no similarity score, no model. Two
observations are the same object because a **stated rule** says so, or
they are not. A resolver that grouped `TR1` with `TR-1` because they look
alike would be guessing, and the guess would arrive downstream as an
equipment record nobody could question.

## Identity

`entity_key` is a SHA-256 over the document, the exact evidence source,
the rule and its version, the entity contract version, and whatever
distinguishes an entity from its siblings.

- The same evidence under the same rules always yields the same key -
  which lets the schema enforce idempotency rather than merely hope for
  it.
- A rule version bump yields different keys - which makes a re-resolution
  a **new set** rather than a silent rewrite.

Three versions are recorded on every entity or set, because they change
for different reasons: `extraction_policy_version` (which rules found the
observations), `resolution_policy_version` (which rules grouped them), and
`entity_version` (the shape of an entity itself).

## Provenance

**Entities never own provenance. They aggregate it.**

Each contributing observation is referenced by its `evidence_key`,
together with the location it occupied - page, paragraph, line, token
range. The character-level chain stays on the evidence item, which
remains the authoritative record; an entity that copied it would become a
second source of truth for where a thing was seen.

Every entity can enumerate the evidence that created it, and **no entity
exists without at least one** - validation refuses an entity citing none,
because an entity with no evidence is an assertion rather than a
hypothesis.

## Status

An entity's status is **derived from its evidence**, never invented:

| Evidence status | Entity status |
|---|---|
| `OBSERVED` | `RESOLVED` |
| `AMBIGUOUS` | `AMBIGUOUS` |

The uncertainty recorded at extraction time survives into the hypothesis
rather than being laundered away by the act of grouping.

## Failures

| Code | When |
|---|---|
| `evidence_set_missing` | The document has no engineering evidence |
| `unsupported_extraction_policy_version` | Evidence built under a policy this resolver does not know |
| `invalid_resolution_rule` | An entity cites a rule or version the catalogue does not declare |
| `resolution_failure` | A rule raised - the one genuinely unknown cause |
| `entity_validation_failure` | The set violates an invariant - an entity with no evidence, or two typed values |
| `entity_persistence_failure` | Resolved, and could not be stored |
| `inconsistent_source_identity` | The evidence describes a different document or version |

## Persistence

Three tables added by migration `46ec4e0fe42f` (purely additive):
`engineering_entity_sets`, `engineering_entities`,
`engineering_entity_evidence`.

The stored key is
`(document_id, content_checksum, resolution_policy_version)`. Re-running
finds the existing set and re-uses it; new evidence or new rules produce
a new set **alongside** the old one, so a hypothesis drawn under last
year's rules stays explainable.

Nothing here references or modifies the evidence tables, canonical text,
the document row, the Engineering Index or the Knowledge Graph.

## API

```
POST /documents/{document_id}/engineering-entities              resolve or re-use
GET  /documents/{document_id}/engineering-entities              the current set
GET  /documents/{document_id}/engineering-entities/{entity_key} one entity
GET  /documents/{document_id}/engineering-entities/{entity_key}/evidence
```

Resolving nothing is a success, not a failure: a document may contain no
observations these rules group into anything. No ORM model is exposed.

## Known debt

- **Cross-document resolution does not exist.** `T1` in two documents is
  two entities. That is the correct conservative default and also a real
  limitation: a substation's equipment appears across a drawing set, and
  uniting those observations needs a rule about document scope that
  nobody has written yet.
- **Quantities are never attributed.** Every quantity is its own entity,
  which is honest and not yet useful: the value of `630 kVA` is knowing
  what it rates. That attribution is the next reasoning step and needs
  its own evaluation before it can be trusted.
- **Resolution is unmeasured.** Milestone 28.2's evaluation framework
  measures *extraction*; there is no corpus of expected **entities** yet,
  so grouping quality is asserted by unit test rather than measured
  against annotated documents.
