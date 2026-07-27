# ADR-0011: Context Builder Foundation

## Status

Accepted.

## Context

By Milestone 13 (Structured Retrieval Foundation, ADR-0010), the
governed knowledge pipeline can turn a set of structured criteria into
a ranked, explainable `KnowledgeCandidateCollection` - deterministic,
scored, provenance-carrying evidence drawn exclusively from governed
graph state. Nothing yet turns "I have a ranked set of knowledge
candidates" into "I have a bounded, structured package suitable for a
future AI capability to consume" - the shape every future Prompt
Builder, and eventually the AI Assistant (ADR-0006, `PRODUCT_VISION.md`),
will need before it can safely build a prompt or an answer.

Three temptations existed and were rejected before writing any code:

1. **Let the future Prompt Builder consume `KnowledgeCandidateCollection`
   directly.** This would push candidate selection, budget enforcement,
   and coverage/warning logic into the Prompt Builder itself - the one
   bounded context in this pipeline whose entire purpose is to sit
   closest to an AI provider. Selection and budget policy are
   engineering decisions about *which governed knowledge enters an AI
   capability's context*, not prompt-formatting decisions; conflating
   the two would put non-AI-specific logic behind the boundary this
   project treats as most sensitive (ADR-0006).
2. **Fold budget enforcement and coverage reporting into Structured
   Retrieval itself**, since it already has a `limit` and a scoring
   policy. Rejected: Structured Retrieval's `limit` bounds *one
   request's* result page: Milestone 14 requires bounding a *package*
   that may be assembled from candidates a caller gathered across more
   than one retrieval call, with its own budget dimensions (entities,
   relationships, attributes, metadata entries, warnings) that have
   nothing to do with ranking one search's results. This is a distinct
   responsibility, not an extension of an existing one.
3. **Start building the Prompt Builder and the AI Assistant directly
   against `KnowledgeCandidateCollection`, skipping a dedicated
   assembly layer.** Rejected for the same reason ADR-0010 rejected
   embeddings before a deterministic baseline existed: every future AI
   capability would duplicate its own selection/budget/coverage logic,
   with no shared, testable, explainable contract between "ranked
   knowledge" and "what an AI capability is allowed to see."

## Decision

### 1. Context Builder is a new bounded context, `app/domain/context_builder/**`, that owns assembly - never retrieval, never AI

Context Builder's input is exactly one type: Structured Retrieval's own
`KnowledgeCandidateCollection` (`app.domain.structured_retrieval.structured_retrieval_models`),
consumed the same way Structured Retrieval consumes Graph Query's
`GraphNodeView`/`GraphRelationshipView` - as a shared, stable,
read-oriented vocabulary reused across bounded contexts, never
re-derived. Context Builder never calls Graph Query, never calls
Structured Retrieval, never queries a database, and never calls an AI
provider - its own architecture tests
(`tests/architecture/test_bounded_context_dependencies.py::test_context_builder_does_not_import_forbidden_modules`/
`test_context_builder_surface_has_no_ai_or_vector_dependency`) enforce
this the same way Milestone 13's tests enforce Structured Retrieval's
own boundaries. Its responsibility begins exactly where Structured
Retrieval's ends: turning an already-ranked, already-scored, already
provenance-carrying collection into a bounded `ContextPackage`.

### 2. Context Builder owns candidate-count and budget-enforcement, not Structured Retrieval

A configurable `BudgetPolicy` bounds six independent dimensions:
candidates, entities, relationships, attributes, metadata entries, and
warnings. Selection re-derives its own deterministic ranking key
(highest score, then candidate kind priority, then entity/natural
identity, then candidate identity) from `KnowledgeCandidate`'s own
public fields, rather than trusting `KnowledgeCandidate.sort_key` -
Structured Retrieval's own internal ranking aid that its API responses
deliberately never expose (`app/schemas/structured_retrieval.py`).
Every admission/discard decision is deterministic and fully traceable
through `BudgetConsumption` (requested/accepted/discarded/utilization
per dimension); overflow is never a validation error, it is the
routine, expected, warned-about behavior this milestone exists to
report (`ContextWarningCategory.BUDGET_EXCEEDED`/`CANDIDATE_DISCARDED`).

### 3. Context Builder owns coverage as a selection-completeness measure, never an engineering-confidence score

`CoverageReport` answers exactly one question: *how much of the
retrieved knowledge entered the package* - entity/relationship/
attribute coverage, candidate utilization, and an overall completeness
figure, each a `selected_count / available_count` ratio (or `1.0` when
nothing was available - vacuously complete, never a divide-by-zero
error and never a bug in "nothing to select yields nothing wrong").
Coverage never claims anything about whether the underlying engineering
facts are trustworthy or complete in the real world - that would
misrepresent Structured Retrieval's own ADR-0004-derived guarantee (a
fact reached the graph only after review) as something Context Builder
independently re-certifies, which it does not and must not.

### 4. Provenance is aggregated, never invented

`ContextPackage.selected_candidates` carries the exact `KnowledgeCandidate`
objects Structured Retrieval produced - scores, reasons, matches,
`graph_node_ids`/`graph_relationship_ids`/`graph_execution_ids`/
`source_fact_ids` unchanged. Where provenance is honestly absent (a
missing `graph_execution_ids`, per Milestone 13's own documented
technical debt), Context Builder represents that absence explicitly, as
a `ContextWarningCategory.MISSING_PROVENANCE` warning, rather than
silently dropping the candidate or fabricating a value.

### 5. Prompt Builder must not duplicate this logic

```
Graph Query            = deterministic read model over current graph state
Structured Retrieval   = ranked, explainable KnowledgeCandidates from structured criteria
Context Builder        = bounded, provenance-aware ContextPackage from ranked candidates
Prompt Builder          = (future) deterministic, provider-independent PromptPackage from a ContextPackage
AI Assistant            = (future) consumer, not owner, of engineering truth
```

The next milestone (Prompt Builder) is expected to consume
`ContextPackage` the same way Context Builder consumes
`KnowledgeCandidateCollection`: one new responsibility (formatting a
provider-independent prompt), never re-deriving selection, budget, or
coverage decisions this milestone already made. A Prompt Builder that
re-selects candidates, re-enforces a budget, or recomputes coverage
would silently diverge from the figures a caller already inspected in
the `ContextPackage` it was handed - exactly the duplicated,
inconsistent logic this ADR's Context section rejected building
directly into the Prompt Builder in the first place.

## Consequences

**Easier:**
- Every future AI capability (Prompt Builder, and eventually the AI
  Assistant) has one shared, tested, explainable contract for "what
  governed knowledge is allowed into an AI-facing context," instead of
  hand-rolled selection/budget logic duplicated per consumer.
- A `ContextPackage` is independently inspectable - by a frontend, by an
  engineer auditing why a package looks the way it does, or by a test -
  without executing any retrieval or any AI call.
- Budget and coverage figures give a caller (today: a test or a
  frontend; tomorrow: the Prompt Builder) a structured, machine-readable
  way to detect and react to "this package is incomplete," rather than
  discovering it only once a downstream AI answer looks wrong.

**Harder / deferred:**
- Context Builder cannot itself call Structured Retrieval - a caller
  must retrieve first and pass the resulting `KnowledgeCandidateCollection`
  in explicitly. Solving that orchestration (e.g. a single endpoint that
  retrieves and assembles in one call) is explicitly out of this
  milestone's scope and, if ever needed, is a thin orchestration
  concern for a future caller (an application service or the eventual
  AI Assistant), not a reason for Context Builder to depend on
  Structured Retrieval's service or router.
- `KnowledgeCandidate.sort_key` is not exposed on the wire
  (`KnowledgeCandidateRead`), so Context Builder recomputes its own
  ranking key rather than reusing Structured Retrieval's already-computed
  one. This is a small, deliberate duplication of a *documented*
  ordering convention (`structured_retrieval.md`'s "Result Ordering"),
  never of Structured Retrieval's private scoring/matching internals.
- Coverage's `context_completeness` figure is a simple, fixed,
  equally-weighted average of the four base ratios - not a
  statistically validated model of "how much knowledge is enough."
  Adequate for Milestone 14's own "explain selection, don't invent
  confidence" requirement; a future milestone could weight it
  differently with a documented rationale and a version bump, the same
  discipline `scoring_policy.py`'s `SCORING_POLICY_VERSION` already
  establishes for Structured Retrieval.

## Rejected Alternatives

- **Let the future Prompt Builder consume `KnowledgeCandidateCollection`
  directly, with its own selection/budget logic.** Rejected: conflates
  prompt-formatting concerns with engineering decisions about which
  governed knowledge enters an AI capability's context, and gives every
  future AI capability no shared, testable contract.
- **Fold budget enforcement into Structured Retrieval's own `limit`.**
  Rejected: Structured Retrieval's limit bounds one request's result
  page; Context Builder's budget bounds a package that may be assembled
  from more than one retrieval call, across independent dimensions
  Structured Retrieval has no reason to know about.
- **Persist `ContextPackage`.** Rejected, for the same reason ADR-0010
  rejected persisting `StructuredRetrievalResult`: no requirement
  demonstrated a need for it this milestone, and a package is cheaply
  recomputable from its own inputs (a `KnowledgeCandidateCollection` and
  a `BudgetPolicy`) - persisting it would be a second, potentially stale
  copy of derived data with no clear owner.
- **Model `ContextSelectionPolicy` as a full, alternative ranking
  algorithm.** Rejected: Milestone 14 explicitly forbids heuristic or
  random selection; reusing the same, publicly documented ordering
  convention Structured Retrieval already uses (score, then kind
  priority, then natural key, then candidate id) keeps behavior
  predictable across both bounded contexts rather than introducing a
  second, divergent notion of "best" knowledge.
- **Give `ContextMetadata` only fixed, code-controlled fields, with no
  caller-supplied entries.** Rejected: Milestone 14 names "maximum
  metadata entries" as a real budget dimension, which only makes sense
  if metadata can genuinely vary in size - `ContextMetadataEntry` gives
  a caller a small, explicitly budget-capped way to attach audit-useful
  context (e.g. the originating Structured Retrieval request's mode)
  without turning `ContextMetadata` into an unbounded, untyped bag.
