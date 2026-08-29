"""
Selection over governed context items (EPIC 31.3).

Replaces the candidate-selection tests. What is asserted has changed in
one important way: there is no score. Selection ranks by the order
Governed Structured Retrieval already decided - match-strategy
precedence, folded labels, governed identity - and admits up to the
budget.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetPolicy,
    ContextItem,
    ContextItemOrigin,
)
from app.domain.context_builder.item_selection import (
    deduplicate_items,
    select_items,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedQueryType,
    GovernedResultKind,
    RetrievalScope,
)
from tests._governed_context import (
    asset_item,
    quantity_item,
    relationship_item,
)

PROJECT_ID = 1

UNIQUE = ContextItemOrigin(
    query_type=GovernedQueryType.ASSET_BY_DESIGNATION,
    outcome=GovernedMatchOutcome.UNIQUE_MATCH,
    scope=RetrievalScope.CURRENT_ONLY,
    normalized_query="tr1",
    matched_before_limit=1,
)


def _policy(**overrides) -> BudgetPolicy:
    defaults = dict(
        version="2.0",
        max_items=100,
        max_assets=50,
        max_quantities=50,
        max_relationships=50,
        max_metadata_entries=20,
        max_warnings=50,
    )
    defaults.update(overrides)

    return BudgetPolicy(**defaults)


def _asset(designation: str) -> ContextItem:
    return ContextItem(
        result=asset_item(
            f"node-{designation.lower()}",
            designation,
            project_id=PROJECT_ID,
        ),
        origin=UNIQUE,
    )


def _quantity(designation: str) -> ContextItem:
    return ContextItem(
        result=quantity_item(
            subject_node_id=f"node-{designation.lower()}",
            subject_label=designation,
            quantity_node_id=f"node-q-{designation.lower()}",
            quantity_label="630 kVA",
            edge_id=f"edge-{designation.lower()}",
            project_id=PROJECT_ID,
        ),
        origin=UNIQUE,
    )


def _relationship(designation: str) -> ContextItem:
    return ContextItem(
        result=relationship_item(
            subject_node_id=f"node-{designation.lower()}",
            subject_label=designation,
            object_node_id=f"node-q-{designation.lower()}",
            object_label="630 kVA",
            edge_id=f"edge-r-{designation.lower()}",
            project_id=PROJECT_ID,
        ),
        origin=UNIQUE,
    )


# --- Ordering ------------------------------------------------------------


def test_selection_orders_by_the_governed_retrieval_key() -> None:
    items = (_asset("TR3"), _asset("TR1"), _asset("TR2"))

    selected = select_items(items, _policy()).selected

    assert [item.result.node.label for item in selected] == [
        "TR1",
        "TR2",
        "TR3",
    ]


def test_a_stronger_match_strategy_outranks_a_weaker_one() -> None:
    """
    An exact designation outranks one matched only after separators were
    dropped - a fact about the comparison, not a number about the
    knowledge.
    """

    exact = ContextItem(
        result=asset_item(
            "node-b",
            "ZZ1",
            strategy=GovernedMatchStrategy.EXACT_DESIGNATION,
            project_id=PROJECT_ID,
        ),
        origin=UNIQUE,
    )
    canonical = ContextItem(
        result=asset_item(
            "node-a",
            "AA1",
            strategy=GovernedMatchStrategy.CANONICAL_DESIGNATION,
            project_id=PROJECT_ID,
        ),
        origin=UNIQUE,
    )

    selected = select_items((canonical, exact), _policy()).selected

    assert selected[0] is exact
    assert selected[1] is canonical


def test_selection_is_deterministic() -> None:
    items = (_asset("TR2"), _quantity("TR1"), _relationship("TR3"))

    first = select_items(items, _policy()).selected
    second = select_items(tuple(reversed(items)), _policy()).selected

    assert [item.item_id for item in first] == [
        item.item_id for item in second
    ]


def test_no_selection_input_carries_a_score() -> None:
    for item in (_asset("TR1"), _quantity("TR1"), _relationship("TR1")):
        assert not hasattr(item.result, "score")


# --- Budgets -------------------------------------------------------------


def test_the_overall_budget_caps_the_admitted_items() -> None:
    items = tuple(_asset(f"TR{index}") for index in range(5))

    outcome = select_items(items, _policy(max_items=2))

    assert len(outcome.selected) == 2
    assert len(outcome.discarded) == 3
    assert all(
        discarded.reason is BudgetCategory.ITEMS
        for discarded in outcome.discarded
    )


def test_a_per_kind_cap_discards_only_that_kind() -> None:
    items = (_asset("TR1"), _quantity("TR1"), _relationship("TR1"))

    outcome = select_items(items, _policy(max_quantities=0))

    kinds = {item.kind for item in outcome.selected}

    assert GovernedResultKind.QUANTITY not in kinds
    assert kinds == {
        GovernedResultKind.ASSET,
        GovernedResultKind.RELATIONSHIP,
    }
    assert outcome.discarded[0].reason is BudgetCategory.QUANTITIES


def test_a_full_kind_does_not_consume_the_overall_budget() -> None:
    """
    A lower-ranked item of a still-open kind is still admitted - one
    linear scan, no backtracking, and no item is lost to a cap that did
    not apply to it.
    """

    items = (_asset("TR1"), _asset("TR2"), _relationship("TR1"))

    outcome = select_items(items, _policy(max_assets=1))

    assert len(outcome.selected) == 2
    assert {item.kind for item in outcome.selected} == {
        GovernedResultKind.ASSET,
        GovernedResultKind.RELATIONSHIP,
    }


def test_consumption_is_reported_for_every_budget_dimension() -> None:
    outcome = select_items((_asset("TR1"),), _policy())

    assert {entry.category for entry in outcome.consumption} == {
        BudgetCategory.ITEMS,
        BudgetCategory.ASSETS,
        BudgetCategory.QUANTITIES,
        BudgetCategory.RELATIONSHIPS,
    }


# --- Deduplication -------------------------------------------------------


def test_deduplication_keeps_one_of_each_governed_identity() -> None:
    asset = _asset("TR1")

    assert deduplicate_items((asset, asset)) == (asset,)


def test_deduplication_never_merges_two_identities_sharing_a_label() -> None:
    first = ContextItem(
        result=asset_item("node-a", "TR1", project_id=PROJECT_ID),
        origin=UNIQUE,
    )
    second = ContextItem(
        result=asset_item("node-b", "TR1", project_id=PROJECT_ID),
        origin=UNIQUE,
    )

    assert len(deduplicate_items((first, second))) == 2
