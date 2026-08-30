# ADR-0030: Governed Structural Relationship Semantics Foundation

## Status

Accepted. Introduced by EPIC 32.P1, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant was weakened, bypassed,
renamed away or reinterpreted. This is the **first change to the shape
of the governed graph since AF-01 was written**, and it is an addition
to a vocabulary the freeze already governs rather than a change to what
any invariant means.

## Context

### Why this milestone exists at all

EPIC 32.2 — Governed Relationship & Topology Reasoning Foundation — was
attempted and **correctly stopped** with `BLOCKED_BY_ONTOLOGY`. The
audit that stopped it is the input to this ADR.

The governed graph held exactly one relationship:

```
HAS_RATED_POWER : ENGINEERING_ASSET -> ENGINEERING_QUANTITY
```

and `EDGE_ENDPOINT_KINDS` permitted that pair and no other. Three
consequences followed, and the third is the one that mattered:

1. Every governed edge started at an asset and ended at a quantity.
2. A quantity node could never be an edge *subject*.
3. Therefore the governed graph was a **depth-1 bipartite graph**: the
   longest path from any node was one hop.

A relationship inference of the shape `A --R1--> B --R2--> C` was
therefore not merely unsupported but *unconstructible*, under any data,
forever. The only shape that could be built — two assets sharing a rated
power quantity — was rejected as semantic overreach: two transformers
both rated 630 kVA share a magnitude, not a topology.

The missing capability was named precisely: **a governed relationship
whose both endpoints are structural objects**. This milestone supplies
exactly one, and no more.

### What the repository could actually prove

The discovery constraint was that no relationship may be invented to
unblock a later milestone. The evidence layer observes five things —
designations and four quantity kinds — and every extraction rule is
`SINGLE_TOKEN` or `QUANTITY`. There is no table-structure evidence, no
drawing geometry, and no rule that observes a relation between two
things.

One thing in the repository does carry structure, and it was already
there: the designation pattern catalogue recognises **IEC 81346**
reference designations.

```python
DESIGNATION_IEC_81346 = re.compile(
    r"^[+\-][A-Z]{1,3}[0-9]{1,3}(?:-[A-Z]{1,3}[0-9]{1,3})?$"
)
```

`+E01-QA1` was already being observed — as one opaque designation. But
IEC 81346-1 assigns `+` to the **location aspect** and `-` to the
**product aspect**, so that string is not opaque: it designates the
object `-QA1` in the context of location `+E01`. That is a published,
international standard's reading of a syntax the document itself chose
to use.

## Decision

### 1. The first structural relationship

```
IS_LOCATED_IN : ENGINEERING_ASSET -> STRUCTURAL_LOCATION
```

read from the location aspect of a **compound** IEC 81346 reference
designation. `+E01-QA1` is located in `+E01`.

Exactly one relationship family ships. `CONNECTED_TO`, `FEEDS`,
`PART_OF`, `UPSTREAM_OF`, `HAS_TERMINAL` and the rest were evaluated and
rejected; each is recorded below with the reason.

### 2. Why this inference is engineering-semantically valid

Because it is not an inference about the world — it is a **reading of a
standard's syntax**, and the two entities come from *the same
characters*.

This is the distinction that matters, and it is worth stating in the
terms the fact-construction catalogue already uses. `HAS_ASSOCIATED_QUANTITY`
rests on `SAME_LINE_ASSOCIATION`: two entities are associated because
they appeared on one line. That rule was accepted because a line is a
line — there is no window to calibrate. The location rule is scoped
*more* tightly still: `StructuralScope.TOKEN`, meaning the designation
and the location aspect were produced from one token.

So the objections that sink page-level, paragraph-level and geometric
association do not apply. There is no distance, no threshold, no
nearest-neighbour, no coordinate. Either the document wrote `+E01-QA1`
or it did not.

**And it is still reviewed.** The reading is declared as a versioned
semantic rule and an engineer approves each statement before it becomes
governed. If a document uses `+` for something other than a location,
the reviewer rejects the statement and no knowledge is published — the
same protection every other interpretation in this platform has.

### 3. Candidates evaluated and rejected

| Candidate | Would need | Why rejected |
|---|---|---|
| **Explicit connection** (`CONNECTED_TO`) | Evidence that two objects are joined | Nothing in the pipeline observes a connection. Deriving one from adjacency, alignment or shared line would be exactly the geometry-as-topology error. |
| **Terminal association** | A terminal entity and terminal evidence | No evidence type, no entity type. |
| **Feeder / source-destination** (`FEEDS`) | Direction-bearing evidence | The ontology encodes no electrical direction at all. Reading it off edge orientation would be inventing it. |
| **Equipment-to-bay membership** | A governed bay vocabulary | `+E01` is a *location*; that it is a bay rather than a room, panel or building is a classification nobody governs. Modelled generically instead. |
| **Panel membership** | As above | As above. |
| **Product-within-product** (`-QA1-XB2`) | Nothing new — it is observable | **Deferred, not impossible.** It is a real second relationship (component of a product) and §10 permits only one. It is explicitly refused today: the compound pattern requires `+`. |
| **Protection-target association** | Protection evidence | No evidence type, no entity type, no statement type. |
| **Functional association** | A function vocabulary and an assigning rule | Neither exists. |
| **Shared rated power** | Nothing — it is constructible | Rejected as overreach. Identical ratings are commonplace across unrelated equipment. This is the candidate EPIC 32.2 already refused. |

### 4. Governed relationship vs derived relationship

Unchanged, and worth restating because this milestone makes the
distinction easier to blur:

`IS_LOCATED_IN` is **governed knowledge**. It came from a document,
through a versioned rule, and an engineer approved it. It is a
`GraphEdge`.

Anything concluded *from* two `IS_LOCATED_IN` edges — for instance that
two assets in one location are related to each other — is an
**inference**, is not governed, and is not a `GraphEdge`. That remains
EPIC 32.2's problem, and ADR-0029's boundary continues to govern it.

**No topology reasoning was implemented here.** `engineering_reasoning`
is byte-for-byte unchanged.

### 5. Graph reachability still does not imply engineering meaning

This milestone creates, for the first time, a governed graph in which
two assets can be reached from one another in two hops:

```
+E01-QA1 --IS_LOCATED_IN--> +E01 <--IS_LOCATED_IN-- +E01-QB1
```

That path exists and means **nothing beyond what it says**: two devices
are in the same place. It does not say they are connected, that one
feeds the other, that they are on one busbar, or that current flows
between them. A substation location routinely holds equipment from
several unrelated circuits.

A future rule that wants to conclude something from this path must
justify the conclusion on engineering grounds and carry its own rule id
and version. The path being traversable is not the justification.

### 6. The pipeline, stage by stage

Every stage is the existing stage, with one catalogue entry added. No
stage was bypassed and no new writer was created.

| Stage | Added | Identity |
|---|---|---|
| Evidence | `EvidenceType.LOCATION_ASPECT`, rule `location_aspect_iec_81346` v1.0 | `sha256(document, checksum, rule, version, type, page, paragraph, line, tokens)` |
| Entities | `EntityType.STRUCTURAL_LOCATION`, rule `location_aspect_grouping` v1.0 | Existing entity key — **document-scoped** |
| Facts | `FactPredicate.HAS_LOCATION_ASPECT`, rule `compound_reference_designation` v1.0, scope `TOKEN`, cardinality `ONE_SUBJECT_ONE_OBJECT` | Existing fact key |
| Semantics | `SemanticStatementType.IS_LOCATED_IN`, rule `location_from_compound_reference_designation` v1.0 | Existing statement key |
| Human Review | *nothing* — the existing lifecycle carries it | Existing review snapshot |
| Promotion | *nothing* — vocabulary-driven, no code change | Existing edge id |
| Graph | `GraphNodeKind.STRUCTURAL_LOCATION`, `GraphEdgeKind.IS_LOCATED_IN`, endpoint pair | Existing node/edge identity |
| Retrieval | `GovernedResultKind.STRUCTURAL_LOCATION` | Existing result identity |
| Context Assembly | *nothing* | — |
| Reasoning | *nothing* | — |

That promotion required **no code change at all** is the strongest
evidence the vocabulary was the only thing missing: `evaluate()` is a
pure function of the three mapping tables, so a new relationship that
obeys the tables is admitted by the rules that were already there.

### 7. Evidence provenance points at the characters, not the token

The location observation covers `+E01` — four characters — and not the
eight characters of `+E01-QA1`. This is the only observation in the
catalogue that covers *part* of a token, which is why it has its own
`RuleKind` and why the extractor narrows the character range explicitly.

An observation pointing at the whole token would have claimed the
document wrote `+E01` where it wrote `+E01-QA1`. Provenance is the
reason to trust any of this, so it is exact.

Both observations are kept: `+E01-QA1` is a designation that was
written, and `+E01` is a location aspect written inside it. The evidence
key covers the rule and the evidence type, so they are two records, not
one overwriting the other.

### 8. Fact is structural; semantics assigns meaning

`HAS_LOCATION_ASPECT` says the document wrote one inside the other.
`IS_LOCATED_IN` says the equipment is located there. The first is
structural and needs no engineering judgement; the second is a meaning
and is reviewed.

This is deliberately the same two-layer split as
`HAS_ASSOCIATED_QUANTITY` → `HAS_RATED_POWER`, and it is why the fact
predicate is **not** named `BELONGS_TO` — which the fact-vocabulary
architecture test explicitly forbids.

### 9. Identity and cross-document policy

Entity identity is **document-scoped**, unchanged: the entity key is a
SHA-256 over the document id, content checksum, extraction policy
version, rule id and version, entity contract version, entity type and
discriminator.

So two documents that both write `+E01` produce **two governed
locations**, and they are not merged. Cross-document entity resolution
remains out of scope and was not introduced. Deciding that two documents
mean one place is a capability that needs its own milestone and its own
review.

Within one document, a `+E01` written alone and a `+E01` read out of
`+E01-QA1` are also two entities — different claims, different evidence
types, different rules.

### 10. What is deliberately not claimed

- **No location classification.** `+E01` is a designated location. Bay,
  panel, room, building — none is asserted.
- **No direction.** Edge orientation records which endpoint is the
  subject of the reviewed statement. It is grammatical, not electrical.
- **No equipment state.** Nothing about energisation, breaker position
  or service status.
- **No connectivity.** Containment is not a circuit.
- **No transitivity.** Nothing composes two statements into a third; the
  interpreter applies each rule independently and every statement has
  exactly one supporting fact.

### 11. Persistence and migration

**No migration.** The four affected columns are `SqlEnum` columns
rendered as `VARCHAR(n)` with no `CHECK` constraint, and `n` is derived
from the longest member value. Every new member is shorter than the
current longest, so the DDL is unchanged:

| Column | Length | Longest member |
|---|---|---|
| `engineering_evidence.evidence_type` | 19 | `cable_section_value` (`location_aspect` is 15) |
| `engineering_entities.entity_type` | 21 | `equipment_designation` (`structural_location` is 19) |
| `engineering_facts.predicate` | 23 | `has_associated_quantity` (`has_location_aspect` is 19) |
| `engineering_semantic_statements.statement_type` | 15 | `has_rated_power` (`is_located_in` is 13) |

Graph `kind` columns are `String(60)` and were never enum-typed.

**Existing data is not backfilled.** Documents processed before this
milestone have no location evidence and therefore no location
relationships. They acquire them only by being re-run through the
pipeline and re-reviewed. No historical row is converted into a
structural relationship, and no approval is manufactured.

### 12. API

**No new endpoint.** The relationship is exposed through the resources
that already exist: `/knowledge-graph/nodes`, `/knowledge-graph/edges`,
the semantics and review routes, and the governed retrieval endpoint.

The OpenAPI change is **purely additive** — six enum members and
docstring text, no path added, changed or removed. No relationship-write
API exists, and none was added: promotion consumes internal artefacts
and the graph repository is unreachable from any route.

### 13. LLM boundary

Untouched, and untested by this milestone: the extraction path is
deterministic regular expressions and the interpretation path is a
declared rule catalogue. No LLM participates in producing, interpreting,
reviewing or promoting a structural relationship.

## Consequences

### Good

- EPIC 32.2 is unblocked. A governed relationship between two structural
  objects exists, and the "shared structural parent" shape it named is
  reachable: two assets, one location, two governed edges.
- The addition cost almost no code. Promotion, Human Review, Context
  Assembly and Reasoning required **zero** changes, which is what a
  well-factored governed pipeline should look like when its vocabulary
  grows.
- Evidence-extraction quality is now measured for the new rule on the
  same terms as every other: the reference corpus baseline moved from
  17/18 to 18/19 exact matches, deliberately and with the numbers pinned.

### Costs and risks

- **The graph is no longer depth-1.** Two-hop paths between assets now
  exist. They are meaningless on their own, and the temptation to read
  them as topology is the single largest risk this milestone creates.
  Architecture tests forbid the vocabulary that would express it, but no
  test can forbid a future rule from being written badly.
- **The `+` reading is a judgement about documents.** A document that
  uses `+` for something else will produce a wrong statement. It is
  caught by review rather than by extraction, which is the correct place
  but not a free one.
- **One relationship is a small ontology.** Location membership does not
  make a substation model. It is one honest relationship, not a
  foundation for claiming topological coverage.

### Debt recorded, not paid

- Product-within-product (`-QA1-XB2`) is observable and not observed.
- Function aspect (`=`) is in IEC 81346 and not recognised at all.
- Location *classification* has no governed vocabulary.
- Cross-document location identity is unresolved by design.

## Conditions for resuming EPIC 32.2

1. A relationship reasoning rule must justify its conclusion on
   engineering grounds — reachability over `IS_LOCATED_IN` is not a
   justification.
2. It must carry its own `rule_id` and `rule_version`.
3. It must not treat containment as connectivity, and must not read
   direction or state from it.
4. Absence of a location edge must map to insufficient knowledge, not to
   a negative conclusion: the governed graph is a partial projection of
   what reviewers approved and has no complete-world basis.
5. Two documents' identically-named locations must remain distinct.

## References

- [ADR-0029: Deterministic Engineering Reasoning Foundation](0029-deterministic-engineering-reasoning-foundation.md)
- [ADR-0024: Governed Knowledge Graph as Projection](0024-governed-knowledge-graph-as-projection.md)
- [ADR-0023: Human Review — Append-Only Judgement](0023-human-review-append-only-judgement.md)
- [ADR-0026: Governed Structured Retrieval](0026-governed-structured-retrieval.md)
- [ADR-0027: Governed Context Assembly](0027-governed-context-assembly.md)
- [ADR-0004: Reviewed Facts Only in the Queryable Graph](0004-reviewed-facts-only-in-queryable-graph.md)
- [Architecture Freeze AF-01](../architecture_freeze_af01.md)
- IEC 81346-1, *Industrial systems, installations and equipment and
  industrial products — Structuring principles and reference
  designations*
