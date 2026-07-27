"""
Aggregation (Milestone 14's pipeline stage of the same name). Groups
Selection's already-admitted, already-ordered candidates into
``ContextSection``s by ``KnowledgeCandidateKind``, and exposes the same
grouping as the three kind-specific tuples ``ContextPackage`` itself
carries. Never re-ranks, never discards, never re-scores - a single O(n)
pass that preserves Selection's own order within each kind.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    ContextAssemblyResult,
    ContextSection,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateKind,
)

# Fixed, documented order - every ContextAssemblyResult always carries
# exactly these four sections, even when a section is empty, so a
# caller can rely on a stable shape.
_SECTION_KINDS: tuple[KnowledgeCandidateKind, ...] = (
    KnowledgeCandidateKind.ENTITY,
    KnowledgeCandidateKind.RELATIONSHIP,
    KnowledgeCandidateKind.ATTRIBUTE,
    KnowledgeCandidateKind.NEIGHBORHOOD,
)


def aggregate(
    selected: tuple[KnowledgeCandidate, ...],
) -> ContextAssemblyResult:
    by_kind: dict[KnowledgeCandidateKind, list[KnowledgeCandidate]] = {
        kind: [] for kind in _SECTION_KINDS
    }

    for candidate in selected:
        by_kind[candidate.candidate_kind].append(candidate)

    sections = tuple(
        ContextSection(
            kind=kind,
            candidates=tuple(by_kind[kind]),
            candidate_count=len(by_kind[kind]),
        )
        for kind in _SECTION_KINDS
    )

    return ContextAssemblyResult(
        selected_candidates=selected,
        sections=sections,
        selected_entities=tuple(by_kind[KnowledgeCandidateKind.ENTITY]),
        selected_relationships=tuple(
            by_kind[KnowledgeCandidateKind.RELATIONSHIP]
        ),
        selected_attributes=tuple(by_kind[KnowledgeCandidateKind.ATTRIBUTE]),
    )
