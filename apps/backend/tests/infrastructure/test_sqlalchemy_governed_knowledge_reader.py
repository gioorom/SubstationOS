"""
Adapter tests for ``SqlAlchemyGovernedKnowledgeReader`` (EPIC 31.2).

Against a real database session, because what these prove is exactly
what an in-memory fake cannot: that the SQL filters are the ones the
port promises, and that every read comes back in a deterministic order
whatever the planner decided.

The rows are written through the governed graph's own repository - the
one promotion uses - so no test here can assert on a graph shape that a
promotion could never produce.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.infrastructure.governed_knowledge_graph.sqlalchemy_governed_graph_repository import (  # noqa: E501
    SqlAlchemyGovernedGraphRepository,
)
from app.infrastructure.governed_retrieval.sqlalchemy_governed_knowledge_reader import (  # noqa: E501
    SqlAlchemyGovernedKnowledgeReader,
)
from tests._governed_graph_builder import (
    governed_asset,
    governed_asset_with_quantity,
)

CURRENT = (GraphObjectState.ACTIVE,)
CURRENT_AND_HISTORICAL = (
    GraphObjectState.ACTIVE,
    GraphObjectState.HISTORICAL,
)


@pytest.fixture()
def reader(db_session: Session) -> SqlAlchemyGovernedKnowledgeReader:
    return SqlAlchemyGovernedKnowledgeReader(db_session)


@pytest.fixture()
def populated(db_session: Session) -> tuple:
    """Two documents, each designating a `TR1` - the cross-document case
    the identity model deliberately keeps apart."""

    repository = SqlAlchemyGovernedGraphRepository(db_session)
    written = []

    for document_id in (1, 2):
        asset, quantity, edge = governed_asset_with_quantity(
            designation="TR1", document_id=document_id, project_id=document_id
        )
        repository.upsert_node(asset)
        repository.upsert_node(quantity)
        repository.upsert_edge(edge)
        written.append((asset, quantity, edge))

    return tuple(written)


def test_a_node_is_readable_by_its_governed_identity(
    reader, populated
) -> None:
    asset = populated[0][0]

    found = reader.find_node(asset.node_id.value)

    assert found is not None
    assert found.node_id.value == asset.node_id.value
    assert found.label == "TR1"
    assert found.provenance.statement_key == asset.provenance.statement_key


def test_an_unknown_identity_reads_as_absent(reader, populated) -> None:
    assert reader.find_node("nope") is None
    assert reader.find_edge("nope") is None


def test_nodes_are_filtered_by_kind(reader, populated) -> None:
    assets = reader.nodes(
        states=CURRENT, kind=GraphNodeKind.ENGINEERING_ASSET
    )

    assert len(assets) == 2
    assert all(
        node.kind is GraphNodeKind.ENGINEERING_ASSET for node in assets
    )


def test_nodes_are_filtered_by_project(reader, populated) -> None:
    assets = reader.nodes(
        states=CURRENT,
        kind=GraphNodeKind.ENGINEERING_ASSET,
        project_id=2,
    )

    assert [node.provenance.project_id for node in assets] == [2]


def test_nodes_are_filtered_by_document(reader, populated) -> None:
    assets = reader.nodes(
        states=CURRENT,
        kind=GraphNodeKind.ENGINEERING_ASSET,
        document_id=1,
    )

    assert [node.provenance.document_id for node in assets] == [1]


def test_historical_nodes_are_excluded_unless_the_state_is_asked_for(
    db_session: Session, reader
) -> None:
    repository = SqlAlchemyGovernedGraphRepository(db_session)
    repository.upsert_node(
        governed_asset(
            designation="TR9",
            state=GraphObjectState.HISTORICAL,
            retirement_reason=None,
        )
    )

    assert reader.nodes(states=CURRENT) == ()
    assert len(reader.nodes(states=CURRENT_AND_HISTORICAL)) == 1


def test_edges_are_filtered_by_kind_and_scope(reader, populated) -> None:
    edges = reader.edges(
        states=CURRENT, kind=GraphEdgeKind.HAS_RATED_POWER, project_id=1
    )

    assert len(edges) == 1
    assert edges[0].provenance.project_id == 1


def test_edges_are_read_from_their_subject_only(reader, populated) -> None:
    """Directional: asking from the quantity's side returns nothing,
    because ``has_rated_power`` relates an asset *to* a quantity."""

    asset, quantity, _ = populated[0]

    from_asset = reader.edges_from_subjects(
        (asset.node_id.value,), states=CURRENT
    )
    from_quantity = reader.edges_from_subjects(
        (quantity.node_id.value,), states=CURRENT
    )

    assert len(from_asset) == 1
    assert from_quantity == ()


def test_identity_reads_ignore_state(reader, db_session: Session) -> None:
    """A relationship's far end must be readable whatever its state, or
    a governed relationship would come back with a missing side."""

    repository = SqlAlchemyGovernedGraphRepository(db_session)
    node = governed_asset(
        designation="TR9", state=GraphObjectState.HISTORICAL
    )
    repository.upsert_node(node)

    assert reader.nodes_by_identity((node.node_id.value,))


def test_identity_reads_deduplicate_and_tolerate_an_empty_request(
    reader, populated
) -> None:
    asset = populated[0][0]

    assert reader.nodes_by_identity(()) == ()
    assert len(
        reader.nodes_by_identity(
            (asset.node_id.value, asset.node_id.value)
        )
    ) == 1


def test_every_read_is_ordered_by_governed_identity(
    reader, populated
) -> None:
    nodes = reader.nodes(states=CURRENT)
    edges = reader.edges(states=CURRENT)

    assert [node.node_id.value for node in nodes] == sorted(
        node.node_id.value for node in nodes
    )
    assert [edge.edge_id.value for edge in edges] == sorted(
        edge.edge_id.value for edge in edges
    )


def test_two_identical_reads_return_identical_rows(
    reader, populated
) -> None:
    assert reader.nodes(states=CURRENT) == reader.nodes(states=CURRENT)
    assert reader.edges(states=CURRENT) == reader.edges(states=CURRENT)


def test_the_reader_reports_no_generation_before_a_rebuild(
    reader, populated
) -> None:
    assert reader.latest_generation() is None
