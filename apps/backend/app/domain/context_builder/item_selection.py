"""
Selection: which governed results enter the context, and in what order.

Replaces ``candidate_selection.py`` (EPIC 31.3). The stage's job is
unchanged - rank, then admit up to the budget - but the two things it
ranked *by* are gone:

- **the score.** Legacy selection sorted by ``-candidate.score.total``,
  a weighted sum that read as a measure of how true the knowledge was.
  Governed results carry no such number, and selection now sorts by the
  order retrieval already decided.
- **the re-derivation.** Legacy selection deliberately recomputed the
  ordering from public candidate fields, because the upstream
  ``sort_key`` was not on the wire. A governed item's ``sort_key`` *is*
  its documented ordering (match-strategy precedence, folded labels,
  governed identity), so re-deriving it here would be a second
  definition of the same rule.

---

## The complete ordering rule

```
(match strategy precedence, folded primary label, folded secondary label,
 governed identity)      - GovernedRetrievalItem.sort_key
then item identity       - the final tie-break
```

Total, deterministic, and free of anything that varies between runs: no
clock, no counter, no insertion order, no database sort. Two identical
governed inputs produce the same admitted items in the same sequence.

## Admission

An overall item cap plus a per-kind cap for assets, quantities and
relationships. An item whose own kind has already reached its cap is
skipped **without consuming the overall budget**, so a lower-ranked item
of a still-open kind can still be admitted - one linear scan, no
backtracking.

Selection never merges, never re-ranks and never drops an item for being
a duplicate: deduplication happens on governed identity before this
stage (``deduplicate_items``), and two governed objects that merely
share a label are two items here as everywhere else.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    BudgetPolicy,
    ContextItem,
    DiscardedItem,
    SelectionOutcome,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedResultKind,
)

#: Only these three kinds have a dedicated per-kind budget dimension.
#: Total over ``GovernedResultKind`` - a kind missing here would be
#: governed knowledge with no budget, so a test asserts completeness.
_BUDGET_CATEGORY_FOR_KIND: dict[GovernedResultKind, BudgetCategory] = {
    GovernedResultKind.ASSET: BudgetCategory.ASSETS,
    GovernedResultKind.QUANTITY: BudgetCategory.QUANTITIES,
    GovernedResultKind.RELATIONSHIP: BudgetCategory.RELATIONSHIPS,
}


def _selection_key(item: ContextItem) -> tuple[tuple[int, str, str, str], str]:
    """Retrieval's own order, then governed identity. Nothing else."""

    return (item.order_key, item.item_id)


def deduplicate_items(
    items: tuple[ContextItem, ...],
) -> tuple[ContextItem, ...]:
    """
    Collapses items naming the same governed object, keeping the first.

    Reachable when several governed queries answer with the same object -
    a designation lookup and a quantity traversal both resolving ``TR1``,
    say. Deduplication is **by governed identity** (``item_id``, derived
    from the governed node and edge ids), never by display text: two
    documents that each designate a ``TR1`` produce two governed nodes
    and stay two items, because deciding they are the same transformer
    is cross-document entity resolution and no governed rule performs
    it.
    """

    seen: dict[str, ContextItem] = {}

    for item in items:
        seen.setdefault(item.item_id, item)

    return tuple(seen.values())


def _consumption(
    category: BudgetCategory, *, requested: int, accepted: int, limit: int
) -> BudgetConsumption:
    return BudgetConsumption(
        category=category,
        requested=requested,
        accepted=accepted,
        discarded=requested - accepted,
        limit=limit,
        utilization=0.0 if limit == 0 else accepted / limit,
    )


def select_items(
    items: tuple[ContextItem, ...], budget_policy: BudgetPolicy
) -> SelectionOutcome:
    """
    O(n log n) in ``len(items)`` (the ranking sort); every other step is
    a single O(n) linear pass.
    """

    ranked = sorted(items, key=_selection_key)

    kind_limits: dict[GovernedResultKind, int] = {
        GovernedResultKind.ASSET: budget_policy.max_assets,
        GovernedResultKind.QUANTITY: budget_policy.max_quantities,
        GovernedResultKind.RELATIONSHIP: budget_policy.max_relationships,
    }
    kind_requested: dict[GovernedResultKind, int] = {
        kind: 0 for kind in GovernedResultKind
    }
    kind_accepted: dict[GovernedResultKind, int] = {
        kind: 0 for kind in GovernedResultKind
    }

    selected: list[ContextItem] = []
    discarded: list[DiscardedItem] = []

    for item in ranked:
        kind_requested[item.kind] += 1

        if len(selected) >= budget_policy.max_items:
            discarded.append(
                DiscardedItem(item=item, reason=BudgetCategory.ITEMS)
            )
            continue

        if kind_accepted[item.kind] >= kind_limits[item.kind]:
            discarded.append(
                DiscardedItem(
                    item=item, reason=_BUDGET_CATEGORY_FOR_KIND[item.kind]
                )
            )
            continue

        selected.append(item)
        kind_accepted[item.kind] += 1

    consumption = (
        _consumption(
            BudgetCategory.ITEMS,
            requested=len(ranked),
            accepted=len(selected),
            limit=budget_policy.max_items,
        ),
        _consumption(
            BudgetCategory.ASSETS,
            requested=kind_requested[GovernedResultKind.ASSET],
            accepted=kind_accepted[GovernedResultKind.ASSET],
            limit=budget_policy.max_assets,
        ),
        _consumption(
            BudgetCategory.QUANTITIES,
            requested=kind_requested[GovernedResultKind.QUANTITY],
            accepted=kind_accepted[GovernedResultKind.QUANTITY],
            limit=budget_policy.max_quantities,
        ),
        _consumption(
            BudgetCategory.RELATIONSHIPS,
            requested=kind_requested[GovernedResultKind.RELATIONSHIP],
            accepted=kind_accepted[GovernedResultKind.RELATIONSHIP],
            limit=budget_policy.max_relationships,
        ),
    )

    return SelectionOutcome(
        selected=tuple(selected),
        discarded=tuple(discarded),
        consumption=consumption,
    )
