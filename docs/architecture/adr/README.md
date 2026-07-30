# Architecture Decision Records

This directory holds SubstationOS's Architecture Decision Records (ADRs) —
short documents that capture a significant, hard-to-reverse architectural
decision: what was decided, why, and what was explicitly rejected instead.
`CLAUDE.md` §11 requires ADRs for exactly this class of decision ("a new
bounded context, a persistence choice, an external dependency"); this
directory is where they live.

## Why this convention, and why here

No usable ADR convention existed in the repository before Architecture
Freeze v1.0. A single file, `docs/decisions/0005-electrical-ontology.md`,
existed but was empty — no format, numbering rule, or required sections
were established anywhere. This directory defines that convention from
scratch, as instructed for Architecture Freeze v1.0, and is the convention
all future ADRs use.

**Known discrepancy, not resolved here:** `docs/decisions/` still exists,
still empty, and implies a second, competing location and numbering
sequence. This directory (`docs/architecture/adr/`) is the one actually in
use as of Architecture Freeze v1.0. Reconciling or retiring
`docs/decisions/` is left as an explicit follow-up (see the Architecture
Freeze Checklist) — not resolved silently, and not resolved here, since
doing so was outside this task's scope.

## Numbering

Sequential, four-digit, zero-padded, starting at `0001`, in this
directory's own sequence. Numbers are never reused, even if an ADR is later
superseded — a superseded ADR keeps its original number and gains a
`Status: Superseded by ADR-NNNN` marker; it is not deleted or renumbered.

## File naming

```
NNNN-kebab-case-title.md
```

Example: `0001-project-centric-architecture.md`.

## Required sections

Every ADR contains exactly these five sections, in this order:

- **Status** — one of `Proposed`, `Accepted`, `Rejected`, or
  `Superseded by ADR-NNNN`. An ADR recording a decision that is agreed in
  principle but whose implementation is deliberately deferred is still
  `Accepted` — the decision is accepted, even if the work is not yet
  scheduled. `Proposed` is reserved for a decision that has not yet been
  ratified by whoever owns SubstationOS's architecture.
- **Context** — the situation that made a decision necessary: what
  problem, what constraint, what conflicting requirement.
- **Decision** — the decision itself, stated as a clear, actionable
  sentence or short set of sentences — not a discussion, a decision.
- **Consequences** — what becomes easier, what becomes harder, and what
  future work this decision creates or forecloses. Both positive and
  negative consequences are recorded; an ADR with only upside is
  incomplete.
- **Rejected Alternatives** — every alternative seriously considered and
  not chosen, each with the specific reason it was rejected. An ADR with
  no rejected alternatives usually means the alternatives were never
  seriously considered, which is itself worth being honest about.

## What is, and is not, an ADR

An ADR records a decision, not a design. `docs/architecture/*.md` documents
(like `project_intelligence_architecture.md`) describe *how something
works*, in detail, and change as understanding improves. An ADR records
*that a specific choice was made, and why*, at a point in time — once
written, an ADR's Context and Decision are not edited to reflect later
changes of mind; a changed decision gets a new ADR that supersedes the old
one.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-project-centric-architecture.md) | Project-Centric Architecture | Accepted |
| [0002](0002-engineering-index-vs-project-knowledge-graph.md) | Separation of Engineering Index and Project Knowledge Graph | Accepted |
| [0003](0003-canonical-domain-vs-project-knowledge.md) | Separation of Canonical Domain and Project Knowledge | Accepted |
| [0004](0004-reviewed-facts-only-in-queryable-graph.md) | Reviewed Facts Only in the Queryable Project Knowledge Graph | Accepted |
| [0005](0005-project-vs-canonical-library-document-scope.md) | Explicit PROJECT versus CANONICAL_LIBRARY Document Scope | Accepted |
| [0006](0006-ai-as-interpretation-presentation-layer.md) | AI as Interpretation/Presentation Layer, Never Source of Engineering Truth | Accepted |
| [0007](0007-project-knowledge-graph-persistence.md) | Project Knowledge Graph Persistence — Execution Semantics, Database-Agnostic Store, and Deferred Neo4j | Accepted |
| [0008](0008-database-migration-governance.md) | Database Migration Governance — Alembic Replaces `create_all()` | Accepted |
| [0009](0009-legacy-knowledge-graph-isolation.md) | Legacy Knowledge Graph Isolation | Accepted |
| [0010](0010-structured-retrieval-foundation.md) | Structured Retrieval Foundation | Accepted |
| [0011](0011-context-builder-foundation.md) | Context Builder Foundation | Accepted |
| [0012](0012-prompt-builder-foundation.md) | Prompt Builder Foundation | Accepted |
| [0013](0013-llm-provider-abstraction-layer.md) | LLM Provider Abstraction Layer | Accepted |
| [0014](0014-llm-invocation-runtime.md) | LLM Invocation Runtime | Accepted |
| [0015](0015-engineering-response-foundation.md) | Engineering Response Foundation | Accepted |
| [0016](0016-engineering-session-foundation.md) | Engineering Session Foundation | Accepted |
| [0017](0017-conversation-foundation.md) | Conversation Foundation | Accepted |
| [0018](0018-working-memory-foundation.md) | Working Memory Foundation | Accepted |
| [0019](0019-engineering-request-classification.md) | Engineering Request Classification | Accepted |
| [0020](0020-engineering-engine-foundation.md) | Engineering Engine Foundation | Accepted |
| [0021](0021-engineering-workspace-document-viewer.md) | Engineering Workspace Document Viewer and Support-Chain Strategy | Accepted |
| [0022](0022-session-authentication-and-password-hashing.md) | Session Authentication and Password Hashing | Accepted |
