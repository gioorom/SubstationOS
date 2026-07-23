# ADR-0003: Separation of Canonical Domain and Project Knowledge

## Status

Accepted.

## Context

The Canonical Domain (`app/domain/ontology/**`: Equipment Definitions,
Attribute Definitions, and the Relationship Vocabulary and Domain
Constraints described in
`docs/architecture/project_intelligence_architecture.md` §1) is shared
across every project. It is the vocabulary that defines what *can* exist.
Project Knowledge — what a specific installation's documents show *does*
exist — is produced continuously, by many concurrent extraction sessions,
across potentially thousands of projects (ADR-0001). If project-level
extraction were permitted to create or modify Canonical Domain concepts as
a side effect, one project's document quirks, mislabeled equipment, or
extraction error could corrupt the shared vocabulary every other project
also depends on.

## Decision

Project Knowledge Extraction (`knowledge/extraction/README.md` Stage 5,
"Domain Mapping") may only produce facts that reference existing Canonical
Domain concepts by `id`. It never creates, edits, or deletes a Canonical
Domain concept as a side effect of processing a project's documents. If a
document contains something with no matching canonical concept, the fact
is recorded with an explicit unresolved open question and carried forward
unmapped — it is not auto-created.

Extending the Canonical Domain is a separate, deliberate, human-governed
process, following the existing YAML-authoring discipline (`CLAUDE.md` §7)
and the Canonical Knowledge Protocol's own lifecycle
(`CANONICAL_KNOWLEDGE_PROTOCOL.md` §2, Stages 5–10). It is never an
automatic or implicit consequence of any single project's extraction run.

## Consequences

- Guarantees the Canonical Domain evolves slowly and deliberately even as
  project-level extraction runs continuously and at scale.
- Requires an explicit escalation workflow — not yet designed — for an
  engineer to turn a project's unmapped fact into a request to extend the
  Canonical Domain. Until that workflow exists, unmapped facts accumulate
  as a visible backlog of open questions rather than silently vanishing or
  silently becoming ad hoc canonical concepts.
- Some project facts may remain permanently unmapped to any canonical
  concept if that escalation is never pursued. This is an accepted,
  visible gap (recorded as `Not specified` / an open question, per the
  Canonical Knowledge Protocol's Extraction Rules) rather than a hidden
  one.
- Requires the extraction pipeline to actually consult the Canonical
  Domain catalog during Domain Mapping — today's `ingest_document` does
  not do this at all; the AI extractor assigns free-text `EntityType`
  values with no reference back to `app/domain/ontology/**`. This is a
  known implementation gap, not fixed by this ADR.

## Rejected Alternatives

- **Let extraction auto-create a new canonical concept when no match is
  found.** Rejected because it removes human governance from the one layer
  that must stay universally consistent across every project, and would
  let a single poorly-scoped extraction session pollute the vocabulary
  every other project relies on — directly contradicting `CLAUDE.md` §16's
  "Backwards compatibility of the ontology" principle.
- **Give each project its own private copy of the ontology.** Rejected
  because it defeats the purpose of a shared, reusable domain model:
  cross-project consistency, reuse, and comparison would become impossible,
  and every project would have to independently rediscover and redefine
  concepts (e.g. "what is a circuit breaker") that are already solved
  problems.
