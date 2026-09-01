# ADR Index

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

**32 ADRs**, all under `docs/architecture/adr/`. The authoritative status column
lives in `docs/architecture/adr/README.md` — statuses below are copied from it,
not inferred. Individual ADR files do not all carry a status heading; where the
index is the only source, it is the source.

Summaries are one line each and lossy by design. **Read the ADR before relying
on it.**

---

## Governing the engineering pipeline

| ADR | Title | Status | Decision, in one line | Read before touching |
|---|---|---|---|---|
| [0023](../architecture/adr/0023-human-review-append-only-judgement.md) | Human Review as Append-Only Judgement, with Identity-Based Revalidation | Accepted | Review decisions are never edited or deleted; applicability is decided by statement identity, not by a status field. | Human Review, semantics identity |
| [0024](../architecture/adr/0024-governed-knowledge-graph-as-projection.md) | The Governed Knowledge Graph is a Rebuildable Projection | Accepted | The graph is derived from approved statements and can be rebuilt; it is not a source of truth. | Graph, promotion, retrieval |
| [0026](../architecture/adr/0026-governed-structured-retrieval.md) | Governed Structured Retrieval | Accepted | Retrieval reads governed knowledge only, with closed ambiguity outcomes and no query language. | Retrieval |
| [0027](../architecture/adr/0027-governed-context-assembly.md) | Governed Context Assembly | Accepted | Context selects and budgets what retrieval returned, and performs no I/O. | Context builder |
| [0029](../architecture/adr/0029-deterministic-engineering-reasoning-foundation.md) | Deterministic Engineering Reasoning Foundation | Accepted | Reasoning is deterministic, reads governed knowledge, and its conclusions are not governed knowledge. | Reasoning |
| [0030](../architecture/adr/0030-governed-structural-relationship-semantics.md) | Governed Structural Relationship Semantics Foundation | Accepted | Introduces governed structural-location semantics (`IS_LOCATED_IN`) as reference-designation meaning. | Semantics, structural work |
| [0031](../architecture/adr/0031-deterministic-shared-structural-location-reasoning.md) | Deterministic Shared Structural Location Reasoning | Accepted | Two governed assets sharing a governed structural location is a *derived* conclusion, not governed knowledge. | Reasoning |
| [0032](../architecture/adr/0032-upstream-identity-in-derived-set-reuse.md) | Upstream Identity in Derived-Set Reuse | **Amended (32.E2.4)** | A derived artifact is reusable only when its upstream identity and local contract are compatible; the amendment replaces natural-key propagation with a deterministic artifact identity chain. | **Anything touching reuse, identity, policy or contract versions** |

**ADR-0032 is the one to read in full before any identity work.** The original
decision and its amendment are both live: the rule is unchanged, the enforcement
mechanism was replaced.

## Retirements — do not treat these surfaces as available

| ADR | Title | Status | Note |
|---|---|---|---|
| [0025](../architecture/adr/0025-retire-the-legacy-knowledge-graph.md) | Retire the Legacy Knowledge Graph | Accepted | The legacy graph stack is gone; no domain packages remain for it. |
| [0028](../architecture/adr/0028-retire-the-canonical-facts-graph.md) | Retire the Canonical Facts Graph | Accepted | Supersedes ADR-0007. |
| [0007](../architecture/adr/0007-project-knowledge-graph-persistence.md) | Project Knowledge Graph Persistence — Execution Semantics, Database-Agnostic Store, Deferred Neo4j | **Superseded by ADR-0028** | Historical. |
| [0010](../architecture/adr/0010-structured-retrieval-foundation.md) | Structured Retrieval Foundation | **Superseded by ADR-0026** | Historical. |
| [0009](../architecture/adr/0009-legacy-knowledge-graph-isolation.md) | Legacy Knowledge Graph Isolation | Accepted | Isolation decision that preceded retirement. |

## Foundational structure

| ADR | Title | Status | Decision, in one line |
|---|---|---|---|
| [0001](../architecture/adr/0001-project-centric-architecture.md) | Project-Centric Architecture | Accepted | The project is the root aggregate everything is scoped to. |
| [0002](../architecture/adr/0002-engineering-index-vs-project-knowledge-graph.md) | Separation of Engineering Index and Project Knowledge Graph | Accepted | Candidate mentions are not governed knowledge. |
| [0003](../architecture/adr/0003-canonical-domain-vs-project-knowledge.md) | Separation of Canonical Domain and Project Knowledge | Accepted | The reference ontology is distinct from what a project asserts. |
| [0004](../architecture/adr/0004-reviewed-facts-only-in-queryable-graph.md) | Reviewed Facts Only in the Queryable Project Knowledge Graph | Accepted | Nothing unreviewed becomes queryable knowledge. |
| [0005](../architecture/adr/0005-project-vs-canonical-library-document-scope.md) | Explicit PROJECT versus CANONICAL_LIBRARY Document Scope | Accepted | A document's scope is explicit, never inferred. |
| [0006](../architecture/adr/0006-ai-as-interpretation-presentation-layer.md) | AI as Interpretation/Presentation Layer, Never Source of Engineering Truth | Accepted | **The constraint the whole architecture is built around.** |
| [0008](../architecture/adr/0008-database-migration-governance.md) | Database Migration Governance — Alembic Replaces `create_all()` | Accepted | Schema changes are migrations, reviewed and ordered. |

## Answering path

| ADR | Title | Status | Decision, in one line |
|---|---|---|---|
| [0011](../architecture/adr/0011-context-builder-foundation.md) | Context Builder Foundation | Accepted | Context assembly as its own bounded context. |
| [0012](../architecture/adr/0012-prompt-builder-foundation.md) | Prompt Builder Foundation | Accepted | Prompt rendering is separate from context selection. |
| [0013](../architecture/adr/0013-llm-provider-abstraction-layer.md) | LLM Provider Abstraction Layer | Accepted | Providers sit behind a domain-owned port. |
| [0014](../architecture/adr/0014-llm-invocation-runtime.md) | LLM Invocation Runtime | Accepted | Invocation is an application concern, not a domain one. |
| [0015](../architecture/adr/0015-engineering-response-foundation.md) | Engineering Response Foundation | Accepted | The response envelope and its source contract. |
| [0019](../architecture/adr/0019-engineering-request-classification.md) | Engineering Request Classification | Accepted | Intent classification precedes answering. |
| [0020](../architecture/adr/0020-engineering-engine-foundation.md) | Engineering Engine Foundation | Accepted | The engine orchestrates intent, context and response. |

## Session, conversation and access

| ADR | Title | Status | Decision, in one line |
|---|---|---|---|
| [0016](../architecture/adr/0016-engineering-session-foundation.md) | Engineering Session Foundation | Accepted | Sessions as a bounded context. |
| [0017](../architecture/adr/0017-conversation-foundation.md) | Conversation Foundation | Accepted | Conversation state distinct from session state. |
| [0018](../architecture/adr/0018-working-memory-foundation.md) | Working Memory Foundation | Accepted | Working memory derived from prior responses. |
| [0021](../architecture/adr/0021-engineering-workspace-document-viewer.md) | Engineering Workspace Document Viewer and Support-Chain Strategy | Accepted | How a user follows a claim back to the document. |
| [0022](../architecture/adr/0022-session-authentication-and-password-hashing.md) | Session Authentication and Password Hashing | Accepted | Authentication approach. |

---

## When you must read an ADR

- **Before changing a governance boundary** — 0004, 0023, 0024, 0029.
- **Before changing reuse, identity or any policy/contract version** — 0032,
  including its amendment. This is the most common trap: the versions look like
  ordinary constants and are not.
- **Before adding a relationship or vocabulary member** — 0030, 0031, and the
  vocabulary-closure fitness tests.
- **Before touching the graph** — 0024, 0025, 0028.
- **Before adding a bounded context, a persistence choice or an external
  dependency** — `CLAUDE.md` §11 requires a new ADR for exactly that class of
  decision. Discover the next free number from the directory; do not guess.

An ADR is a decision record, not a specification. Where an ADR and current code
disagree, that is a discrepancy to **record**, not to silently reconcile.
