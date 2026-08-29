"""
Domain tests for Governed Structured Retrieval (EPIC 31.2).

Pure and fast: no database, no network, no provider, no clock. Every
test names a behaviour an engineer would recognise - what matches, why
it matched, and in what order the answers come back.
"""

from __future__ import annotations

import pytest

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval import (
    governed_matching,
    governed_normalization,
    governed_result_assembly,
)
from app.domain.governed_retrieval.governed_match_policy import (
    DESIGNATION_STRATEGY_ORDER,
    STRATEGY_PRECEDENCE,
    precedence_of,
)
from app.domain.governed_retrieval.governed_retrieval_exceptions import (
    AmbiguousGovernedIdentityError,
    BlankDesignationError,
    BlankGovernedIdentityError,
    DesignationTooLongError,
    InvalidDocumentScopeError,
    InvalidProjectScopeError,
    InvalidResultLimitError,
    UnresolvableAssetSubjectError,
)
from app.domain.governed_retrieval.governed_retrieval_factory import (
    GovernedRetrievalQueryFactory,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedResultKind,
    RetrievalScope,
)
from tests._governed_graph_builder import (
    governed_asset,
    governed_asset_with_quantity,
)

# --- Normalization ---------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("TR1", "tr1"),
        ("  TR1  ", "tr1"),
        ("TR   1", "tr 1"),
        ("C-295", "c-295"),
    ],
)
def test_normalizing_a_designation_folds_case_and_whitespace(
    written: str, expected: str
) -> None:
    assert governed_normalization.normalize_designation(written) == expected


@pytest.mark.parametrize(
    "written", ["C-295", "c 295", "C295", " c-295 ", "C_295"]
)
def test_the_canonical_key_ignores_every_separator(written: str) -> None:
    """The capability the legacy ``normalize_identifier`` provided,
    preserved verbatim so the migration loses no matching an engineer
    relied on."""

    assert (
        governed_normalization.canonical_designation_key(written) == "c295"
    )


def test_the_canonical_key_does_not_make_two_designations_equal() -> None:
    """The fold is deliberately weak enough to survive typography and no
    weaker: ``TR1`` and ``TR2`` remain two different machines."""

    assert governed_normalization.canonical_designation_key(
        "TR1"
    ) != governed_normalization.canonical_designation_key("TR2")


# --- Matching --------------------------------------------------------------


def test_an_exact_label_match_is_reported_as_exact() -> None:
    node = governed_asset(designation="TR1")

    match = governed_matching.match_designation(node, "TR1")

    assert match.strategy is GovernedMatchStrategy.EXACT_DESIGNATION
    assert match.matched_field == "label"
    assert match.matched_value == "TR1"


def test_a_case_difference_is_reported_as_a_normalized_match() -> None:
    node = governed_asset(designation="TR1")

    match = governed_matching.match_designation(node, "tr1")

    assert match.strategy is GovernedMatchStrategy.NORMALIZED_DESIGNATION
    assert match.normalized_query == "tr1"


def test_a_separator_difference_is_reported_as_a_canonical_match() -> None:
    node = governed_asset(designation="C-295")

    match = governed_matching.match_designation(node, "C295")

    assert match.strategy is GovernedMatchStrategy.CANONICAL_DESIGNATION
    assert match.normalized_query == "c295"


def test_a_node_matches_under_exactly_one_strategy() -> None:
    """An exact match also satisfies every weaker fold, and is reported
    under the strongest one only - "why did this match?" has one answer,
    and it is the most specific true one."""

    node = governed_asset(designation="TR1")

    match = governed_matching.match_designation(node, "TR1")

    assert match.strategy is GovernedMatchStrategy.EXACT_DESIGNATION


def test_an_unrelated_designation_does_not_match() -> None:
    node = governed_asset(designation="TR1")

    assert governed_matching.match_designation(node, "TR2") is None


def test_matching_is_not_a_substring_search() -> None:
    """A designation contained inside another is a coincidence, not an
    identification - and a retrieval that treated it as one would answer
    about the wrong equipment."""

    node = governed_asset(designation="QT10")

    assert governed_matching.match_designation(node, "T1") is None


def test_the_pipeline_normalized_value_can_carry_the_match() -> None:
    node = governed_asset(designation="TR1")

    match = governed_matching.match_designation(node, "tr1")

    assert match is not None
    # The label fold wins over the normalized-value fold, both being
    # true - the label is what the drawing shows.
    assert match.matched_field == "label"


# --- Match policy ----------------------------------------------------------


def test_every_match_strategy_has_a_documented_rank() -> None:
    """A strategy with no rank would be a result nobody could order."""

    assert set(STRATEGY_PRECEDENCE) == set(GovernedMatchStrategy)


def test_the_designation_strategies_are_tried_strongest_first() -> None:
    ranks = [precedence_of(strategy) for strategy in DESIGNATION_STRATEGY_ORDER]

    assert ranks == sorted(ranks)


def test_governed_identity_outranks_every_textual_strategy() -> None:
    identity_rank = precedence_of(GovernedMatchStrategy.GOVERNED_IDENTITY)

    assert all(
        identity_rank < precedence_of(strategy)
        for strategy in GovernedMatchStrategy
        if strategy is not GovernedMatchStrategy.GOVERNED_IDENTITY
    )


# --- Result assembly -------------------------------------------------------


def test_every_governed_node_kind_can_be_reported() -> None:
    """A node kind retrieval could not report would be governed
    knowledge that silently never answers."""

    assert set(
        governed_result_assembly.RESULT_KIND_FOR_NODE_KIND
    ) == set(GraphNodeKind)


def test_a_result_identity_is_derived_from_governed_identity() -> None:
    node = governed_asset(designation="TR1")

    item = governed_result_assembly.node_item(
        node, governed_matching.match_designation(node, "TR1")
    )

    assert item.result_id == f"asset:{node.node_id.value}"


def test_the_same_node_always_produces_the_same_result_identity() -> None:
    node = governed_asset(designation="TR1")
    match = governed_matching.match_designation(node, "TR1")

    first = governed_result_assembly.node_item(node, match)
    second = governed_result_assembly.node_item(node, match)

    assert first.result_id == second.result_id
    assert first.sort_key == second.sort_key


def test_a_quantity_reached_by_two_relationships_is_two_results() -> None:
    """The same 630 kVA node can be the rated power of two transformers,
    and those are two engineering answers rather than one."""

    left_asset, quantity, left_edge = governed_asset_with_quantity(
        designation="TR1", document_id=1
    )
    right_asset, _, right_edge = governed_asset_with_quantity(
        designation="TR2", document_id=2
    )

    left = governed_result_assembly.traversed_node_item(
        quantity,
        left_edge,
        left_asset,
        governed_matching.traversal_match(
            left_edge.edge_id.value, left_edge.kind.value
        ),
    )
    right = governed_result_assembly.traversed_node_item(
        quantity,
        right_edge,
        right_asset,
        governed_matching.traversal_match(
            right_edge.edge_id.value, right_edge.kind.value
        ),
    )

    assert left.result_id != right.result_id


def test_a_result_always_carries_its_provenance() -> None:
    node = governed_asset(designation="TR1", document_id=42)

    item = governed_result_assembly.node_item(
        node, governed_matching.match_designation(node, "TR1")
    )

    assert item.provenance.document_id == 42
    assert item.provenance.review_id > 0
    assert item.provenance.statement_key
    assert item.provenance.support_fingerprint


def test_ordering_puts_the_stronger_strategy_first() -> None:
    exact = governed_asset(designation="C-295", document_id=1)
    folded = governed_asset(designation="c 295", document_id=2)

    items = governed_result_assembly.order(
        (
            governed_result_assembly.node_item(
                folded, governed_matching.match_designation(folded, "C-295")
            ),
            governed_result_assembly.node_item(
                exact, governed_matching.match_designation(exact, "C-295")
            ),
        )
    )

    assert [item.match.strategy for item in items] == [
        GovernedMatchStrategy.EXACT_DESIGNATION,
        GovernedMatchStrategy.CANONICAL_DESIGNATION,
    ]


def test_ordering_is_total_and_never_depends_on_input_order() -> None:
    nodes = [
        governed_asset(designation="TR1", document_id=index)
        for index in range(1, 6)
    ]
    items = tuple(
        governed_result_assembly.node_item(
            node, governed_matching.match_designation(node, "TR1")
        )
        for node in nodes
    )

    forwards = governed_result_assembly.order(items)
    backwards = governed_result_assembly.order(tuple(reversed(items)))

    assert [item.result_id for item in forwards] == [
        item.result_id for item in backwards
    ]


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (0, GovernedMatchOutcome.NO_MATCH),
        (1, GovernedMatchOutcome.UNIQUE_MATCH),
        (2, GovernedMatchOutcome.MULTIPLE_MATCHES),
        (9, GovernedMatchOutcome.MULTIPLE_MATCHES),
    ],
)
def test_the_outcome_reports_how_many_governed_objects_matched(
    total: int, expected: GovernedMatchOutcome
) -> None:
    assert governed_result_assembly.classify(total) is expected


def test_deduplication_is_by_governed_identity_never_by_label() -> None:
    first = governed_asset(designation="TR1", document_id=1)
    second = governed_asset(designation="TR1", document_id=2)

    items = governed_result_assembly.deduplicate(
        (
            governed_result_assembly.node_item(
                first, governed_matching.match_designation(first, "TR1")
            ),
            governed_result_assembly.node_item(
                second, governed_matching.match_designation(second, "TR1")
            ),
        )
    )

    assert len(items) == 2


def test_a_historical_node_reports_its_state_and_reason() -> None:
    from app.domain.governed_knowledge_graph.graph_lifecycle import (
        GraphRetirementReason,
    )

    node = governed_asset(
        designation="TR1",
        state=GraphObjectState.HISTORICAL,
        retirement_reason=GraphRetirementReason.REVIEW_REVERSED,
    )

    item = governed_result_assembly.node_item(
        node, governed_matching.match_designation(node, "TR1")
    )

    assert item.state is GraphObjectState.HISTORICAL
    assert item.retirement_reason is GraphRetirementReason.REVIEW_REVERSED
    assert item.is_current is False


def test_a_relationship_result_resolves_both_endpoints() -> None:
    asset, quantity, edge = governed_asset_with_quantity(designation="TR1")

    item = governed_result_assembly.relationship_item(
        edge,
        asset,
        quantity,
        governed_matching.edge_kind_match(edge.kind.value),
    )

    assert item.kind is GovernedResultKind.RELATIONSHIP
    assert item.relationship.subject.label == "TR1"
    assert item.relationship.object.unit == "kVA"
    assert item.relationship.kind is GraphEdgeKind.HAS_RATED_POWER


# --- Query construction ----------------------------------------------------


def test_a_designation_query_defaults_to_current_knowledge() -> None:
    query = GovernedRetrievalQueryFactory.asset_by_designation(
        designation="TR1"
    )

    assert query.scope is RetrievalScope.CURRENT_ONLY


def test_a_blank_designation_is_refused() -> None:
    with pytest.raises(BlankDesignationError):
        GovernedRetrievalQueryFactory.asset_by_designation(designation="   ")


def test_an_overlong_designation_is_refused() -> None:
    with pytest.raises(DesignationTooLongError):
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="T" * 500
        )


@pytest.mark.parametrize("limit", [0, -1, 201, 10_000])
def test_an_out_of_range_limit_is_refused(limit: int) -> None:
    with pytest.raises(InvalidResultLimitError):
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1", limit=limit
        )


def test_a_non_positive_project_scope_is_refused() -> None:
    with pytest.raises(InvalidProjectScopeError):
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1", project_id=0
        )


def test_a_non_positive_document_scope_is_refused() -> None:
    with pytest.raises(InvalidDocumentScopeError):
        GovernedRetrievalQueryFactory.document_knowledge(document_id=0)


def test_a_quantity_query_names_its_asset_exactly_one_way() -> None:
    with pytest.raises(UnresolvableAssetSubjectError):
        GovernedRetrievalQueryFactory.quantity_for_asset()

    with pytest.raises(UnresolvableAssetSubjectError):
        GovernedRetrievalQueryFactory.quantity_for_asset(
            designation="TR1", subject_node_id="abc"
        )


def test_an_identity_query_names_exactly_one_governed_object() -> None:
    with pytest.raises(BlankGovernedIdentityError):
        GovernedRetrievalQueryFactory.governed_identity()

    with pytest.raises(AmbiguousGovernedIdentityError):
        GovernedRetrievalQueryFactory.governed_identity(
            node_id="a", edge_id="b"
        )


def test_an_identity_query_reads_historical_knowledge_by_default() -> None:
    """A caller who names an id already knows the object exists;
    answering "no such object" for one that is merely retired would be a
    lie about the graph's contents."""

    query = GovernedRetrievalQueryFactory.governed_identity(node_id="abc")

    assert query.scope is RetrievalScope.CURRENT_AND_HISTORICAL
