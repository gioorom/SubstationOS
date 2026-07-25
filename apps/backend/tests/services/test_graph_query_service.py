from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.graph_query.graph_query_exceptions import (
    CrossProjectGraphQueryError,
    EntityNotFoundError,
    UnsupportedTraversalDepthError,
)
from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphRelationshipView,
)
from app.domain.graph_query.graph_query_repository import (
    GraphQueryRepository,
)
from app.services import graph_query_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _entity(entity_type: str, canonical_id: str, project_id: int = 10) -> GraphEntityId:
    return GraphEntityId(
        project_id=project_id, entity_type=entity_type, canonical_id=canonical_id
    )


def _node(entity_type: str, canonical_id: str, properties: dict | None = None) -> GraphNodeView:
    return GraphNodeView(
        project_id=10,
        graph_entity_id=_entity(entity_type, canonical_id),
        entity_type=entity_type,
        canonical_id=canonical_id,
        properties=properties or {},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _relationship(
    source: GraphEntityId, rel_type: str, target: GraphEntityId
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


class FakeGraphQueryRepository(GraphQueryRepository):
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNodeView] = {}
        self.relationships: list[GraphRelationshipView] = []

    def add_node(self, node: GraphNodeView) -> None:
        self.nodes[node.graph_entity_id.value] = node

    def add_relationship(self, relationship: GraphRelationshipView) -> None:
        self.relationships.append(relationship)

    def get_node(self, project_id, graph_entity_id):
        node = self.nodes.get(graph_entity_id.value)
        return node if node is not None and node.project_id == project_id else None

    def list_nodes(self, project_id):
        return [n for n in self.nodes.values() if n.project_id == project_id]

    def list_nodes_by_type(self, project_id, entity_type):
        return [
            n
            for n in self.list_nodes(project_id)
            if n.entity_type == entity_type
        ]

    def list_nodes_with_attribute(self, project_id, attribute):
        return [
            n for n in self.list_nodes(project_id) if attribute in n.properties
        ]

    def list_orphan_nodes(self, project_id):
        connected = set()
        for r in self.relationships:
            connected.add(r.source_entity_id.value)
            connected.add(r.target_entity_id.value)
        return [
            n
            for n in self.list_nodes(project_id)
            if n.graph_entity_id.value not in connected
        ]

    def list_relationships(self, project_id):
        return [r for r in self.relationships if r.project_id == project_id]

    def list_outgoing_relationships(self, project_id, graph_entity_id):
        return [
            r
            for r in self.list_relationships(project_id)
            if r.source_entity_id.value == graph_entity_id.value
        ]

    def list_incoming_relationships(self, project_id, graph_entity_id):
        return [
            r
            for r in self.list_relationships(project_id)
            if r.target_entity_id.value == graph_entity_id.value
        ]

    def count_entities_by_type(self, project_id):
        counts: dict[str, int] = {}
        for n in self.list_nodes(project_id):
            counts[n.entity_type] = counts.get(n.entity_type, 0) + 1
        return counts

    def count_relationships_by_type(self, project_id):
        counts: dict[str, int] = {}
        for r in self.list_relationships(project_id):
            counts[r.relationship_type.value] = (
                counts.get(r.relationship_type.value, 0) + 1
            )
        return counts


@pytest.fixture()
def repository() -> FakeGraphQueryRepository:
    repo = FakeGraphQueryRepository()
    repo.add_node(_node("CABLE", "C-295"))
    repo.add_node(_node("TRANSFORMER", "TR-02", {"rated_voltage": "132kV"}))
    repo.add_node(_node("BREAKER", "CB-01"))
    repo.add_relationship(
        _relationship(_entity("CABLE", "C-295"), "FEEDS", _entity("TRANSFORMER", "TR-02"))
    )
    return repo


def test_get_entity_returns_the_node(repository) -> None:
    result = graph_query_service.get_entity(
        repository,
        project_id=10,
        graph_entity_id=_entity("CABLE", "C-295"),
        now=CREATED_AT,
    )

    assert result.payload.canonical_id == "C-295"


def test_get_entity_raises_for_an_unknown_entity(repository) -> None:
    with pytest.raises(EntityNotFoundError):
        graph_query_service.get_entity(
            repository,
            project_id=10,
            graph_entity_id=_entity("CABLE", "UNKNOWN"),
            now=CREATED_AT,
        )


def test_get_entity_raises_for_cross_project_access(repository) -> None:
    with pytest.raises(CrossProjectGraphQueryError):
        graph_query_service.get_entity(
            repository,
            project_id=10,
            graph_entity_id=_entity("CABLE", "C-295", project_id=99),
            now=CREATED_AT,
        )


def test_list_entities_returns_every_node_sorted(repository) -> None:
    result = graph_query_service.list_entities(
        repository, project_id=10, has_attribute=None, now=CREATED_AT
    )

    values = [n.graph_entity_id.value for n in result.payload]
    assert values == sorted(values)
    assert len(result.payload) == 3


def test_list_entities_filters_by_attribute(repository) -> None:
    result = graph_query_service.list_entities(
        repository, project_id=10, has_attribute="rated_voltage", now=CREATED_AT
    )

    assert [n.canonical_id for n in result.payload] == ["TR-02"]


def test_list_entities_by_type(repository) -> None:
    result = graph_query_service.list_entities_by_type(
        repository, project_id=10, entity_type="TRANSFORMER", now=CREATED_AT
    )

    assert [n.canonical_id for n in result.payload] == ["TR-02"]


def test_list_outgoing_relationships_raises_for_an_unknown_entity(
    repository,
) -> None:
    with pytest.raises(EntityNotFoundError):
        graph_query_service.list_outgoing_relationships(
            repository,
            project_id=10,
            graph_entity_id=_entity("CABLE", "UNKNOWN"),
            now=CREATED_AT,
        )


def test_list_outgoing_relationships(repository) -> None:
    result = graph_query_service.list_outgoing_relationships(
        repository,
        project_id=10,
        graph_entity_id=_entity("CABLE", "C-295"),
        now=CREATED_AT,
    )

    assert len(result.payload) == 1


def test_list_incoming_relationships(repository) -> None:
    result = graph_query_service.list_incoming_relationships(
        repository,
        project_id=10,
        graph_entity_id=_entity("TRANSFORMER", "TR-02"),
        now=CREATED_AT,
    )

    assert len(result.payload) == 1


def test_get_neighborhood_returns_center_and_neighbor(repository) -> None:
    result = graph_query_service.get_neighborhood(
        repository,
        project_id=10,
        graph_entity_id=_entity("CABLE", "C-295"),
        depth=1,
        now=CREATED_AT,
    )

    neighborhood = result.payload
    assert neighborhood.center.canonical_id == "C-295"
    assert len(neighborhood.outgoing) == 1
    assert len(neighborhood.incoming) == 0
    assert [n.canonical_id for n in neighborhood.neighbors] == ["TR-02"]


def test_get_neighborhood_rejects_unsupported_depth(repository) -> None:
    with pytest.raises(UnsupportedTraversalDepthError):
        graph_query_service.get_neighborhood(
            repository,
            project_id=10,
            graph_entity_id=_entity("CABLE", "C-295"),
            depth=2,
            now=CREATED_AT,
        )


def test_get_traversal_derives_from_neighborhood(repository) -> None:
    traversal = graph_query_service.get_traversal(
        repository,
        project_id=10,
        graph_entity_id=_entity("CABLE", "C-295"),
        depth=1,
        now=CREATED_AT,
    )

    assert traversal.origin.value == "10:CABLE:C-295"
    assert len(traversal.visited_nodes) == 1
    assert len(traversal.traversed_relationships) == 1


def test_get_statistics(repository) -> None:
    result = graph_query_service.get_statistics(
        repository, project_id=10, now=CREATED_AT
    )

    statistics = result.payload
    assert statistics.total_entities == 3
    assert statistics.total_relationships == 1
    assert statistics.orphan_count == 1


def test_list_orphans(repository) -> None:
    result = graph_query_service.list_orphans(
        repository, project_id=10, now=CREATED_AT
    )

    assert [n.canonical_id for n in result.payload] == ["CB-01"]


def test_list_all_relationships(repository) -> None:
    result = graph_query_service.list_all_relationships(
        repository, project_id=10, now=CREATED_AT
    )

    assert len(result.payload) == 1


def test_get_project_snapshot_bundles_nodes_and_relationships(
    repository,
) -> None:
    result = graph_query_service.get_project_snapshot(
        repository, project_id=10, now=CREATED_AT
    )

    snapshot = result.payload
    assert len(snapshot.nodes) == 3
    assert len(snapshot.relationships) == 1
