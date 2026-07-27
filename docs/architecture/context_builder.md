# Context Builder

**Status:** As-built reference, Milestone 14 (Context Builder
Foundation). Describes the `context_builder` bounded context as
implemented - for the decision record (why a dedicated assembly layer,
why it owns budget and coverage, why the future Prompt Builder must not
duplicate this logic), see
[ADR-0011](adr/0011-context-builder-foundation.md). For where this
context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[structured_retrieval.md](structured_retrieval.md).

## Pipeline

```
KnowledgeCandidateCollection
        |
   Selection            (candidate_selection.py - pure, no I/O)
        |
   Aggregation           (context_aggregation.py)
        |
   Coverage Analysis     (coverage_analysis.py)
        |
   Budget Enforcement    (budget_enforcement.py, context_metadata.py,
        |                 context_warnings.py)
   ContextPackage
```

`app/services/context_builder_service.py` validates the request
through `ContextBuildRequestFactory` and delegates assembly to
`app/domain/context_builder/context_package_assembler.py`; nothing in
`app/domain/context_builder/**` performs I/O, calls Graph Query,
Structured Retrieval, or an AI provider.

## Input

Context Builder's entire input is Structured Retrieval's own
`KnowledgeCandidateCollection` (`app.domain.structured_retrieval.structured_retrieval_models`),
consumed as a shared, stable vocabulary the same way Structured
Retrieval itself consumes Graph Query's `GraphNodeView`/
`GraphRelationshipView`. Context Builder never calls Structured
Retrieval - a caller retrieves first, then passes the resulting
collection to `POST /projects/{project_id}/context-builder/build`
directly.

## Configuration

A `ContextBuildRequest` (built exclusively by
`ContextBuildRequestFactory.create`, which enforces every invariant
below at construction time) always has:

- `project_id` - mandatory, positive.
- `candidates` - the input `KnowledgeCandidateCollection`. An empty
  collection is valid, not an error - it produces a valid, empty
  `ContextPackage`.
- `configuration` - a `ContextBuilderConfiguration` bundling the
  `BudgetPolicy` in effect (six independently configurable limits;
  every field optional on the API, falling back to the documented
  default in `app/domain/context_builder/budget_policy.py` when
  omitted) and the `ContextSelectionPolicy` version.
- `metadata_entries` - zero or more caller-supplied
  `(key, value)` pairs, budget-capped by `max_metadata_entries`.
- `retrieval_policy_version` - optional; a caller may echo the
  originating `StructuredRetrievalResult.metadata.scoring_policy_version`
  here so `ContextMetadata` can record which retrieval policy produced
  the input collection, "when available" (Milestone 14's own phrase -
  Context Builder never infers this itself).

Budget overflow (more candidates than a limit allows) is never a
validation error - it is routine, expected, warned-about behavior. Only
structurally invalid input (a non-positive `project_id`, a budget field
outside its documented bounds, a blank metadata entry key) raises a
typed `ContextBuilderError`.

## Selection

Candidates are ordered deterministically by `(-score.total, candidate
kind priority, natural key, candidate id)` - the same convention
`structured_retrieval.md`'s "Result Ordering" documents for
`KnowledgeCandidate.sort_key`. Selection recomputes this key
independently from `KnowledgeCandidate`'s own public fields rather than
trusting `sort_key` itself: that field is Structured Retrieval's own
internal ranking aid, and `KnowledgeCandidateRead` (Structured
Retrieval's own API response shape) deliberately never exposes it - see
`app/schemas/context_builder.py`'s `_candidate_from_read`.

An overall `max_candidates` cap and three per-kind caps
(`max_entities`/`max_relationships`/`max_attributes`) are enforced in a
single linear scan over the ranked candidates: a candidate whose own
kind has already reached its cap is skipped without consuming the
overall budget, so a lower-ranked candidate of a still-open kind
further down the list can still be admitted. `NEIGHBORHOOD`-kind
candidates are bounded only by `max_candidates` - Milestone 14 defines
no dedicated neighborhood budget dimension.

## Aggregation

Selection's admitted, already-ordered candidates are grouped into
`ContextSection`s by `KnowledgeCandidateKind` (always four sections -
`ENTITY`/`RELATIONSHIP`/`ATTRIBUTE`/`NEIGHBORHOOD` - even when empty),
and the same grouping is exposed as `ContextPackage.selected_entities`/
`selected_relationships`/`selected_attributes`. A single O(n) pass;
order within each kind is preserved from Selection, never re-derived.

## Coverage

`CoverageReport` measures **selection completeness**, never engineering
confidence or certainty about the underlying facts (Milestone 14's
explicit "do not invent confidence percentages" rule):

| Metric | Formula |
|---|---:|
| `entity_coverage` | selected entities / retrieved entities |
| `relationship_coverage` | selected relationships / retrieved relationships |
| `attribute_coverage` | selected attributes / retrieved attributes |
| `candidate_utilization` | selected candidates / retrieved candidates |
| `context_completeness` | mean of the four ratios above |

"Retrieved" always means "present in the input `KnowledgeCandidateCollection.candidates`"
- not Structured Retrieval's own `total_before_limit` (a detail
upstream of Context Builder's boundary). A ratio is `1.0` when nothing
was available in that category (vacuously complete - there is nothing
missing), never a divide-by-zero.

## Budget

Six independently tracked dimensions, each reported as a
`BudgetConsumption` (`requested`/`accepted`/`discarded`/`limit`/
`utilization`): `candidates`, `entities`, `relationships`, `attributes`
(from Selection), `metadata_entries` (from metadata truncation), and
`warnings` (from warning truncation). `ContextBudget.exceeded` is `True`
whenever any dimension discarded at least one item. Defaults
(`app/domain/context_builder/budget_policy.py`):

| Field | Default |
|---|---:|
| `max_candidates` | 100 |
| `max_entities` | 50 |
| `max_relationships` | 50 |
| `max_attributes` | 50 |
| `max_metadata_entries` | 20 |
| `max_warnings` | 50 |

## Warnings

Generated in a fixed, documented priority order, then truncated to
`max_warnings` (the truncation itself reported as the `warnings`
`BudgetConsumption`):

1. `budget_exceeded` - one per budget dimension with `discarded > 0`.
2. `missing_provenance` - one per selected candidate with no
   `graph_execution_ids` (a real, honestly-observable gap per
   `structured_retrieval.md`'s Provenance section - never triggered by
   `source_fact_ids`, which is always empty this milestone and would
   fire for every candidate, never a useful signal).
3. `missing_attributes` / `missing_relationships` - only when that kind
   was actually retrieved but none survived selection; never for a kind
   that was never offered to Context Builder in the first place (an
   empty or narrowly-scoped input collection is not a "gap").
4. `partial_coverage` - one summary warning naming every coverage
   category below `1.0`.
5. `candidate_discarded` - one per candidate Selection ranked but did
   not admit, naming which budget dimension discarded it.

## Statistics

`ContextStatistics` summarizes the already-computed results:
`selected_candidate_count`, `discarded_candidate_count`,
`entity_count`, `relationship_count`, `attribute_count`, and the full
`coverage_summary`/`budget_summary` - never persistence statistics,
never a recomputation of anything an earlier stage already decided.

## Metadata

`ContextMetadata` carries `context_builder_version`, `assembled_at`
(supplied by the caller as `now`, never read from the wall clock inside
the domain layer - CLAUDE.md SS16, Reproducibility),
`selection_policy_version`, `budget_policy_version`,
`retrieval_policy_version` (optional, "when available"), and
budget-capped caller-supplied `entries`. No secrets are ever placed
here.

## Provenance

`ContextPackage.selected_candidates` carries the exact
`KnowledgeCandidate` objects Structured Retrieval produced - scores,
reasons, matches, and every provenance field, unchanged. Context
Builder never invents provenance; where it is honestly absent, a
`missing_provenance` warning represents that explicitly.

## API

```
POST /projects/{project_id}/context-builder/build
```

`project_id` in the path is authoritative; the request body never
repeats it. The body's `candidates` field is exactly the
`candidates` object a prior `/structured-retrieval/search` call
returned; every budget field is optional and falls back to the
documented default when omitted. Response: a `ContextBuilderResultRead`
(the request's own configuration, paired with the resulting
`ContextPackageRead`).

### Example

```http
POST /projects/42/context-builder/build
Content-Type: application/json

{
  "candidates": { "candidates": [ ... ], "total_before_limit": 12, "returned_count": 12, "applied_limit": 20 },
  "max_candidates": 20,
  "max_entities": 10,
  "metadata_entries": [{"key": "mode", "value": "entity_type_search"}]
}
```

### Errors

Every `ContextBuilderError` subtype (invalid project id, a budget field
outside its documented bounds, a blank metadata entry key) maps to
`422 Unprocessable Entity`. Budget overflow relative to the supplied
candidates is never an error - it is reported through `warnings` and
`budget.exceeded` instead.

## Performance

Assembly is O(n log n) in the number of candidates in the input
collection, dominated entirely by Selection's ranking sort; every later
stage (Aggregation, Coverage Analysis, metadata/warning truncation,
Statistics) is a single O(n) or O(1) pass over already-materialized
results. Assembly cost scales with candidate count, never with graph
size - Context Builder performs no database query of its own. See
[performance_baseline.md](performance_baseline.md) for recorded numbers
(`context_builder_within_budget`/`context_builder_tight_budget`
operations).
