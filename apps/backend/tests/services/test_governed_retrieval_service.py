"""
Service tests for Governed Structured Retrieval (EPIC 31.2).

Driven through an in-memory ``GovernedKnowledgeReader``, so every test
here is about *retrieval* rather than about persistence. The database
adapter has its own test
(``tests/infrastructure/test_sqlalchemy_governed_knowledge_reader.py``),
and the governance rules are proven end to end against real promotions
in ``tests/api/test_governed_retrieval_baseline.py``.

Four properties these tests exist to hold:

1. **Determinism.** The same governed knowledge and the same query
   always produce the same items, in the same order, with the same
   identities.
2. **Ambiguity is never hidden.** Two governed assets sharing a label
   are two answers, and the outcome says so.
3. **Historical knowledge never answers a current question** unless a
   caller asked for it in as many words.
4. **Provenance is on everything.** No result reaches a caller that
   cannot be followed back to the review that authorised it.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
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
from app.services import governed_retrieval_service
from tests._governed_graph_builder import (
    governed_asset,
    governed_asset_with_quantity,
)

NOW = datetime(2026, 3, 1, 9, 0, 0)


class InMemoryGovernedKnowledgeReader:
    """
    A governed graph held in memory, ordered by governed identity - the
    same ordering guarantee the port requires of every implementation.
    """

    def __init__(self, nodes=(), edges=()) -> None:
        self._nodes = {node.node_id.value: node for node in nodes}
        self._edges = {edge.edge_id.value: edge for edge in edges}
        self.reads = 0

    # --- Identity --------------------------------------------------------

    def find_node(self, node_id):
        self.reads += 1
        return self._nodes.get(node_id)

    def find_edge(self, edge_id):
        self.reads += 1
        return self._edges.get(edge_id)

    def nodes_by_identity(self, node_ids):
        wanted = set(node_ids)

        return tuple(
            node
            for node in self._sorted_nodes()
            if node.node_id.value in wanted
        )

    # --- Scoped reads ----------------------------------------------------

    def nodes(self, *, states, kind=None, project_id=None, document_id=None):
        self.reads += 1

        return tuple(
            node
            for node in self._sorted_nodes()
            if node.state in states
            and (kind is None or node.kind is kind)
            and (
                project_id is None
                or node.provenance.project_id == project_id
            )
            and (
                document_id is None
                or node.provenance.document_id == document_id
            )
        )

    def edges(self, *, states, kind=None, project_id=None, document_id=None):
        self.reads += 1

        return tuple(
            edge
            for edge in self._sorted_edges()
            if edge.state in states
            and (kind is None or edge.kind is kind)
            and (
                project_id is None
                or edge.provenance.project_id == project_id
            )
            and (
                document_id is None
                or edge.provenance.document_id == document_id
            )
        )

    def edges_from_subjects(self, subject_node_ids, *, states, kind=None):
        self.reads += 1
        wanted = set(subject_node_ids)

        return tuple(
            edge
            for edge in self._sorted_edges()
            if edge.subject_node_id in wanted
            and edge.state in states
            and (kind is None or edge.kind is kind)
        )

    def latest_generation(self):
        return None

    # --- Ordering --------------------------------------------------------

    def _sorted_nodes(self):
        return sorted(
            self._nodes.values(), key=lambda node: node.node_id.value
        )

    def _sorted_edges(self):
        return sorted(
            self._edges.values(), key=lambda edge: edge.edge_id.value
        )


def _reader_with(*designations: str, project_id: int = 1):
    nodes = []
    edges = []

    for index, designation in enumerate(designations, start=1):
        asset, quantity, edge = governed_asset_with_quantity(
            designation=designation,
            document_id=index,
            project_id=project_id,
        )
        nodes.extend((asset, quantity))
        edges.append(edge)

    return InMemoryGovernedKnowledgeReader(nodes=nodes, edges=edges)


def _retrieve(reader, query):
    return governed_retrieval_service.retrieve(reader, query, now=NOW)


# --- Retrieving an asset by designation -----------------------------------


def test_a_designation_resolves_to_its_governed_asset() -> None:
    reader = _reader_with("TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(designation="TR1"),
    )

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert len(result.items) == 1
    assert result.items[0].node.label == "TR1"
    assert result.items[0].kind is GovernedResultKind.ASSET
    assert result.items[0].match.strategy is (
        GovernedMatchStrategy.EXACT_DESIGNATION
    )


def test_a_designation_nothing_designates_is_a_successful_no_match() -> None:
    """Not a 404 and not an exception: "the governed graph holds nothing
    about this" is an engineering answer, and one an engineer must be
    able to read."""

    result = _retrieve(
        _reader_with("TR1"),
        GovernedRetrievalQueryFactory.asset_by_designation(designation="TR9"),
    )

    assert result.outcome is GovernedMatchOutcome.NO_MATCH
    assert result.items == ()
    assert result.diagnostics.no_match is True


def test_only_assets_answer_a_designation_query() -> None:
    """A quantity is not designated by anything, so a designation query
    never returns one even when its label happens to match."""

    reader = _reader_with("630 kVA")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="630 kVA"
        ),
    )

    assert all(
        item.kind is GovernedResultKind.ASSET for item in result.items
    )


# --- Ambiguity, and cross-document identity -------------------------------


def test_two_documents_designating_the_same_thing_are_two_answers() -> None:
    """**The cross-document boundary.** Deciding that TR1 in drawing A
    and TR1 in drawing B are the same transformer is entity resolution
    across documents, which no governed rule performs - so retrieval
    reports two governed assets and says the answer is ambiguous."""

    reader = _reader_with("TR1", "TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(designation="TR1"),
    )

    assert result.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
    assert result.total_before_limit == 2
    assert len({item.node.node_id for item in result.items}) == 2
    assert result.diagnostics.ambiguous is True


def test_a_limit_never_turns_several_answers_into_one() -> None:
    reader = _reader_with("TR1", "TR1", "TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1", limit=1
        ),
    )

    assert len(result.items) == 1
    assert result.total_before_limit == 3
    assert result.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES


# --- Quantities ------------------------------------------------------------


def test_a_quantity_query_follows_the_governed_relationship() -> None:
    reader = _reader_with("TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.quantity_for_asset(designation="TR1"),
    )

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    item = result.items[0]
    assert item.kind is GovernedResultKind.QUANTITY
    assert item.node.label == "630 kVA"
    assert item.node.unit == "kVA"
    assert item.relationship.subject.label == "TR1"
    assert item.relationship.kind is GraphEdgeKind.HAS_RATED_POWER
    assert item.match.strategy is (
        GovernedMatchStrategy.RELATIONSHIP_TRAVERSAL
    )


def test_an_ambiguous_asset_traverses_every_resolved_subject() -> None:
    """Answering with one of two TR1s would be the silent merge the
    identity model exists to refuse."""

    reader = _reader_with("TR1", "TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.quantity_for_asset(designation="TR1"),
    )

    assert result.total_before_limit == 2
    assert result.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES


def test_a_quantity_query_for_an_unknown_asset_matches_nothing() -> None:
    result = _retrieve(
        _reader_with("TR1"),
        GovernedRetrievalQueryFactory.quantity_for_asset(designation="TR9"),
    )

    assert result.outcome is GovernedMatchOutcome.NO_MATCH


def test_a_quantity_query_never_answers_from_a_quantity_node() -> None:
    """``has_rated_power`` relates an asset to a quantity in one
    direction; answering the reverse would invert an engineering
    statement."""

    reader = _reader_with("TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.quantity_for_asset(
            designation="630 kVA"
        ),
    )

    assert result.outcome is GovernedMatchOutcome.NO_MATCH


# --- Relationships and document scope -------------------------------------


def test_relationships_are_retrievable_by_kind() -> None:
    reader = _reader_with("TR1", "TR2")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.relationships(
            edge_kind=GraphEdgeKind.HAS_RATED_POWER
        ),
    )

    assert len(result.items) == 2
    assert all(
        item.kind is GovernedResultKind.RELATIONSHIP for item in result.items
    )
    assert all(
        item.match.strategy is GovernedMatchStrategy.EDGE_KIND
        for item in result.items
    )


def test_document_knowledge_returns_the_nodes_and_the_relationships() -> None:
    reader = _reader_with("TR1", "TR2")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.document_knowledge(document_id=1),
    )

    kinds = {item.kind for item in result.items}
    assert GovernedResultKind.ASSET in kinds
    assert GovernedResultKind.RELATIONSHIP in kinds
    assert all(
        item.provenance.document_id == 1 for item in result.items
    )


def test_a_project_scope_excludes_another_project_s_knowledge() -> None:
    reader = InMemoryGovernedKnowledgeReader(
        nodes=(
            governed_asset(designation="TR1", document_id=1, project_id=1),
            governed_asset(designation="TR1", document_id=2, project_id=2),
        )
    )

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1", project_id=2
        ),
    )

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert result.items[0].provenance.project_id == 2


# --- Historical knowledge --------------------------------------------------


def test_historical_knowledge_never_answers_a_current_question() -> None:
    reader = InMemoryGovernedKnowledgeReader(
        nodes=(
            governed_asset(
                designation="TR1",
                state=GraphObjectState.HISTORICAL,
                retirement_reason=GraphRetirementReason.REVIEW_REVERSED,
            ),
        )
    )

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(designation="TR1"),
    )

    assert result.outcome is GovernedMatchOutcome.NO_MATCH


def test_historical_knowledge_is_readable_when_asked_for_explicitly() -> None:
    reader = InMemoryGovernedKnowledgeReader(
        nodes=(
            governed_asset(
                designation="TR1",
                state=GraphObjectState.HISTORICAL,
                retirement_reason=GraphRetirementReason.REVIEW_REVERSED,
            ),
        )
    )

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1",
            scope=RetrievalScope.CURRENT_AND_HISTORICAL,
        ),
    )

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert result.items[0].state is GraphObjectState.HISTORICAL
    assert result.items[0].retirement_reason is (
        GraphRetirementReason.REVIEW_REVERSED
    )


def test_a_removed_object_answers_no_scope() -> None:
    """``REMOVED`` is a tombstone - nothing produces this knowledge any
    more - and no retrieval scope admits it."""

    reader = InMemoryGovernedKnowledgeReader(
        nodes=(
            governed_asset(
                designation="TR1", state=GraphObjectState.REMOVED
            ),
        )
    )

    for scope in RetrievalScope:
        result = _retrieve(
            reader,
            GovernedRetrievalQueryFactory.asset_by_designation(
                designation="TR1", scope=scope
            ),
        )

        assert result.outcome is GovernedMatchOutcome.NO_MATCH, scope


# --- Identity and provenance ----------------------------------------------


def test_a_governed_object_is_retrievable_by_its_identity() -> None:
    reader = _reader_with("TR1")
    asset = reader.nodes(states=(GraphObjectState.ACTIVE,))[0]

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.governed_identity(
            node_id=asset.node_id.value
        ),
    )

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert result.items[0].match.strategy is (
        GovernedMatchStrategy.GOVERNED_IDENTITY
    )


def test_every_returned_item_carries_a_complete_provenance() -> None:
    reader = _reader_with("TR1", "TR2")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.relationships(),
    )

    assert result.items

    for item in result.items:
        provenance = item.provenance
        assert provenance.statement_key
        assert provenance.document_id > 0
        assert provenance.review_id > 0
        assert provenance.reviewer_display_name
        assert provenance.semantic_rule_id
        assert provenance.semantic_rule_version
        assert provenance.support_fingerprint
        assert provenance.content_checksum


# --- Determinism -----------------------------------------------------------


@pytest.mark.parametrize(
    "query_factory",
    [
        lambda: GovernedRetrievalQueryFactory.asset_by_designation(
            designation="TR1"
        ),
        lambda: GovernedRetrievalQueryFactory.quantity_for_asset(
            designation="TR1"
        ),
        lambda: GovernedRetrievalQueryFactory.relationships(),
        lambda: GovernedRetrievalQueryFactory.document_knowledge(
            document_id=1
        ),
    ],
)
def test_the_same_query_over_the_same_knowledge_answers_identically(
    query_factory,
) -> None:
    reader = _reader_with("TR1", "TR1", "TR2")

    first = _retrieve(reader, query_factory())
    second = _retrieve(reader, query_factory())

    assert [item.result_id for item in first.items] == [
        item.result_id for item in second.items
    ]
    assert [item.match for item in first.items] == [
        item.match for item in second.items
    ]
    assert [item.provenance for item in first.items] == [
        item.provenance for item in second.items
    ]
    assert first.outcome is second.outcome
    assert first.total_before_limit == second.total_before_limit


def test_duration_is_the_only_field_that_may_differ_between_runs() -> None:
    """Stated as a test so nobody later adds a clock-derived field to a
    result and breaks reproducibility silently."""

    reader = _reader_with("TR1")
    query = GovernedRetrievalQueryFactory.asset_by_designation(
        designation="TR1"
    )

    first = _retrieve(reader, query)
    second = _retrieve(reader, query)

    from dataclasses import replace

    assert replace(
        first.diagnostics, duration_seconds=None
    ) == replace(second.diagnostics, duration_seconds=None)


# --- Diagnostics -----------------------------------------------------------


def test_diagnostics_report_the_fold_and_the_strategies_attempted() -> None:
    reader = _reader_with("TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(designation="tr1"),
    )

    diagnostics = result.diagnostics
    assert diagnostics.normalized_query == "tr1"
    assert GovernedMatchStrategy.EXACT_DESIGNATION in (
        diagnostics.strategies_attempted
    )
    assert diagnostics.candidates_examined >= 1
    assert diagnostics.matched_count == 1
    assert diagnostics.returned_count == 1
    assert diagnostics.normalization_version
    assert diagnostics.matching_policy_version


def test_the_explanation_view_names_one_strategy_per_result() -> None:
    reader = _reader_with("TR1", "TR1")

    result = _retrieve(
        reader,
        GovernedRetrievalQueryFactory.asset_by_designation(designation="TR1"),
    )

    explanation = governed_retrieval_service.explain(result)

    assert set(explanation) == {item.result_id for item in result.items}
    assert set(explanation.values()) == {"exact_designation"}
