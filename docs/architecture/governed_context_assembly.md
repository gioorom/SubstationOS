# Governed Context Assembly (EPIC 31.3)

> **Package:** `apps/backend/app/domain/context_builder/`
> **Service:** `apps/backend/app/services/context_builder_service.py`
> **Input:** `tuple[GovernedRetrievalResult, ...]`
> **Output:** `ContextPackage`
> **Rule:** it organizes governed knowledge. It creates none.

---

## 1. What this context is for

```
Governed Knowledge Graph
        ↓
Governed Structured Retrieval      what matched, and why
        ↓
Governed Context Assembly          how those results become context
        ↓
Prompt Builder
        ↓
Engineering Response
```

Retrieval decides **what matched**. Context Assembly decides **how those
governed results are represented as context** for the reasoning stages
downstream. That division is the whole of its responsibility, and every
rule below follows from it.

It does **not**: create engineering knowledge, infer relationships,
resolve cross-document identity, approve anything, rank by confidence,
reinterpret semantics, hide ambiguity, or discard provenance.

## 2. What EPIC 31.3 changed

EPIC 31.2 moved the Engineering Engine's retrieval onto the governed
graph but deliberately left one seam standing:

```
GovernedRetrievalResult → governed_context_projection.py → KnowledgeCandidate* → Context Builder
```

That adapter existed so retrieval and context could migrate separately -
migrating both at once would have made a quality regression in either
invisible. **It is now deleted**, and three things went with it:

| Removed | Why it could not stay |
|---|---|
| `KnowledgeCandidate*` | The legacy Structured Retrieval vocabulary. Its `KnowledgeCandidateReference` carries a `GraphEntityId`, so the governed path could not be free of the Canonical Facts lineage while it remained. |
| the **score** | `KnowledgeCandidateScore.total` was an ordering value shaped exactly like a confidence, and in an engineering answer a number is read as confidence whatever it is called. |
| the dual-origin provenance warning | It distinguished "states its origin one of two ways" from "states it neither way". A governed item cannot state it neither way. |

An architecture test asserts the adapter file does not exist, and a
second asserts that **no** module anywhere projects governed results
into the candidate vocabulary - so a replacement cannot be written
quietly.

## 3. Where the boundary is, and why it is not a new context

Context Assembly is **the existing `context_builder` package, migrated
in place**. A new `governed_context_assembly` package would have left
two context builders in the repository, and the second one would have
been the one nobody maintained. The bounded responsibility did not
change; its input vocabulary did.

Its dependencies are now:

```
context_builder → governed_retrieval, governed_knowledge_graph, project
```

`structured_retrieval` and `graph_builder` are gone from that set, and
`tests/architecture/test_bounded_context_dependencies.py` is where that
is enforced.

## 4. The context model

### `ContextItem` wraps a governed result rather than copying it

```python
@dataclass(frozen=True, slots=True)
class ContextItem:
    result: GovernedRetrievalItem   # untouched
    origin: ContextItemOrigin       # the query that produced it
```

This is the same "reuse the upstream read-oriented type" pattern the
platform already follows at every stage - pointed at a type worth
reusing. It copies **no** engineering payload, and three properties
follow structurally rather than by convention:

- **provenance cannot be dropped**, because it lives on the governed
  item, where it has no default and no `| None`;
- **ambiguity cannot be lost**, because the origin carries the retrieval
  outcome;
- **there is one representation** of a governed answer in this system,
  so no two copies can disagree.

### `ContextItemOrigin`

| Field | Why it is here |
|---|---|
| `query_type` | which governed question this item answers |
| `outcome` | `NO_MATCH` / `UNIQUE_MATCH` / `MULTIPLE_MATCHES` |
| `scope` | `CURRENT_ONLY` for everything the engine asks |
| `normalized_query` | the fold that was applied to the engineer's own term |
| `matched_before_limit` | how many governed objects **retrieval** saw |

Carried **per item**, not per package, because one context may be
assembled from several governed queries and "which of them was
ambiguous?" has to stay answerable.

### `ContextPackage`

Same outer shape as before - retrieval summary, coverage, statistics,
warnings, budget, metadata - with governed items in place of candidates
and three kind-specific tuples (`selected_assets`,
`selected_quantities`, `selected_relationships`) mirroring the governed
vocabulary rather than a parallel one.

## 5. Provenance: the hard invariant

Every item preserves the whole chain, by identity:

```
ContextItem
    → GovernedRetrievalItem        result_id
    → governed graph object        node_id / edge_id
    → semantic statement           statement_key
    → authorising review           review_id, reviewer, reviewed_at
    → support chain                support_fingerprint
    → document                     document_id, content_checksum
```

**Nothing on that chain is copied as content.** The statement, the
facts, the entities and the evidence stay in the pipeline, which remains
their single account; a copy here would be a second one, and the day the
two disagreed nobody could say which was authoritative.

There is no code path by which an engineering context item loses
provenance, and no context warning claims missing provenance any more -
a warning that can never fire is worse than none, because its silence
reads as reassurance.

## 6. Ambiguity

Governed retrieval distinguishes `NO_MATCH`, `UNIQUE_MATCH` and
`MULTIPLE_MATCHES`. Context Assembly preserves all three, and states the
third rather than letting ordering imply certainty:

- `ContextItemOrigin.outcome`, per item;
- `RetrievalSummary.queries`, per query, so a unique query beside an
  ambiguous one stays unique - a context is never "somewhat ambiguous";
- a `ContextWarning` of category `AMBIGUOUS_RETRIEVAL`, naming the term
  and the count;
- an `AMBIGUOUS:` block in the prompt's engineering-context section,
  telling the model in words that the subject matched more than one
  governed object and must not be presented as one;
- an `AMBIGUOUS_KNOWLEDGE` warning and a `HIGH` uncertainty on the
  `EngineeringResponse`.

Five places, because an ordered list reads as a ranked one and the first
line of a ranked list reads as the answer.

**Two documents that each designate `TR1` produce two items.** Deciding
they are the same transformer is cross-document entity resolution, which
no governed rule performs and which this milestone does not introduce.

## 7. Ordering

The complete rule, and it contains no score:

```
(match strategy precedence, folded primary label, folded secondary label,
 governed identity)          ← GovernedRetrievalItem.sort_key
then item identity           ← the final tie-break
```

Selection sorts by that key and adds nothing of its own. Re-ranking
governed results would be Context Assembly deciding which knowledge
matters, which is retrieval's judgement rather than its own; the legacy
stage deliberately *re-derived* the ordering because the upstream
`sort_key` was not on the wire, and a governed item's `sort_key` **is**
its documented ordering, so a second derivation here would be a second
definition of one rule.

Nothing in the key varies between runs: no clock, no counter, no
insertion order, no database sort.

## 8. Deduplication

By **governed identity** (`result_id`, derived from the governed node and
edge ids), never by display text. Reachable when several governed
queries answer with the same object - a designation lookup and a
quantity traversal both resolving `TR1`.

A quantity reached by traversal is identified by *both* the edge and the
node, because the same quantity node can be the object of two different
governed relationships, and collapsing them would report one answer
where the graph holds two.

## 9. Truncation

| Budget | Default |
|---|---:|
| `max_items` | 100 |
| `max_assets` | 50 |
| `max_quantities` | 50 |
| `max_relationships` | 50 |
| `max_metadata_entries` | 20 |
| `max_warnings` | 50 |

An item whose own kind has reached its cap is skipped **without
consuming the overall budget**, so a lower-ranked item of a still-open
kind is still admitted.

Truncation is always diagnosable, and never converts ambiguity into
uniqueness:

- `RetrievalSummary.total_before_limit` - how many governed objects
  retrieval saw;
- `RetrievalSummary.retrieved_item_count` - how many reached assembly;
- `ContextStatistics.selected_item_count` / `discarded_item_count`;
- a `ContextWarning` per discarded item, naming the budget dimension.

If ten matched and five are in the package, all three numbers are there
to be read.

## 10. Warnings

| Category | Fires when |
|---|---|
| `BUDGET_EXCEEDED` | any dimension discarded something |
| `AMBIGUOUS_RETRIEVAL` | a governed query matched more than one object |
| `MISSING_QUANTITIES` | quantities were retrieved and none were selected |
| `MISSING_RELATIONSHIPS` | relationships were retrieved and none were selected |
| `PARTIAL_COVERAGE` | any coverage ratio below 1.0 |
| `ITEM_DISCARDED` | one specific item did not fit |

`MISSING_PROVENANCE` is **gone** - see §5.

## 11. Governance stays upstream

Context Assembly never recomputes `APPROVED`, `APPLIES`,
`REQUIRES_REVALIDATION` or `ORPHANED`. The promotion contract already
guarantees that an `ACTIVE` governed object was authorised by a review
that currently holds; a second definition here would eventually disagree
with the first, and the disagreement would be invisible.

An architecture test asserts that no Context Assembly module mentions
any of those terms or imports `human_review`.

## 12. Historical knowledge

The Engineering Engine issues every governed query with scope
`CURRENT_ONLY`, and there is no request field that could widen it.
Context Assembly **cannot** widen it either: its only input is the
results it was handed, and it issues no query of its own.

Each item still carries its `state` and its `retirement_reason`, so a
caller reading a deliberately mixed-scope result can tell current
knowledge from a record of it without inferring it from the query it
sent.

## 13. Versioning

| Version | Bump it when |
|---|---|
| `CONTEXT_ASSEMBLY_VERSION` (`2.0`) | the package could differ for unchanged governed input |
| `SELECTION_POLICY_VERSION` (`2.0`) | the order or the admission rule changes |
| `BUDGET_POLICY_VERSION` (`2.0`) | a default limit changes |

All three describe **behaviour**, never a deployment: two installations
on the same code report the same versions.

`ContextMetadata` also **echoes** the retrieval versions
(`retrieval_normalization_version`, `retrieval_matching_policy_version`,
`graph_generation_number`) rather than restating them from its own
constants. When the governed results disagree - only reachable across a
redeploy mid-request - it reports `None` rather than picking one, because
one value standing for two is how a version field becomes a lie.

## 14. Determinism

Identical governed results and an identical assembly policy produce an
identical `ContextPackage`: the same items, in the same order, with the
same warnings and the same budget figures. `assembled_at` is a caller
parameter rather than a wall-clock read, and nothing in the package's
*content* derives from it.

`test_ordering_is_deterministic_across_input_permutations` asserts the
sharper property: the order does not depend on the order a caller
happened to execute its queries in.

## 15. Security

Context Assembly **performs no I/O**, and that is a security property
rather than a layering preference. Governed Structured Retrieval applied
the project scope, the document scope and the caller's authorization; an
assembly that could read for itself would be able to widen any of them
with nothing downstream noticing.

An architecture test asserts no Context Assembly module mentions
`sqlalchemy`, `app.models`, `app.infrastructure`, `app.database`, or
either governed graph port.

## 16. API

### Withdrawn: `POST /projects/{id}/context-builder/build`

The endpoint took a legacy `KnowledgeCandidateCollection` - the output of
`/structured-retrieval/search` - and assembled a `ContextPackage` from
it.

After this milestone a `ContextPackage` is a **governed** artefact:
every item asserts a statement key, a review id and a named reviewer.
There is no honest request body for that. Accepting one would let any
authenticated caller mint a context that *looks* reviewed, which is
precisely the [ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md)
failure three milestones were spent removing.

**Provenance a caller asserts in a request is not provenance.** So the
route is withdrawn rather than repointed, and no `410 Gone` shim
survives it - the same reasoning [ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md)
applied to the legacy graph routes.

Assembling a governed context is what
`POST /projects/{id}/engineering-engine/execute` does, from retrieval it
ran itself under its own scope and authorization.

### Retained: Prompt Builder and Engineering Response

```
POST /projects/{id}/prompt-builder/build
POST /projects/{id}/engineering-response/build
```

Both still accept a `ContextPackage` in the request body, now in its
governed shape. The asymmetry with Context Assembly is deliberate and
narrow: these two persist nothing, write no graph, and return a prompt
or a response artefact, so a fabricated body harms only the caller's own
answer. Context Assembly is the step where "this is governed knowledge"
is *claimed*, and that claim must come from retrieval.

## 17. Downstream

### Prompt Builder

`describe_item` replaces `describe_candidate`. A knowledge line now ends
in the governed match strategy and the statement key that authorises it,
where it used to end in `(score 100.0)`:

```
ASSET TR1 [node abc…] (matched by exact_designation; statement stmt-1)
QUANTITY TR1 has_rated_power 630 kVA [node def…] (matched by relationship_traversal; statement stmt-2)
```

`PromptEvidenceReference` carries `item_id`, `node_ids`, `edge_ids`,
`statement_key`, `review_id` and `document_id` - identities only, never
the statement or the evidence text.

The system-context section states plainly that *approved* means an
engineer accepted that statement, and does **not** mean the knowledge is
complete or that a question has exactly one answer.

### Engineering Response

`EngineeringEvidenceReference` restates the prompt's citation field for
field, so nothing is lost between the prompt that was sent and the
response produced from it. A citation names which approved statement,
approved in which review, out of which document - it never says the
answer is correct.

`AMBIGUOUS_KNOWLEDGE` (warning) and a `HIGH` uncertainty are added when
a governed question had more than one governed answer, so
*retrieved* / *approved* / *proven* / *certain* stay four different
things.

### Engineering Reasoning (EPIC 32.1)

The `ENGINEERING_VERIFICATION` workflow now runs a deterministic
reasoning step over the assembled `ContextPackage`, between assembly and
the prompt. It is a **pure consumer**: it reads the package it is handed
and nothing else - no session, no repository, no second query.

That is why `INSUFFICIENT_KNOWLEDGE` is one of its four outcomes. If a
rule needs governed knowledge the context does not carry, the honest
answer is that the context does not carry it. A reasoning service that
could read for itself would be able to widen the project scope, the
document scope or the caller's authorization that Context Assembly and
Governed Structured Retrieval already applied - with nothing downstream
noticing.

Context Assembly changed **not at all** for this: reasoning is
downstream of it, and the frozen dependency direction
`context_builder → engineering_reasoning` is now asserted by AF-DEP-001,
because context is assembled before anything is concluded from it. See
[engineering_reasoning.md](engineering_reasoning.md).

### Comparison workflows

Each side hands over its **own** governed results. No projection, no
merge: an ambiguous left subject cannot make the right one look
ambiguous, and neither side's provenance can be attributed to the other.
An architecture test asserts the comparison handlers specifically,
because they are the one workflow with two of everything and therefore
the likeliest place for a compatibility route to survive unnoticed.

## 18. Performance

Context Assembly touches no database. Its cost is O(n log n) in the
number of governed items - dominated entirely by Selection's sort - and
every later stage is a single O(n) or O(1) pass.

There is no N+1: provenance, labels and identities all travel inside the
governed results, so nothing is fetched per item. The benchmarks in
`scripts/benchmarks/graph_performance_benchmark.py` now generate
governed results in memory rather than retrieving them, which is what
makes them a measurement of assembly rather than of a read.

## 19. Known limits

- **Three node kinds and two edge kinds**, inherited from the governed
  graph. See [knowledge_graph.md](knowledge_graph.md) §3. Assembly
  selects governed items and reinterprets none of them - it performs no
  inference, and the shared-location conclusion EPIC 32.2 draws is
  Engineering Reasoning's, never assembly's.

  EPIC 32.2 was the first question to actually **retrieve** a governed
  structural location, and it exposed two gaps EPIC 32.P1 had left:
  aggregation had no section for the kind (a `KeyError` at assembly
  time) and selection had no budget dimension for it. Both are fixed at
  the source - `_SECTION_KINDS` is now derived from the governed
  vocabulary rather than listed by hand, which closes the class of
  defect rather than the instance, and `BudgetCategory.LOCATIONS` bounds
  the kind like every other.
- **No cross-document entity resolution.** Two `TR1`s stay two items.
- **Project visibility is filtering, not enforcement**, inherited from
  EPIC 30.3.
- **The Canonical Facts projection still exists**, still served by four
  legacy route groups. It is no longer read by the Engineering Engine or
  by Context Assembly. See [ADR-0027](adr/0027-governed-context-assembly.md) §"Retirement readiness".

---

## Files

| Concern | Location |
|---|---|
| Domain | `apps/backend/app/domain/context_builder/` |
| Service | `apps/backend/app/services/context_builder_service.py` |
| Wire shapes | `apps/backend/app/schemas/context_builder.py` |
| Engine steps | `apps/backend/app/services/engineering_engine/step_handlers.py`, `comparison_step_handlers.py` |
| Tests | `tests/domain/test_context_package_assembler.py`, `tests/domain/test_item_selection.py`, `tests/domain/test_context_builder_factory.py`, `tests/services/test_context_builder_service.py`, `tests/architecture/test_governed_retrieval_boundaries.py`, `tests/api/test_context_builder_api.py` |
| Test builders | `apps/backend/tests/_governed_context.py` |
