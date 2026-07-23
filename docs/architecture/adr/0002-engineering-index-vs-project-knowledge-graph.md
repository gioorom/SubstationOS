# ADR-0002: Separation of Engineering Index and Project Knowledge Graph

## Status

Accepted.

## Context

The current implementation (`app/services/knowledge_graph.py`,
`ingest_document`) extracts entities and relationships from an uploaded PDF
via an AI provider and writes them **directly** into the same
`ProjectEntity`/`EntityRelation` tables the query API
(`app/routers/knowledge_graph.py`) reads from. There is no intermediate
stage: a document's AI-extracted content becomes queryable "knowledge" the
moment extraction finishes, with no distinction between "a document
appears to mention this" and "an engineer has confirmed this is true."

`docs/architecture/project_intelligence_architecture.md` §5 identifies this
as the closest existing analogue to what should be two structurally
different things: a fast, disposable inventory of candidate mentions, and a
slow, trustworthy, queryable model of confirmed facts.

## Decision

SubstationOS separates these into two explicit layers:

- The **Engineering Index** — built automatically, immediately after
  Document Classification, with no review gate. It records candidate
  mentions of equipment, signals, cables, cabinets, frames, protections,
  drawings, functions, and cross-references, each tied to a document and
  page. It is freely rebuildable as classification/indexing logic improves
  and carries no trust guarantee.
- The **Project Knowledge Graph** — populated only from facts that have
  completed Engineering Review and project-level canonicalization (per
  ADR-0004). It is append-only and versioned, and it is the only layer the
  Semantic Query Engine and AI Assistant may read from.

A mention in the Engineering Index is a lead. A node in the Project
Knowledge Graph is a fact. The two are never represented by the same table
with a boolean "reviewed" flag; they are distinct layers with distinct
mutability and trust models.

## Consequences

- Users can browse and search a project's documents almost immediately
  after upload, via the Index, without waiting for engineering review to
  complete — a real usability benefit, not merely a safety mechanism.
- The Knowledge Graph's trust guarantee becomes structural: nothing
  unreviewed can reach it, because there is no code path that writes
  directly from extraction into the Graph.
- Requires building the Engineering Index as new infrastructure — it does
  not exist today (`docs/architecture/project_intelligence_architecture.md`,
  Component Responsibilities table: "Gap — does not exist").
- Requires changing `ingest_document` to stop writing directly into
  `ProjectEntity`/`EntityRelation` and instead write into the (new)
  Engineering Index, with the Graph populated only via the review and
  canonicalization workflow. This is a known, currently-unresolved gap —
  see ADR-0004 and the Architecture Freeze Checklist.

## Rejected Alternatives

- **One unified table with a `reviewed: bool` flag.** Rejected because it
  conflates two fundamentally different mutability and trust models — the
  Index is disposable and freely rebuilt, the Graph is append-only and
  versioned — into one schema. This is close to what exists today, and it
  is exactly the design that allowed the current gap (unreviewed facts
  being queryable) to occur silently: nothing in a shared table structurally
  prevents a query from ignoring the flag.
- **Skip the Index entirely; only ever expose reviewed data.** Rejected
  because it removes fast document browsability during what may be a long
  review backlog on a large project, which conflicts with
  `PRODUCT_VISION.md`'s goal of engineers understanding an installation
  "after pochi minuti" (a few minutes) of upload — an outcome only the fast,
  unreviewed Index can support at that speed.
