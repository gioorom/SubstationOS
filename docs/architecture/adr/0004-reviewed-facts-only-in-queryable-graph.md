# ADR-0004: Reviewed Facts Only in the Queryable Project Knowledge Graph

## Status

Accepted, and **satisfied since EPIC 31.1**.

This ADR carried the note "the current implementation does not yet comply
with this decision" from Architecture Freeze v1.0 until 2026-07-30. The
non-compliance is over: EPIC 31 built the governed graph that admits only
approved, applicable semantics, and
[ADR-0025](0025-retire-the-legacy-knowledge-graph.md) deleted
`ingest_document`, its two tables and its read routes. Nothing writes
engineering knowledge into a queryable graph without a named engineer
approving it. The historical text below is unchanged.

## Context

`app/services/knowledge_graph.py`'s `ingest_document` currently persists
AI-extracted entities and relationships directly into the tables
`app/routers/knowledge_graph.py`'s query endpoints read from. The only
trust signal present is a bare `EntityRelation.confidence: float`, with no
accompanying review state, no reviewer, no review date, and no
canonicalization step. This means every answer the system can currently
give is only as trustworthy as unreviewed AI output — a direct violation,
at project scope, of the Canonical Knowledge Protocol's Canonical Rules
(`CANONICAL_KNOWLEDGE_PROTOCOL.md` §8: "reviewed... approved...
traceable... versioned... engineering knowledge").

## Decision

Only facts whose review state — per the Canonical Knowledge Protocol's
`RAW` / `UNDER_REVIEW` / `APPROVED` / `REJECTED` / `SUPERSEDED` state
machine (`CANONICAL_KNOWLEDGE_PROTOCOL.md` §6) — is `APPROVED`, and which
have subsequently completed project-level canonicalization
(`knowledge/extraction/README.md` Stage 4), may become a node or edge in
the queryable Project Knowledge Graph. This applies without exception,
including for documents considered simple, urgent, or low-risk by whoever
is uploading them. A Project's size, deadline, or perceived simplicity is
never grounds for skipping Engineering Review.

## Consequences

- Query results become available only after human review completes,
  rather than instantly on upload — a deliberate, accepted latency cost in
  exchange for a categorical trust guarantee (per
  `CANONICAL_KNOWLEDGE_PROTOCOL.md` §1, "traceability is more important
  than AI output").
- Requires implementing review-state, reviewer, and review-date fields
  that do not exist on `EntityRelation` (or `ProjectEntity`) today, and
  requires implementing the Engineering Index (ADR-0002) as the landing
  zone for unreviewed extraction output, so nothing unreviewed has
  anywhere to go except the Index.
- **This ADR recorded an accepted decision, not a completed state.** As of
  Architecture Freeze v1.0, `ingest_document` still wrote AI-extracted
  entities directly into the queryable graph, bypassing this decision
  entirely — a known, explicitly tracked gap (see the Architecture Freeze
  Checklist, "Mandatory review gate").

  **That gap was closed by EPIC 31.1.** `ingest_document` and both its
  tables are gone; the queryable graph is now a projection over statements
  an engineer approved. See
  [ADR-0025](0025-retire-the-legacy-knowledge-graph.md).

## Rejected Alternatives

- **Surface unreviewed facts with a confidence-based warning label instead
  of gating them.** Rejected because it shifts the burden of judging
  trustworthiness onto the end user for every single answer, which defeats
  the purpose of a domain model whose entire value proposition is that
  this judgment has already been made by a qualified engineer.
- **Require review only for "important" fields, skip it for the rest.**
  Rejected because importance cannot be reliably judged before a fact is
  understood in context, and partial review reintroduces exactly the
  inconsistency the Canonical Knowledge Protocol exists to prevent — a
  graph that is "mostly" reviewed is, for trust purposes, unreviewed.
