 # ADR-0006: AI as Interpretation/Presentation Layer, Never Source of Engineering Truth

## Status

Accepted.

## Context

`CLAUDE.md` §3 already establishes "AI as a Service" as a binding
architectural principle: "AI is an adapter behind a domain-owned interface,
never a hard dependency of the domain." `docs/architecture/project_intelligence_architecture.md`
§8 walks through the Semantic Query Engine's worked example, in which an
LLM is used at two distinct points: interpreting a natural-language
question into a structured graph query, and composing a natural-language
answer from data the graph has already returned. The Canonical Knowledge
Protocol's Extraction Rules (`CANONICAL_KNOWLEDGE_PROTOCOL.md` §4, and
Engineering Principle 2, "No hallucinations") already forbid AI inference
during extraction. This ADR extends the same guarantee to query answering,
where the risk of an LLM "helpfully" filling a gap with plausible-sounding
but unsourced text is just as real.

## Decision

An LLM, anywhere in SubstationOS, may only ever perform one of two roles:

1. **Translate** between natural language and a structured representation
   — a question into a graph query, a document into a structured extraction
   prompt response — never asserting a fact as part of this translation.
2. **Compose** natural-language text from data that already exists, fully
   sourced, in the Project Knowledge Graph or Canonical Domain, *before*
   the LLM was invoked for that purpose.

An LLM is never permitted to assert an engineering fact that does not
already exist, with its own citation, in the system. This applies
identically during Knowledge Extraction (Raw Extraction may only transcribe
what a document states) and during Query Services (an answer may only
restate what the graph returned).

## Consequences

- Every AI touchpoint — classification, extraction, query interpretation,
  answer generation — sits behind the same `AIProvider` port already
  implemented at `app/services/ai/base.py`, making the underlying model or
  provider swappable without touching any domain-facing interface.
- An answer with zero supporting graph data is architecturally forced to
  state that no such record exists, never to produce a plausible guess —
  this is a structural guarantee arising from the query workflow's shape
  (interpret → identify project → query graph → collect documents →
  generate answer), not a prompting instruction that could be bypassed.
- Requires discipline in all future prompt design — both extraction prompts
  (`knowledge/extraction/prompts/*.md`, which already follow this rule) and
  the not-yet-built query-interpretation and answer-generation prompts — to
  never ask a model to "fill in," "infer," or "estimate" missing
  information.
- The existing `services/ai/relationship_extractor.py` is implemented but
  currently disabled in the ingest flow; re-enabling it must happen only
  once its output is routed through Engineering Review (ADR-0004), not
  directly into the graph, or its re-enablement would itself violate this
  ADR by increasing the volume of unreviewed "fact-shaped" AI output.

## Rejected Alternatives

- **Allow the AI Assistant to supplement graph answers with general
  engineering knowledge when the graph is incomplete.** Rejected because it
  silently blends sourced fact with unsourced, plausible-sounding text in
  the same answer, which a user has no way to tell apart — directly
  undermining the traceability guarantee that is this platform's core
  value proposition.
- **Let the LLM write back to the Project Knowledge Graph during query
  answering** (e.g. caching an inferred fact it generated as if it were
  confirmed knowledge). Rejected because it would let a read-only query
  session mutate canonicalized project knowledge outside the Engineering
  Review and canonicalization workflow, directly violating ADR-0004.
