"""
Governed Context Assembly, end to end through the pure domain pipeline
(EPIC 31.3).

These are the **migration validation scenarios** ADR-0027 names: the
behaviours a governed context must have, each asserted on observable
output rather than on how assembly is implemented.

Pure and fast: no I/O, no database, no AI provider. Every input is a real
``GovernedRetrievalResult``, so nothing here can pass against a shape the
production path could not produce.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_factory import (
    ContextBuildRequestFactory,
)
from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    ContextWarningCategory,
    CoverageCategory,
)
from app.domain.context_builder.context_package_assembler import (
    assemble_context_package,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedResultKind,
)
from tests._governed_context import (
    asset_item,
    designation_result,
    quantity_item,
    quantity_result,
    relationship_item,
    results_for,
)

PROJECT_ID = 4
NOW = datetime(2026, 5, 6, 11, 0, 0)


def _package(results, **limits):
    request = ContextBuildRequestFactory.create(
        project_id=PROJECT_ID, results=tuple(results), **limits
    )

    return assemble_context_package(request, now=NOW)


def _tr1() -> tuple:
    """The commonest governed answer: one asset and its rated power."""

    return (
        designation_result(
            "TR1",
            (asset_item("node-tr1", "TR1", project_id=PROJECT_ID),),
            project_id=PROJECT_ID,
        ),
        quantity_result(
            "TR1",
            (
                quantity_item(
                    subject_node_id="node-tr1",
                    subject_label="TR1",
                    quantity_node_id="node-630",
                    quantity_label="630 kVA",
                    project_id=PROJECT_ID,
                ),
            ),
            project_id=PROJECT_ID,
        ),
    )


# --- Unique asset, and its quantity -------------------------------------


def test_a_unique_asset_and_its_quantity_become_a_context() -> None:
    package = _package(_tr1())

    assert len(package.selected_items) == 2
    assert len(package.selected_assets) == 1
    assert len(package.selected_quantities) == 1
    assert package.selected_assets[0].result.node.label == "TR1"
    assert package.selected_quantities[0].result.node.label == "630 kVA"


def test_a_quantity_keeps_the_asset_it_was_asserted_about() -> None:
    """
    "630 kVA" on its own is not an engineering answer.

    The governed relationship travels with the quantity, so nothing
    downstream has to re-derive which transformer it belongs to.
    """

    package = _package(_tr1())
    quantity = package.selected_quantities[0].result

    assert quantity.relationship is not None
    assert quantity.relationship.subject.label == "TR1"
    assert quantity.relationship.kind.value == "has_rated_power"


def test_a_governed_relationship_becomes_a_relationship_item() -> None:
    package = _package(
        results_for(
            (
                relationship_item(
                    subject_node_id="node-tr1",
                    subject_label="TR1",
                    object_node_id="node-630",
                    object_label="630 kVA",
                    project_id=PROJECT_ID,
                ),
            ),
            project_id=PROJECT_ID,
        )
    )

    assert len(package.selected_relationships) == 1
    assert package.selected_relationships[0].kind is (
        GovernedResultKind.RELATIONSHIP
    )


# --- No match is an answer, never an error ------------------------------


def test_a_governed_query_that_matched_nothing_assembles_an_empty_context() -> (
    None
):
    package = _package(
        (designation_result("TR9", (), project_id=PROJECT_ID),)
    )

    assert package.selected_items == ()
    assert package.retrieval_summary.all_no_match
    assert package.retrieval_summary.queries[0].outcome is (
        GovernedMatchOutcome.NO_MATCH
    )


def test_an_empty_context_is_vacuously_complete_not_zero_covered() -> None:
    """Nothing was dropped, because nothing was available - which is a
    different statement from "coverage is zero"."""

    package = _package(
        (designation_result("TR9", (), project_id=PROJECT_ID),)
    )

    assert package.coverage.overall_completeness == 1.0


# --- Provenance is preserved --------------------------------------------


def test_every_item_carries_the_review_that_authorised_it() -> None:
    package = _package(_tr1())

    for item in package.selected_items:
        provenance = item.result.provenance
        assert provenance.statement_key
        assert provenance.review_id > 0
        assert provenance.reviewer_display_name
        assert provenance.document_id > 0
        assert provenance.support_fingerprint


def test_provenance_is_the_governed_one_not_a_recomputation() -> None:
    """Context Assembly copies provenance; it derives no part of it."""

    results = _tr1()
    package = _package(results)

    assembled = {
        item.result.result_id: item.result.provenance
        for item in package.selected_items
    }
    retrieved = {
        item.result_id: item.provenance
        for result in results
        for item in result.items
    }

    assert assembled == retrieved


def test_no_context_warning_claims_missing_provenance() -> None:
    """
    The category does not exist any more, and that is the assertion.

    A governed item cannot be built without provenance, so a warning
    about missing provenance would describe a state the platform can no
    longer reach - and its silence would read as reassurance.
    """

    assert not hasattr(ContextWarningCategory, "MISSING_PROVENANCE")


# --- Ambiguity survives --------------------------------------------------


def test_two_documents_designating_tr1_stay_two_items() -> None:
    """
    Cross-document entity resolution is out of scope, and this is where
    that boundary is visible: two governed nodes that share a label are
    two answers.
    """

    package = _package(
        (
            designation_result(
                "TR1",
                (
                    asset_item(
                        "node-a",
                        "TR1",
                        statement_key="statement-a",
                        document_id=11,
                        project_id=PROJECT_ID,
                    ),
                    asset_item(
                        "node-b",
                        "TR1",
                        statement_key="statement-b",
                        document_id=12,
                        project_id=PROJECT_ID,
                    ),
                ),
                project_id=PROJECT_ID,
            ),
        )
    )

    assert len(package.selected_assets) == 2
    assert {item.result.node.node_id for item in package.selected_assets} == {
        "node-a",
        "node-b",
    }


def test_an_ambiguous_retrieval_is_reported_as_a_warning() -> None:
    package = _package(
        (
            designation_result(
                "TR1",
                (
                    asset_item("node-a", "TR1", project_id=PROJECT_ID),
                    asset_item("node-b", "TR1", project_id=PROJECT_ID),
                ),
                project_id=PROJECT_ID,
            ),
        )
    )

    categories = [warning.category for warning in package.warnings]

    assert ContextWarningCategory.AMBIGUOUS_RETRIEVAL in categories
    assert package.is_ambiguous


def test_ambiguity_is_recorded_on_every_item_it_produced() -> None:
    """Per item, so a consumer that reads one answer still knows the
    question had more than one."""

    package = _package(
        (
            designation_result(
                "TR1",
                (
                    asset_item("node-a", "TR1", project_id=PROJECT_ID),
                    asset_item("node-b", "TR1", project_id=PROJECT_ID),
                ),
                project_id=PROJECT_ID,
            ),
        )
    )

    assert all(item.origin.is_ambiguous for item in package.selected_items)
    assert all(
        item.origin.matched_before_limit == 2
        for item in package.selected_items
    )


def test_a_unique_query_beside_an_ambiguous_one_stays_unique() -> None:
    """A context is not "somewhat ambiguous": each query keeps its own
    outcome."""

    package = _package(
        (
            designation_result(
                "TR1",
                (
                    asset_item("node-a", "TR1", project_id=PROJECT_ID),
                    asset_item("node-b", "TR1", project_id=PROJECT_ID),
                ),
                project_id=PROJECT_ID,
            ),
            designation_result(
                "Q1",
                (asset_item("node-q1", "Q1", project_id=PROJECT_ID),),
                project_id=PROJECT_ID,
            ),
        )
    )

    outcomes = {
        query.normalized_query: query.outcome
        for query in package.retrieval_summary.queries
    }

    assert outcomes["tr1"] is GovernedMatchOutcome.MULTIPLE_MATCHES
    assert outcomes["q1"] is GovernedMatchOutcome.UNIQUE_MATCH


# --- Ordering ------------------------------------------------------------


def test_items_are_ordered_by_the_governed_retrieval_key() -> None:
    package = _package(_tr1())
    keys = [item.order_key for item in package.selected_items]

    assert keys == sorted(keys)


def test_ordering_is_deterministic_across_input_permutations() -> None:
    """
    The order is a function of the governed data, not of the order a
    caller happened to execute queries in.
    """

    first, second = _tr1()

    forwards = _package((first, second))
    backwards = _package((second, first))

    assert [item.item_id for item in forwards.selected_items] == [
        item.item_id for item in backwards.selected_items
    ]


def test_assembly_is_deterministic() -> None:
    results = _tr1()

    assert _package(results) == _package(results)


def test_no_item_carries_a_score() -> None:
    """
    EPIC 31.2 removed relevance scores from retrieval; 31.3 removes the
    last score-shaped ordering value from the context path. An item is
    ordered by *how* it matched, which is a fact about the comparison
    rather than a number about the knowledge.
    """

    package = _package(_tr1())

    for item in package.selected_items:
        assert not hasattr(item, "score")
        assert not hasattr(item.result, "score")
        assert isinstance(item.order_key[0], int)


# --- Deduplication -------------------------------------------------------


def test_the_same_governed_object_answering_twice_appears_once() -> None:
    asset = asset_item("node-tr1", "TR1", project_id=PROJECT_ID)

    package = _package(
        (
            designation_result("TR1", (asset,), project_id=PROJECT_ID),
            designation_result("tr1", (asset,), project_id=PROJECT_ID),
        )
    )

    assert len(package.selected_items) == 1


def test_deduplication_is_by_governed_identity_never_by_label() -> None:
    package = _package(
        (
            designation_result(
                "TR1",
                (
                    asset_item("node-a", "TR1", project_id=PROJECT_ID),
                    asset_item("node-b", "TR1", project_id=PROJECT_ID),
                ),
                project_id=PROJECT_ID,
            ),
        )
    )

    assert len(package.selected_items) == 2


# --- Truncation ----------------------------------------------------------


def test_truncation_reports_what_was_dropped() -> None:
    items = tuple(
        asset_item(f"node-{index}", f"TR{index}", project_id=PROJECT_ID)
        for index in range(5)
    )
    package = _package(results_for(items, project_id=PROJECT_ID), max_items=2)

    assert len(package.selected_items) == 2
    assert package.budget.exceeded
    assert package.statistics.discarded_item_count == 3
    assert ContextWarningCategory.ITEM_DISCARDED in {
        warning.category for warning in package.warnings
    }


def test_truncation_never_hides_how_many_governed_objects_matched() -> None:
    """
    Five matched, two are in the context, and the package says both
    numbers. A consumer that only saw the second could not tell a
    complete answer from a truncated one.
    """

    items = tuple(
        asset_item(f"node-{index}", f"TR{index}", project_id=PROJECT_ID)
        for index in range(5)
    )
    package = _package(results_for(items, project_id=PROJECT_ID), max_items=2)

    assert package.retrieval_summary.total_before_limit == 5
    assert package.retrieval_summary.retrieved_item_count == 5
    assert package.statistics.selected_item_count == 2


def test_a_per_kind_budget_discards_only_that_kind() -> None:
    package = _package(_tr1(), max_quantities=0)

    assert len(package.selected_assets) == 1
    assert package.selected_quantities == ()
    assert any(
        entry.category is BudgetCategory.QUANTITIES and entry.discarded == 1
        for entry in package.budget.consumption
    )


def test_a_kind_retrieved_but_never_selected_is_warned_about() -> None:
    package = _package(_tr1(), max_quantities=0)

    assert ContextWarningCategory.MISSING_QUANTITIES in {
        warning.category for warning in package.warnings
    }


# --- Coverage and metadata ----------------------------------------------


def test_coverage_reports_every_governed_kind() -> None:
    package = _package(_tr1())
    categories = {metric.category for metric in package.coverage.metrics}

    assert categories == {
        CoverageCategory.ASSET_COVERAGE,
        CoverageCategory.QUANTITY_COVERAGE,
        CoverageCategory.RELATIONSHIP_COVERAGE,
        CoverageCategory.ITEM_UTILIZATION,
        CoverageCategory.CONTEXT_COMPLETENESS,
    }


def test_metadata_echoes_the_retrieval_versions_rather_than_restating_them() -> (
    None
):
    package = _package(_tr1())

    assert package.metadata.retrieval_normalization_version == "1.0"
    assert package.metadata.retrieval_matching_policy_version == "1.0"
    assert package.metadata.graph_generation_number == 3
    assert package.metadata.context_assembly_version == "2.0"


def test_metadata_reports_no_version_when_there_was_no_retrieval() -> None:
    package = _package(())

    assert package.metadata.retrieval_normalization_version is None
    assert package.metadata.graph_generation_number is None


def test_assembled_at_is_the_supplied_clock_never_a_wall_clock_read() -> None:
    package = _package(_tr1())

    assert package.metadata.assembled_at == NOW
