from __future__ import annotations

from datetime import datetime

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.graph_query.graph_query_factory import (
    GraphNeighborhoodFactory,
    GraphQueryFactory,
    GraphStatisticsFactory,
    GraphTraversalResultFactory,
)
from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphQueryKind,
    GraphRelationshipView,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _node(canonical_id: str, entity_type: str = "CABLE") -> GraphNodeView:
    return GraphNodeView(
        project_id=10,
        graph_entity_id=GraphEntityId(
            project_id=10, entity_type=entity_type, canonical_id=canonical_id
        ),
        entity_type=entity_type,
        canonical_id=canonical_id,
        properties={},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _relationship(
    source: GraphEntityId,
    rel_type: str,
    target: GraphEntityId,
) -> GraphRelationshipView:
    return GraphRelationshipView(
        project_id=10,
        source_entity_id=source,
        relationship_type=GraphRelationshipType(value=rel_type),
        target_entity_id=target,
        properties={},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def test_graph_query_factory_wraps_payload_with_a_query_envelope() -> (
    None
):
    result = GraphQueryFactory.wrap(
        project_id=10,
        kind=GraphQueryKind.STATISTICS,
        payload="anything",
        now=CREATED_AT,
    )

    assert result.query.project_id == 10
    assert result.query.kind is GraphQueryKind.STATISTICS
    assert result.query.requested_at == CREATED_AT
    assert result.payload == "anything"


def test_graph_statistics_factory_computes_totals_and_sorts_by_type() -> (
    None
):
    statistics = GraphStatisticsFactory.build(
        entities_by_type={"TRANSFORMER": 1, "CABLE": 2},
        relationships_by_type={"FEEDS": 3},
        orphan_count=1,
    )

    assert statistics.total_entities == 3
    assert statistics.total_relationships == 3
    assert statistics.entities_by_type == (
        ("CABLE", 2),
        ("TRANSFORMER", 1),
    )
    assert statistics.orphan_count == 1


def test_graph_neighborhood_factory_orders_and_dedups_neighbors() -> (
    None
):
    cable = GraphEntityId(project_id=10, entity_type="CABLE", canonical_id="C-295")
    tr1 = GraphEntityId(
        project_id=10, entity_type="TRANSFORMER", canonical_id="TR-01"
    )
    tr2 = GraphEntityId(
        project_id=10, entity_type="TRANSFORMER", canonical_id="TR-02"
    )

    neighborhood = GraphNeighborhoodFactory.build(
        center=_node("C-295"),
        outgoing=[
            _relationship(cable, "FEEDS", tr2),
            _relationship(cable, "FEEDS", tr1),
        ],
        incoming=[],
        neighbor_nodes=[
            _node("TR-02", "TRANSFORMER"),
            _node("TR-01", "TRANSFORMER"),
        ],
    )

    assert [op.target_entity_id.canonical_id for op in neighborhood.outgoing] == [
        "TR-01",
        "TR-02",
    ]
    assert [n.canonical_id for n in neighborhood.neighbors] == [
        "TR-01",
        "TR-02",
    ]


def test_graph_traversal_result_factory_merges_both_directions() -> (
    None
):
    cable = GraphEntityId(project_id=10, entity_type="CABLE", canonical_id="C-295")
    breaker = GraphEntityId(
        project_id=10, entity_type="BREAKER", canonical_id="CB-01"
    )
    transformer = GraphEntityId(
        project_id=10, entity_type="TRANSFORMER", canonical_id="TR-02"
    )

    neighborhood = GraphNeighborhoodFactory.build(
        center=_node("C-295"),
        outgoing=[_relationship(cable, "FEEDS", transformer)],
        incoming=[_relationship(breaker, "PROTECTS", cable)],
        neighbor_nodes=[
            _node("TR-02", "TRANSFORMER"),
            _node("CB-01", "BREAKER"),
        ],
    )

    traversal = GraphTraversalResultFactory.from_neighborhood(
        neighborhood,
        depth=1,
    )

    assert traversal.origin.value == "10:CABLE:C-295"
    assert traversal.depth == 1
    assert len(traversal.traversed_relationships) == 2
    assert len(traversal.visited_nodes) == 2
