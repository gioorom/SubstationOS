"""
Aggregation: grouping admitted governed items by kind.

Groups Selection's already-admitted, already-ordered items into
``ContextSection``s by ``GovernedResultKind``, and exposes the same
grouping as the three kind-specific tuples ``ContextPackage`` carries.
Never re-ranks, never discards, never re-orders - a single O(n) pass
that preserves Selection's own order within each kind.

The section set is fixed at three (asset, quantity, relationship)
because that is exactly what the governed vocabulary produces. The
legacy fourth section, ``NEIGHBORHOOD``, is gone: a governed edge *is*
the neighbourhood, so a quantity reached by traversal is reported as the
quantity it is, related to the asset it was asserted about.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    ContextAssemblyResult,
    ContextItem,
    ContextSection,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedResultKind,
)

# Fixed, documented order - every ContextAssemblyResult always carries
# exactly these three sections, even when a section is empty, so a
# caller can rely on a stable shape.
_SECTION_KINDS: tuple[GovernedResultKind, ...] = (
    GovernedResultKind.ASSET,
    GovernedResultKind.QUANTITY,
    GovernedResultKind.RELATIONSHIP,
)


def aggregate(selected: tuple[ContextItem, ...]) -> ContextAssemblyResult:
    by_kind: dict[GovernedResultKind, list[ContextItem]] = {
        kind: [] for kind in _SECTION_KINDS
    }

    for item in selected:
        by_kind[item.kind].append(item)

    sections = tuple(
        ContextSection(
            kind=kind,
            items=tuple(by_kind[kind]),
            item_count=len(by_kind[kind]),
        )
        for kind in _SECTION_KINDS
    )

    return ContextAssemblyResult(
        selected_items=selected,
        sections=sections,
        selected_assets=tuple(by_kind[GovernedResultKind.ASSET]),
        selected_quantities=tuple(by_kind[GovernedResultKind.QUANTITY]),
        selected_relationships=tuple(
            by_kind[GovernedResultKind.RELATIONSHIP]
        ),
    )
