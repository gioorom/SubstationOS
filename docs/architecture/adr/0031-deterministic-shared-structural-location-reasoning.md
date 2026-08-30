# ADR-0031: Deterministic Shared Structural Location Reasoning

## Status

Accepted. Introduced by EPIC 32.2 (resumed), under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant was weakened, bypassed,
renamed away or reinterpreted. **No governed ontology was added**: the
governed graph carries exactly what EPIC 32.P1 left it carrying.

## Context

### Why this milestone stopped once, and what unblocked it

EPIC 32.2 was attempted and correctly stopped with `BLOCKED_BY_ONTOLOGY`.
The governed graph held one relationship, `HAS_RATED_POWER`, whose object
is a quantity, and `EDGE_ENDPOINT_KINDS` permitted that pair only. Every
edge therefore ran asset → quantity, a quantity could never be an edge
*subject*, and the graph was **depth-1 bipartite**: a two-hop path was
unconstructible under any data, forever.

[ADR-0030](0030-governed-structural-relationship-semantics.md) (EPIC
32.P1) supplied the missing capability — one governed relationship whose
both endpoints are structural:

```
IS_LOCATED_IN : ENGINEERING_ASSET -> STRUCTURAL_LOCATION
```

read from the location aspect of a compound IEC 81346 reference
designation. This milestone is the narrow reasoning capability that
relationship makes honest, and nothing more.

### The engineering question

> Does governed knowledge establish that these two assets stand in the
> same governed structural location?

Two approved statements can now say `+E01-QA1 IS_LOCATED_IN +E01` and
`+E01-QB1 IS_LOCATED_IN +E01`. Neither document says the two devices are
in one place *together*. That is a conclusion, and this rule is the first
thing in the platform allowed to draw it.

## Decision

### 1. Exactly one rule, in a second explicit family

| Property | Value |
|---|---|
| `rule_id` | `shared_structural_location` |
| `rule_version` | `1.0` |
| `rule_family` | `STRUCTURAL_RELATIONSHIP` |

`QUANTITY_CONSISTENCY` is unchanged and unrenamed. There is no rule
engine, no registry, no DSL and no plugin lookup: two rules are two
functions and one branch.

### 2. The semantic limit

It concludes exactly one thing: **the two assets share a governed
structural-location context.**

It does not conclude that they are connected, that current can flow
between them, that one feeds, supplies, protects or controls the other,
that they are adjacent, that they are on one busbar or in one circuit,
that either is energised or in service, or what kind of place the shared
location is. A substation location routinely holds equipment from several
unrelated circuits.

The derived relationship is named `SHARES_STRUCTURAL_LOCATION_WITH` for
that reason — never `CONNECTED_TO`, `SAME_BAY` or `ADJACENT_TO`.

### 3. Graph reachability is not the authority

The governed graph now contains, for the first time, a two-hop path
between two assets:

```
A --IS_LOCATED_IN--> X <--IS_LOCATED_IN-- B
```

**That path is not why the inference is valid.** A path is a fact about a
data structure. The inference is authorised by a named, versioned rule
that states what that shape means for this question.

The distinction is executable, not rhetorical. The identical shape over a
different edge kind licenses nothing: two assets that both have a rated
power of 630 kVA form the same topological shape through the quantity
node and share no engineering property whatever. The rule reads
`IS_LOCATED_IN` **by name** (`LOCATION_RELATIONSHIP_KIND`), and a test
asserts that two assets sharing a rated power establish nothing.

### 4. Governed relationship vs derived relationship

The inputs are governed knowledge and are `GraphEdge`s. The conclusion is
a `ReasoningResult` and is **not** a `GraphEdge`, `SemanticStatement`,
`EngineeringFact`, `HumanReview` or `Evidence`. It is never persisted.

`DerivedRelationshipKind` is asserted **disjoint** from `GraphEdgeKind`,
`SemanticStatementType`, `FactPredicate` and `GraphNodeKind`. That
disjointness is the structural form of AF-REASON-001: a derived
relationship and a governed one must not be representable as the same
thing.

### 5. Outcome vocabulary, and the outcome that is deliberately absent

A second closed vocabulary, `StructuralReasoningOutcome`:

`ESTABLISHED` · `INSUFFICIENT_KNOWLEDGE` · `AMBIGUOUS`

`CONSISTENT` was **not** reused to mean "yes". It answers "do these
governed values agree?"; stretching it to "this relationship holds" is a
category error every downstream reader would inherit.

**There is no `NOT_SHARED`, no `NOT_ESTABLISHED` and no `DISJOINT`**, for
two independent reasons either of which is sufficient:

1. **Absence is not refutation.** The governed graph is a partial
   projection of approved statements (ADR-0024). An asset with no
   location edge is one nobody recorded a location for.
2. **Distinct identities are not distinct places.** Location identity is
   document-scoped (ADR-0030), so the same `+E01` in two documents is two
   governed identities — entirely compatible with one physical room.

So `A -> X`, `B -> Y`, `X != Y` yields `INSUFFICIENT_KNOWLEDGE` with the
`DISTINCT_LOCATION_IDENTITIES` diagnostic. This is the single most
important refusal in the milestone: a negative outcome would assert
something no governed input supports, and it would be believed.

### 6. Positive conditions

All of: two **distinct** governed asset identities; one applicable
governed `IS_LOCATED_IN` per side; the **same governed location
identity** (never the same label); complete provenance on both; no
ambiguity.

### 7. Ambiguity

`AMBIGUOUS` when a designation resolved to several governed assets (read
from the retrieval outcome the context carries, never recounted), or when
a side has several applicable governed locations. Reasoning never picks
one, never scores, and never resolves entities.

### 8. Same-asset questions are refused at construction

`shared_structural_location(A, A)` raises `SameAssetComparisonError` from
`SharedStructuralLocationQuery.__post_init__`. Every asset trivially
shares its own location with itself; a positive answer would be true,
worthless, and indistinguishable at a glance from the real conclusion.
Refusing at construction keeps "there was no question" from wearing the
shape of "governed knowledge does not establish this".

### 9. Typed query

`SharedStructuralLocationQuery(left_asset_node_id, right_asset_node_id,
left_designation, right_designation, project_id)`.

Assets are named by **governed identity**, resolved upstream by
retrieval; the designations are carried for rendering the question only
and enter neither the conclusion nor its identity. There is no depth, no
direction, no edge filter and no path expression — the query is an
engineering question, not an algorithm.

### 10. Inference path and provenance

A positive result keeps the whole ordered path — left asset id, left edge
id, location id, right edge id, right asset id — and **both** governed
support chains. Neither edge is reduced to a "primary" source. Reducing
the conclusion to "A and B share X" would discard exactly what makes it
checkable: which two approved statements put them there.

### 11. Deterministic identity and symmetry

Result identity is composed from the rule id and version, the
**canonical** question (the two governed asset identities, sorted), the
project, and the sorted contributing governed identities. No clock, no
duration, no UUID, no display text, no LLM output.

Sharing a location is symmetric, so asking (A, B) and asking (B, A) is
one engineering question and produces **one conclusion identity**. The
query preserves the order asked for display; the identity and the
inference path are canonical.

### 12. Contributor ordering

By the governed retrieval sort key, then governed result id. Never by DB
order, set iteration, or which side of the question a relationship came
from.

### 13. Retrieval before reasoning

The flow is unchanged: request → governed retrieval → context assembly →
reasoning. Reasoning retrieves nothing.

The structural question needs both assets' relationships, so the
requirement is declared where retrieval is *planned*:
`RELATIONSHIP_DEPENDENT_INTENTS` in the retrieval step handlers. It
states what an intent needs and is read by the planner; it performs no
retrieval, reaches no conclusion and knows nothing about rules. It is the
smallest thing that could be called a reasoning input requirement, and
deliberately not a planner.

No new retrieval capability was needed: `build_plan` already emits one
asset query per designation, and an asset traversal already returns every
governed relationship from that asset.

### 14. Engine integration

**One reasoning step, one handler**, dispatching on `request.intent_type`
— a typed field the request already carries. Not a registry: two rules
are two branches, and a registry's only effect would be that nobody can
tell from the handler which rules exist.

A new narrow intent, `STRUCTURAL_RELATIONSHIP_QUERY`, and a new workflow,
`STRUCTURAL_RELATIONSHIP`, built from the verification workflow with
`replace` so the two pipelines cannot drift. Forcing the question into
`VERIFICATION_REQUEST` was rejected: it has two subjects and its answer
is computed before any model is invoked, where a verification request has
one subject and asks whether evidence supports a statement.

Routing is phrase-based and narrow. `same bay`, `same panel`, `same
room`, `connected`, `collegato` and the bare `same place` are
deliberately **not** routed here, with negative tests for each: a
confident answer to a question the engineer did not ask is worse than no
answer.

### 15. Prompt and response separation

The prompt carries the governed relationships as `SELECTED_KNOWLEDGE` and
the finished conclusion as `DERIVED_REASONING`, labelled as derived and
not a reviewed engineering statement. **The model is never asked whether
the assets share a location** — that was answered exactly, upstream.

The `INSUFFICIENT_KNOWLEDGE` wording is load-bearing: a model told only
"insufficient" writes "they are in different places", so it is told
explicitly that the finding is not that, and not to report them as
separate.

In the response, governed knowledge stays in `references[]` and the
conclusion stays in `derived_reasoning`, now carrying a typed
`SharedStructuralLocationReport`. `rule_family` is the discriminator; a
consumer switches on it and gets a static type, never a dictionary and
never prose.

### 16. Warnings

`ESTABLISHED` raises none. `AMBIGUOUS` and `INSUFFICIENT_KNOWLEDGE` reuse
the existing `AMBIGUOUS_KNOWLEDGE` and `INSUFFICIENT_EVIDENCE`
categories. **`CONFLICTING_KNOWLEDGE` is never raised**: two assets in
different governed locations are not approved statements contradicting
each other, and reporting a conflict would send an engineer hunting a
documentation error that does not exist.

### 17. Comparison workflow: deliberately disabled

The comparison workflow runs no reasoning step, and a test asserts it.
Location identity is document-scoped, so cross-side reasoning would have
two options and both are wrong: conclude nothing and look broken, or
match on the label and perform cross-document entity resolution. The two
sides are also kept apart end to end, so there is no single governed
context for a relationship rule to read.

### 18. No traversal, no chaining, no closure

There is no traversal: the rule reads a flat collection of governed
relationships and matches on subject identity. No depth parameter (there
is no depth), no visited set (nothing is walked), no cycle handling (a
cycle in unrelated context is data this rule does not select). A derived
result is never an input to another rule.

### 19. Persistence and API

**No table, no migration, no repository, no cache.** A conclusion is a
runtime artefact.

**No standalone endpoint.** OpenAPI keeps its 100 paths; the schema count
grew by four additive types. There is no `/reasoning`, no `/topology`, no
graph-write route and no caller-supplied provenance.

### 20. LLM boundary

No LLM participates in reaching, checking or authorising the conclusion.
It may communicate one it did not reach.

## Consequences

### Good

- The platform states, for the first time, something no document says and
  no reviewer approved — under a version, with a path, and with both
  supporting statements named.
- The 32.1 family was extended without distortion: `ReasoningResult`
  carries common metadata and defers family-specific data to a typed
  field, so every 32.1 consumer kept working unchanged.
- Two latent EPIC 32.P1 defects surfaced and were fixed at the source:
  Context Assembly could not carry a `STRUCTURAL_LOCATION` result
  (`_SECTION_KINDS` is now derived from the vocabulary rather than listed,
  closing the defect class), and the kind had no budget dimension
  (`BudgetCategory.LOCATIONS`).

### Costs and risks

- **The graph is no longer depth-1, and the temptation is now real.** Any
  future rule reading these paths must justify its conclusion on
  engineering grounds. Architecture tests forbid the vocabulary that would
  express connectivity, but no test can force a future rule to be
  well-reasoned.
- **`INSUFFICIENT_KNOWLEDGE` will be read as "no".** The vocabulary, the
  warning text and the prompt wording all push against it; none of them
  can guarantee a reader does not.
- **One relationship rule is not topology.** Co-location is a narrow
  finding, and nothing here approaches a substation model.

### Debt recorded, not paid

- Multiple applicable locations produce `AMBIGUOUS` rather than a
  per-location answer.
- The step resolves a designation to the first governed asset by
  identity; the rule reports `AMBIGUOUS` from the retrieval outcome
  regardless, so the choice never decides an answer, but a richer engine
  contract would carry all candidates.
- Cross-document location identity remains unresolved by design.

## Conditions for future structural reasoning

1. A new rule reads its own edge kind **by name**, on its own line.
2. It carries its own `rule_id` and `rule_version`.
3. It may not treat containment as connectivity, direction or state.
4. Absence must map to insufficient knowledge unless the ontology
   acquires a complete-world basis.
5. Derived results remain non-inputs: no chaining, no closure.
6. Promotion of any conclusion into governed knowledge requires its own
   governance milestone and ADR (AF-REASON-003).

## References

- [ADR-0030: Governed Structural Relationship Semantics Foundation](0030-governed-structural-relationship-semantics.md)
- [ADR-0029: Deterministic Engineering Reasoning Foundation](0029-deterministic-engineering-reasoning-foundation.md)
- [ADR-0024: Governed Knowledge Graph as Projection](0024-governed-knowledge-graph-as-projection.md)
- [ADR-0027: Governed Context Assembly](0027-governed-context-assembly.md)
- [ADR-0006: AI as Interpretation/Presentation Layer](0006-ai-as-interpretation-presentation-layer.md)
- [Architecture Freeze AF-01](../architecture_freeze_af01.md)
- IEC 81346-1, *Structuring principles and reference designations*
