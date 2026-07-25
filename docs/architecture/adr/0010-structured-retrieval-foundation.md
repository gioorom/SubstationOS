# ADR-0010: Structured Retrieval Foundation

## Status

Accepted.

## Context

By Milestone 12, the governed knowledge pipeline (Documents →
Engineering Index → Proposed Claims → Review Workflow →
Canonicalization → Graph Builder → Project Knowledge Graph → Graph
Query) is complete, hardened, and produces a deterministic, queryable
graph. Graph Query's own read model (`GraphQueryRepository`) supports
exact lookups: by id, by type, by attribute presence, by 1-hop
adjacency, statistics, orphans. Nothing yet turns "I have a graph I can
query exactly" into "I can hand a caller a ranked, explainable set of
knowledge candidates relevant to a request that names several criteria
at once" - the shape every future consumer (a frontend search box, a
Context Builder assembling an LLM prompt, an AI Assistant) actually
needs.

Two temptations existed and were both rejected before writing any
code:

1. **Skip straight to embeddings/vector search.** Attractive because
   it is what "retrieval" usually means in an AI system, but it would
   retrieve over raw document *chunks*, not governed engineering
   knowledge - reintroducing exactly the ADR-0004 problem (unreviewed
   content reachable as if it were fact) one layer up, and coupling
   the very first retrieval capability to an AI provider before this
   project has ever needed one for reads.
2. **Let the AI Assistant (not yet built) query the graph directly,
   per-request, with hand-rolled logic each time.** This would
   duplicate matching/scoring logic across every future consumer and
   give none of them a shared, testable, explainable contract.

## Decision

### 1. Structured Retrieval operates on governed graph state, never raw chunks

Every `KnowledgeCandidate` Structured Retrieval returns is built from
Graph Query's own read-model types (`GraphNodeView`/
`GraphRelationshipView`) - never a document chunk, never unreviewed
Engineering Index or Proposed Claims content, never the legacy
`ProjectEntity`/`EntityRelation` path. This is a direct, deliberate
extension of ADR-0004's guarantee one layer further downstream: if a
fact was not reviewed and approved before it became a graph node, it
is not retrievable through Structured Retrieval either. Retrieval
candidates carry references and identifiers, not copies of
`CanonicalFact`/`ProposedClaim`/document aggregates - keeping
Structured Retrieval a thin, derived view over graph state, never a
second store of engineering truth.

### 2. The first retrieval implementation is deterministic, structured-criteria retrieval - not semantic search

A `StructuredRetrievalRequest` names its criteria explicitly
(`canonical_entity_id`, `entity_type`, `attribute_name`/`attribute_value`,
`relationship_type`, `lexical_terms`) and its `RetrievalMode`
explicitly - there is no free-text question, no natural-language intent
detection, and no ranking signal that isn't a named,
weighted `KnowledgeCandidateScoreComponent` a caller can inspect. This
is intentional sequencing, not caution for its own sake: a system that
can already answer "what matches these exact criteria, and why" is a
solid foundation to build a semantic layer *on top of* later; a system
that starts with embeddings has no deterministic baseline to fall back
to, verify against, or explain results in terms of. The bounded context
is named `structured_retrieval`, not `semantic_retrieval`, specifically
so this distinction is visible in the codebase itself, not just in
prose.

### 3. Embeddings, vector search, and NL interpretation are deferred, not rejected

Nothing in this milestone forecloses a future Semantic Retrieval layer
(see `knowledge_pipeline_overview.md`'s "Required conceptual
distinction" block). The deferral is deliberate: embeddings/vector
search solve a different problem (fuzzy, similarity-based matching over
large text) than this milestone needs to solve (turn already-known
structured criteria into ranked, explainable graph candidates), and
introducing them now would mean choosing a vector store, an embedding
model, and a hybrid ranking strategy before the deterministic
foundation they'd need to be validated against even existed.

### 4. Candidate identity is deterministic; scoring is a fixed, documented sum of named components

`KnowledgeCandidate.candidate_id` is derived from the semantic identity
of (project, candidate kind, primary entity/relationship, matched
attribute where applicable) - never a random UUID - so the same graph
state and the same request always produce the same identifiers and the
same ordering (`candidate_identity.py`). Every `KnowledgeCandidateScore.total`
is the sum of named `KnowledgeCandidateScoreComponent`s drawn from a
single, fixed, documented weight table (`scoring_policy.py`) - no
machine learning, no unexplained numbers. Full rationale, the matching
rules, and the exact ordering algorithm are documented in
`docs/architecture/structured_retrieval.md`, not repeated here (an ADR
records the decision, not the mechanics - see the ADR README's "What
is, and is not, an ADR").

### 5. Structured Retrieval, Context Builder, and the AI Assistant are three separate, ordered layers

```
Graph Query            = deterministic read model over current graph state
Structured Retrieval   = ranked, explainable KnowledgeCandidates from structured criteria
Context Builder        = (future) bounded, provenance-aware context package from ranked candidates
AI Assistant            = (future) consumer, not owner, of engineering truth
```

Structured Retrieval consumes Graph Query exclusively through
`GraphQueryRepository`/`graph_query_service` (never `GraphStore`, never
a second independent graph read architecture). The next milestone
(Context Builder) is expected to consume Structured Retrieval's ranked
`KnowledgeCandidateCollection` the same way Structured Retrieval
consumes Graph Query - each layer adding exactly one new
responsibility, never re-deriving a decision an earlier layer already
made, the same discipline every earlier stage of this pipeline follows
(`docs/architecture/knowledge_pipeline_overview.md`).

## Consequences

**Easier:**
- Every future retrieval consumer (frontend search, Context Builder,
  eventually an AI Assistant) has one shared, tested, explainable
  contract instead of hand-rolled graph queries duplicated per
  consumer.
- A wrong or surprising result is always explainable in terms of named
  score components and matched criteria - there is no black-box
  ranking to debug.
- A future Semantic Retrieval layer has a deterministic baseline to be
  validated against, compared to, and fall back to when embeddings are
  uncertain or unavailable.

**Harder / deferred:**
- Structured Retrieval cannot answer a free-text question - a caller
  (frontend or future AI Assistant) must translate intent into
  structured criteria itself. Solving that translation is explicitly
  out of this milestone's scope and is the natural shape of a future
  Semantic Retrieval or NL-interpretation milestone.
- Lexical matching is deliberately limited (exact token, normalized
  identifier, scoped prefix - no fuzzy/edit-distance matching); a term
  that doesn't share a normalized form or prefix with a field will not
  match, even where a human reader would recognize the connection (see
  `structured_retrieval.md`'s "Matching Rules" for the exact,
  documented boundary).

## Rejected Alternatives

- **Build embeddings/vector search as the first retrieval capability.**
  Rejected: retrieves over raw chunks, not governed knowledge (a
  step backward from ADR-0004), and commits to a vector store/embedding
  model/AI provider before any deterministic baseline exists to
  validate it against.
- **Let each future consumer query Graph Query directly with its own
  matching/ranking logic.** Rejected: duplicates matching and scoring
  logic per consumer, with no shared, testable contract and no
  consistent explainability guarantee.
- **Name the bounded context `semantic_retrieval` now, implement it
  deterministically, and "upgrade" it later.** Rejected: the name
  would misdescribe the milestone's actual capability (per
  `knowledge_pipeline_overview.md`'s explicit distinction between
  Structured Retrieval and the future Semantic Retrieval layer) and
  risk a future reader assuming embedding-based behavior that does not
  exist.
- **Persist retrieval results.** Rejected: no requirement demonstrated
  a need for it this milestone, and retrieval results are cheaply
  recomputable from governed graph state on every request - persisting
  them would be a second, potentially stale copy of derived data with
  no clear owner.
