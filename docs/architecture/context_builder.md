# Context Builder

> **Superseded by [governed_context_assembly.md](governed_context_assembly.md).**

Context Builder was introduced by Milestone 14
([ADR-0011](adr/0011-context-builder-foundation.md)) as the stage that
turned Structured Retrieval's `KnowledgeCandidateCollection` into a
bounded, provenance-aware `ContextPackage`.

**EPIC 31.3 migrated it onto governed knowledge.** The bounded
responsibility is unchanged - organize retrieved knowledge into a
bounded, explainable artefact - but its input is now
`tuple[GovernedRetrievalResult, ...]`, and with that change three things
that this document described are gone:

| Was | Is |
|---|---|
| `KnowledgeCandidate` items | `ContextItem`, wrapping a `GovernedRetrievalItem` |
| ordering by `score.total` | ordering by governed match-strategy precedence |
| `MISSING_PROVENANCE` warnings | provenance that cannot be absent, and `AMBIGUOUS_RETRIEVAL` warnings |

`POST /projects/{id}/context-builder/build` was **withdrawn** in the same
milestone: a governed `ContextPackage` cannot honestly be assembled from
a request body, because provenance a caller asserts is not provenance.

For the as-built reference - the context model, provenance, ambiguity,
ordering, deduplication, truncation, versioning and the API decision -
see [governed_context_assembly.md](governed_context_assembly.md) and
[ADR-0027](adr/0027-governed-context-assembly.md).

ADR-0011 remains accepted: its decisions about *bounding* context and
*reporting* what was dropped are the ones this context still follows.
