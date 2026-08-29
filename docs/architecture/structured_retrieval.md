# Structured Retrieval (Canonical Facts) — RETIRED

> # ⚠ RETIRED / HISTORICAL (EPIC 31.4)
>
> **This describes software that no longer exists.** Nothing below is a
> current architecture reference.
>
> | | |
> |---|---|
> | Runtime implementation | **Deleted.** `app/domain/structured_retrieval/**` and `app/services/structured_retrieval_service.py` are gone. |
> | Public API | **Withdrawn.** `POST /projects/{id}/structured-retrieval/plan` and `.../search` return `404`. |
> | Substrate | The **Canonical Facts graph projection**, itself retired - its seven tables were dropped by migration `f4a90c27b615`. |
> | Current implementation | **[governed_structured_retrieval.md](governed_structured_retrieval.md)** - Governed Structured Retrieval, over the Governed Knowledge Graph. |
> | Decision record | [ADR-0028](adr/0028-retire-the-canonical-facts-graph.md); [ADR-0010](adr/0010-structured-retrieval-foundation.md) is superseded by [ADR-0026](adr/0026-governed-structured-retrieval.md). |
>
> **Retained deliberately**, not left behind. Two things here are still
> worth reading:
>
> - **why deterministic-first was chosen**, and why embeddings, vector
>   search and NL interpretation were refused. Governed Structured
>   Retrieval keeps that principle and strengthened it.
> - **what the capability actually was**, so that the two capabilities
>   EPIC 31.4 removed outright - property-bag attribute search, and
>   broad lexical matching across attribute keys and values - can be
>   understood by whoever asks where they went.
>
> Two things below were **replaced rather than carried forward**: the
> **scoring policy** (governed retrieval ranks by documented match
> strategy, never by a weighted total) and **property-bag matching**
> (the governed graph deliberately has no property bag - ADR-0024).
>
> Everything after this banner is preserved as written when the system
> was live. It is not maintained.

---

**Original status:** As-built reference, Milestone 13 (Structured
Retrieval Foundation). For where this context sat in the pipeline of the
time, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## Pipeline

```
StructuredRetrievalRequest
        |
   Query Planning        (retrieval_query_planner.py - pure, no I/O)
        |
   Graph Query            (GraphQueryRepository / graph_query_service)
        |
   Candidate Construction (candidate_matching.py)
        |
   Deterministic Scoring  (candidate_aggregation.py)
        |
   KnowledgeCandidateCollection (candidate_ranking.py)
```

`app/services/structured_retrieval_service.py` orchestrates every
stage; nothing in `app/domain/structured_retrieval/**` performs I/O.

## Request model

A `StructuredRetrievalRequest` (built exclusively by
`StructuredRetrievalRequestFactory.create`, which enforces every
invariant below at construction time) always has:

- `project_id` - mandatory, positive.
- `mode` - one of the six `RetrievalMode` values (below).
- `criteria` - a non-empty, canonically ordered tuple of
  `RetrievalCriterion`, derived from whichever optional fields the
  caller supplied (`canonical_entity_id`, `entity_type`,
  `attribute_name`, `attribute_value`, `relationship_type`,
  `lexical_terms`).
- `limit` - `1..200` (`MIN_RESULT_LIMIT`/`MAX_RESULT_LIMIT` in
  `structured_retrieval_validator.py`).
- `include_neighborhood` / `neighborhood_depth` - depth must be `0`
  when neighborhood expansion is off, `1` when it's on (Graph Query
  itself supports only depth-1 traversal).
- `lexical_match_mode` - `ANY` or `LexicalMatchMode.ALL`, explicit on
  the request, never inferred.

Criteria are always evaluated in a fixed order regardless of the order
the caller supplied fields in:
`CANONICAL_ENTITY_ID → ENTITY_TYPE → RELATIONSHIP_TYPE → ATTRIBUTE_NAME
→ ATTRIBUTE_VALUE → LEXICAL_TERM` (`CRITERION_ORDER` in
`structured_retrieval_factory.py`).

## Retrieval modes

| Mode | Required criterion | Notes |
|---|---|---|
| `ENTITY_LOOKUP` | `CANONICAL_ENTITY_ID` | Single exact entity, by `"entity_type:canonical_id"`. |
| `ENTITY_TYPE_SEARCH` | `ENTITY_TYPE` | Every entity of the given type. |
| `ATTRIBUTE_SEARCH` | `ATTRIBUTE_NAME` and/or `ATTRIBUTE_VALUE` | Name-only (presence), name+value (presence, narrowed by value), or value-only (scans every attribute on every node for an exact value match). |
| `RELATIONSHIP_SEARCH` | `RELATIONSHIP_TYPE` | Every relationship of the given type. |
| `LEXICAL_SEARCH` | at least one `LEXICAL_TERM` | See Matching Rules. |
| `COMBINED` | any non-empty mix | The only mode where more than one criterion *kind* is allowed together. |

Every single-purpose mode rejects criterion kinds outside its own set
with `UnsupportedCriterionCombinationError` - mixing kinds is only
valid under `COMBINED` (`_ALLOWED_KINDS_FOR_MODE`/
`_REQUIRED_ANY_OF_KINDS_FOR_MODE` in `structured_retrieval_validator.py`).

## Matching rules

Deterministic, minimal, and explicit (`lexical_matching.py`) - **no
embeddings, no fuzzy/edit-distance matching, no stemming, no external
search engine, no NL intent detection**:

- **Exact token matching** - case-insensitive, whitespace-trimmed
  (`normalize_token`).
- **Normalized identifier matching** - lowercases and strips every
  non-alphanumeric character, so `"C-295"`, `"c 295"`, and `"C295"` are
  equal (`normalize_identifier`).
- **Prefix matching** - the normalized field *starts with* the
  normalized term. Applied only to canonical identifiers and
  relationship types, never to free-form attribute values.

**Known, deliberate limitation:** none of the three rules is a
*contains*/substring match. Searching `"295"` will **not** find
`"C-295"` - it doesn't equal it, and `"C-295"` doesn't start with
`"295"`. This is a documented boundary, not a bug: a substring match
would be closer to fuzzy matching than this milestone's "controlled,
explicitly-scoped" matching is meant to be. Search `"C-295"` or a
genuine prefix (`"C-2"`) instead.

Lexical fields checked: canonical identifier, entity type, attribute
keys, string attribute values (on nodes); relationship type (on
relationships). `LexicalMatchMode.ALL` requires every supplied term to
match somewhere on the *same* candidate; `ANY` requires only one.

## Scoring policy

Every `KnowledgeCandidateScore.total` is the sum of named
`KnowledgeCandidateScoreComponent` weights, fixed and documented in
`scoring_policy.py` (`SCORING_POLICY_VERSION`):

| Component | Weight |
|---|---:|
| Exact canonical id match | 100 |
| Normalized identifier match | 80 |
| Relationship natural-key match | 75 |
| Relationship type match | 60 |
| Entity type match | 50 |
| Attribute name match | 40 |
| Attribute value match | 35 |
| Lexical token match | 10 per distinct matched token |
| Neighborhood support | 5 |
| Multi-criterion support | 5 per additional distinct criterion kind beyond the first |

Changing a weight requires a documented domain rationale and a bump to
`SCORING_POLICY_VERSION` (echoed in every result's
`RetrievalExecutionMetadata`, so a caller can tell which policy
produced a given score).

### Deduplication and aggregation

The same logical entity/relationship/attribute discovered through more
than one criterion is merged, not duplicated
(`candidate_aggregation.py`):

- Score components are deduplicated by `(category, detail)` - the same
  evidence seen twice contributes once, but distinct evidence within
  the same category (e.g. two different matched lexical tokens) each
  contribute their own component.
- Reasons, matches, matched attributes/relationships, related
  entities, and provenance identifiers are unioned.
- A **multi-criterion support bonus** is added once per merged
  candidate when evidence from more than one distinct criterion *kind*
  converged on it.

### Candidate identity

`KnowledgeCandidate.candidate_id` is deterministic - never a random
UUID - derived from `(project, candidate kind, primary entity or
relationship, matched attribute where applicable)`
(`candidate_identity.py`). The same graph state and the same request
always produce the same candidate identifiers.

## Result ordering

Candidates are sorted by `sort_key = (-total_score, candidate_kind_priority,
natural_key, candidate_id)`:

1. Total score, descending.
2. Candidate kind priority: `ENTITY` (0) → `RELATIONSHIP` (1) →
   `ATTRIBUTE` (2) → `NEIGHBORHOOD` (3) - a candidate that *is* the
   matched entity ranks above one that only relates to it, above a
   bare attribute match, above neighborhood-only context.
3. Natural key (canonical id, or relationship natural key), ascending.
4. `candidate_id`, ascending - the final, always-deterministic
   tie-breaker.

The result `limit` is applied **only after** full deduplication and
ranking (`candidate_ranking.py`) - a caller always sees the true
top-N, never a limit applied before ranking could distort it.

## Neighborhood enrichment

Optional (`include_neighborhood=true`, `neighborhood_depth=1`).
Enriches only the **already-limited, final page** of `ENTITY`-kind
candidates with their direct (1-hop) neighbors as `related_entities` -
never the full pre-limit candidate pool. This bounds neighborhood
expansion to at most `limit` extra Graph Query round-trips
(`structured_retrieval_service._enrich_with_neighborhood`), satisfying
Milestone 13's "no unrestricted project-wide expansion" operational
safety requirement.

## Provenance

Every candidate carries:

- `graph_node_ids` / `graph_relationship_ids` - the `GraphEntityId`/
  natural-key identifiers of the graph rows involved, always present.
- `graph_execution_ids` - the `GraphExecution` id(s) that created the
  involved node(s)/relationship(s), when that column was populated
  (`ProjectGraphNodeRecord.created_by_execution_id`/
  `ProjectGraphRelationshipRecord.created_by_execution_id`, newly
  projected through `GraphNodeView`/`GraphRelationshipView` this
  milestone - see ADR-0010's context).
- `source_fact_ids` - **always empty in this milestone.** A
  `GraphNodeOperation`/`GraphRelationshipOperation`'s `source_fact_id`
  is ephemeral at execution time and is not persisted onto the
  node/relationship row itself; no schema change was made to add it
  (out of this milestone's scope - see the ADR's rejected
  alternatives). Represented as honestly absent, per Milestone 13's
  "do not invent provenance" rule, not silently omitted from the type.

The legacy Knowledge Graph path (`ProjectEntity`/`EntityRelation`) is
never read by Structured Retrieval - enforced by
`tests/architecture/test_bounded_context_dependencies.py::test_structured_retrieval_domain_does_not_import_forbidden_modules`.

## API

```
POST /projects/{project_id}/structured-retrieval/plan
POST /projects/{project_id}/structured-retrieval/search
```

`project_id` in the path is authoritative; the request body never
repeats it. `plan` builds and validates the request, then returns only
the `RetrievalQueryPlan` - no Graph Query call is made. `search`
executes the full pipeline and returns a `StructuredRetrievalResultRead`
(normalized request, plan, candidates, execution metadata).

### Example: exact entity lookup with neighborhood enrichment

```http
POST /projects/42/structured-retrieval/search
Content-Type: application/json

{
  "mode": "entity_lookup",
  "canonical_entity_id": "CABLE:C-295",
  "include_neighborhood": true,
  "neighborhood_depth": 1
}
```

### Example: combined search

```http
POST /projects/42/structured-retrieval/search
Content-Type: application/json

{
  "mode": "combined",
  "entity_type": "TRANSFORMER",
  "attribute_name": "rated_voltage",
  "limit": 10
}
```

### Errors

Every `StructuredRetrievalError` subtype (missing/unsupported
criteria, out-of-range limit, invalid neighborhood depth, blank/too
many/too long lexical terms, malformed canonical entity reference) maps
to `422 Unprocessable Entity` with the error's own message as `detail`
(`app/routers/structured_retrieval.py`). There is no 404: an
`ENTITY_LOOKUP` for a nonexistent entity, or any mode against an
empty/nonexistent project, is a **successful, empty result**
(`returned_count: 0`) - Structured Retrieval is a search endpoint, not
a get-resource-by-id endpoint, and follows Graph Query's own established
convention of never checking project existence on a pure read (a
nonexistent project and an existing-but-empty one are indistinguishable
from a read's point of view).

## Performance limitations

See [performance_baseline.md](performance_baseline.md) for
methodology and recorded numbers. In short: `LEXICAL_SEARCH`,
`COMBINED`, and the value-only shape of `ATTRIBUTE_SEARCH` all require
a full node and/or relationship scan (no SQL-side lexical or
attribute-value index exists) and inherit Graph Query's own
Python-side filtering costs; neighborhood enrichment is bounded to the
returned page, not the full candidate pool. None of these are fixed
this milestone - recorded as known algorithmic risk areas for a future
performance-focused milestone if real usage ever demands it.
