# ADR-0027: Governed Context Assembly

## Status

Accepted.

## Context

[ADR-0026](0026-governed-structured-retrieval.md) moved the Engineering
Engine's retrieval onto the Governed Knowledge Graph, and deliberately
left one seam standing:

> `GovernedRetrievalResult → governed_context_projection.py →
> KnowledgeCandidate* → Context Builder`
>
> It is a compromise and is documented as one. Migrating retrieval
> **and** its four downstream consumers in a single change would have
> made a quality regression in any of them invisible — the one thing
> this milestone was required not to do.

It gave the adapter an explicit end date: **delete it when Context
Builder consumes `GovernedRetrievalResult` directly.** It also recorded
a second, smaller retirement condition:

> its `KnowledgeCandidate*` value objects still reference
> `graph_builder`'s `GraphEntityId` and `GraphRelationshipType`, so
> retiring `graph_builder` also requires the Context Builder migration.

That isolation has served its purpose. Retrieval was migrated, measured
against a baseline, and shipped green. This ADR records closing the
seam.

## Decision

### 1. Context Assembly consumes `GovernedRetrievalResult` directly

`ContextBuildRequestFactory.create` takes
`results: tuple[GovernedRetrievalResult, ...]`, and there is no
constructor that takes anything else. That is what makes "Context
Assembly reads only governed knowledge" a property of the type rather
than a rule somebody has to remember.

The adapter is **deleted**, not deprecated. Two architecture tests hold
the line: one asserts the file does not exist, the other asserts that no
module anywhere projects governed results into the candidate vocabulary,
so a replacement cannot be written quietly under another name.

### 2. It stays in `context_builder`, and is not a new bounded context

A `governed_context_assembly` package would have left two context
builders in the repository, and the second would have been the one
nobody maintained. The bounded responsibility did not change - organize
retrieved knowledge into a bounded, provenance-aware, explainable
artefact - only its input vocabulary did.

Its allowed dependencies are now `governed_retrieval`,
`governed_knowledge_graph` and `project`. `structured_retrieval` and
`graph_builder` are gone from that set, enforced by
`test_bounded_context_dependencies.py`.

### 3. A `ContextItem` wraps a governed result rather than copying it

```python
@dataclass(frozen=True, slots=True)
class ContextItem:
    result: GovernedRetrievalItem   # untouched
    origin: ContextItemOrigin       # the query that produced it
```

Rejected alternative: **a flat context item copying the fields it
needs.** It would have duplicated engineering payload into a second
representation, and the day the two disagreed nobody could say which was
authoritative. Reusing the upstream read-oriented type is the pattern
every stage of this platform already follows, and here it buys three
guarantees *structurally*:

- **provenance cannot be dropped** — it lives on the governed item,
  where it has no default and no `| None`;
- **ambiguity cannot be lost** — the origin carries the retrieval
  outcome;
- **there is one representation** of a governed answer in the system.

### 4. Provenance is preserved structurally, not by convention

```
ContextItem → GovernedRetrievalItem → governed graph object
    → statement_key → review_id → support_fingerprint → document_id
```

Every link is an **identity**. Nothing on the chain is copied as
content: the statement, the facts, the entities and the evidence stay in
the pipeline, which remains their single account.

The consequence is that `MISSING_PROVENANCE` was **removed** from
`ContextWarningCategory`. It described a state the platform can no
longer reach, and a warning that can never fire is worse than no
warning — its silence reads as reassurance.

### 5. Ambiguity survives context construction, in five places

`MULTIPLE_MATCHES` must never become "the first result". So it is
carried on each item's origin, on each query's summary, as an
`AMBIGUOUS_RETRIEVAL` context warning, as an `AMBIGUOUS:` block in the
prompt, and as an `AMBIGUOUS_KNOWLEDGE` warning plus a `HIGH`
uncertainty on the response.

Five, and not fewer, because an ordered list reads as a ranked one and
the first line of a ranked list reads as the answer. A chain that
preserved ambiguity at four stages and dropped it at the fifth would
have preserved nothing.

Per query rather than per package: a context assembled from one unique
and one ambiguous query is not "somewhat ambiguous".

### 6. Score-based ordering is gone from the governed path

The adapter's `KnowledgeCandidateScore` was documented as an ordering
value and computed from the match strategy's rank alone. It was still a
number attached to an engineering answer, and a number attached to an
engineering answer is read as confidence whatever it is called.

Ordering is now the governed retrieval sort key — match-strategy
precedence, folded labels, governed identity — with item identity as the
final tie-break. Selection adds nothing: re-ranking governed results
would be Context Assembly deciding which knowledge matters, and that is
retrieval's judgement.

An architecture test fails on `KnowledgeCandidateScore` or
`ScoreComponentCategory` appearing anywhere in the governed path.

### 7. Deduplication is by governed identity

Never by display text. Two governed nodes that share the label `TR1`
stay two items, because deciding they are the same transformer is
cross-document entity resolution and no governed rule performs it.

A quantity reached by traversal is identified by **both** its edge and
its node: the same quantity node can be the object of two governed
relationships, and collapsing them would report one answer where the
graph holds two.

### 8. Context Assembly performs no governance and no I/O

It never recomputes `APPROVED`, `APPLIES`, `REQUIRES_REVALIDATION` or
`ORPHANED`. The promotion contract already guarantees that an `ACTIVE`
object was authorised by a review that currently holds, and a second
definition would eventually disagree with the first, invisibly.

It also issues no query of its own — which is a **security** property,
not a layering preference. Retrieval applied the project scope, the
document scope and the caller's authorization; an assembly that could
read for itself could widen any of them with nothing downstream
noticing. Architecture tests assert both.

### 9. `POST /projects/{id}/context-builder/build` is withdrawn

This is the one place where legacy API compatibility was **not**
preserved, and the reason is correctness rather than tidiness.

The endpoint's only possible input was a legacy
`KnowledgeCandidateCollection`. After this milestone a `ContextPackage`
is a governed artefact: every item asserts a statement key, a review id
and a named reviewer. Accepting one in a request body would let any
authenticated caller mint a context that *looks* reviewed — the exact
[ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) failure three
milestones were spent removing.

**Provenance a caller asserts is not provenance.** There is no honest
replacement request body: the only correct source of governed
provenance is retrieval the platform ran itself, which is what
`/engineering-engine/execute` does.

No `410 Gone` shim, for the reason ADR-0025 already gave: it preserves a
URL whose only honest answer is that the request it accepted should
never have produced governed knowledge.

`/prompt-builder/build` and `/engineering-response/build` **keep** their
`context_package` bodies. The asymmetry is deliberate and narrow: those
two persist nothing and write no graph, so a fabricated body harms only
the caller's own answer. Context Assembly is the step where "this is
governed knowledge" is claimed.

### 10. Canonical Facts retirement remains a separate product decision

Unchanged from ADR-0026, and deliberately not acted on here.

## Consequences

**Positive**

- The Engineering Engine's path from graph to answer speaks **one**
  vocabulary end to end. There is no translation layer left in which
  provenance, ambiguity or identity could quietly be lost.
- A prompt now cites the statement and the review behind every line,
  where it used to cite a candidate id and a score.
- The `structured_retrieval → graph_builder` dependency is severed from
  the governed engine path: no module the engine reaches imports either.
- Three fewer trust signals to explain: no score, no dual-origin
  provenance, no candidate identity that is not a governed identity.
- `_governed_context.py` gives the test suite one place to build
  governed fixtures, all of them real domain objects — so no test can
  pass against a shape production could not produce.

**Negative**

- **`ContextPackageRead` is a breaking wire change.** `selected_items`
  replaces `selected_candidates`, items carry governed identities and
  provenance instead of a score and a `GraphEntityId`, and
  `PromptEvidenceReference`/`EngineeringEvidenceReference` changed shape
  with it. No frontend code consumed any of these, and the OpenAPI
  snapshot is regenerated.
- **One route is withdrawn** (§9). It had no frontend consumer and is
  not in `public_api.md`, but it was a served, tested capability.
- **The legacy lineage still exists**, with its own API. This milestone
  removes the engine's dependency on it and nothing more.

**Neutral**

- `context_builder_version` is renamed `context_assembly_version` from
  the context package through the prompt, the LLM request metadata and
  the response. The field always meant "which context assembly produced
  this"; it now says so.

## Retirement readiness

ADR-0026 recorded two conditions for retiring the Canonical Facts
projection. **The second is now met; the first is unchanged.**

| Condition | Status after EPIC 31.3 |
|---|---|
| `structured_retrieval`'s value objects reference `graph_builder`, so the Context Builder migration is required first | **Met for the governed path.** No module the Engineering Engine reaches imports `structured_retrieval` or `graph_builder`. The types survive only inside the legacy retrieval implementation and the API that serves it. |
| Four legacy route groups still serve the lineage | **Unchanged.** `/graph-builder/*`, `/graph-executions/*`, `/projects/{id}/graph/*` and `/projects/{id}/structured-retrieval/*` are still served, documented and tested. |

So the technical work is done and the remaining blocker is entirely a
**product decision**: whether the platform continues to offer those four
route groups. The day they are withdrawn, retirement is mechanical —
delete the three contexts, their models, schemas, services and tests,
and add a forward migration dropping `project_graph_nodes`,
`project_graph_relationships`, `graph_executions`,
`graph_execution_operation_results`, `graph_execution_fingerprints`,
`graph_operation_batches` and `graph_operations`.

That migration is still **not** written. A migration for tables a live
route serves is a trap for whoever runs it.

One further live consumer is worth naming precisely, because it is easy
to mistake for an engine dependency: `retrieval_bridge` imports
`RetrievalMode` from `structured_retrieval`, and is served by
`/engineering-request-preparation`. The Engineering Engine does **not**
import it — the engine reads plain fields off its own execution request
— so this is a legacy-API dependency rather than a governed-path one.

## Rejected Alternatives

**Keep the adapter and rename it.** Rejected: ADR-0026 gave it an end
date precisely so that it could be deleted rather than renamed. An
adapter that survives its stated retirement condition is a permanent
one.

**Flatten governed results into a purpose-built context item.**
Rejected: it duplicates engineering payload into a second
representation, and makes provenance a field somebody must remember to
copy rather than one that cannot be dropped.

**Keep a score for ordering, documented as "not a confidence".** ADR-0026
tried exactly that inside the adapter, and this milestone removes it.
The documentation is not where the number is read.

**Repoint `/context-builder/build` at a governed request body.**
Rejected: it would accept caller-asserted statement keys, review ids and
reviewer names, and emit a package indistinguishable from one the
platform derived. That is a worse outcome than withdrawing the route.

**Migrate Prompt Builder and Engineering Response to read governed
results directly, bypassing `ContextPackage`.** Rejected as out of
scope and wrong: bounding, budgeting and reporting coverage is Context
Assembly's job, and removing the artefact would push it into two places.

## Related

- [ADR-0026](0026-governed-structured-retrieval.md) — the milestone that
  created the adapter and set this one's condition.
- [ADR-0024](0024-governed-knowledge-graph-as-projection.md) — why the
  governed graph has no property bag, which is why a context over it
  needs none either.
- [ADR-0004](0004-reviewed-facts-only-in-queryable-graph.md) — the
  decision §9 protects.
- [ADR-0011](0011-context-builder-foundation.md) — the original Context
  Builder, whose shape this migration keeps.
- `docs/architecture/governed_context_assembly.md` — the as-built
  reference.
