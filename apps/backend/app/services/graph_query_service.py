"""
Application services for Graph Query (Milestone 11.3). Each function is
a single use case, orchestrating the domain (``app.domain.graph_query``)
through the ``GraphQueryRepository`` port - never a raw database
session, and never Graph Persistence's own ``GraphStore``.

This module provides deterministic graph inspection and retrieval only:
no semantic search, no AI, no embeddings, no vector database, no
natural-language interpretation, no graph algorithms beyond depth-1
traversal. Every query here is one of a closed, named set
(``GraphQueryKind``).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_exceptions import (
    EntityNotFoundError,
)
from app.domain.graph_query.graph_query_factory import (
    GraphNeighborhoodFactory,
    GraphQueryFactory,
    GraphStatisticsFactory,
    GraphTraversalResultFactory,
)
from app.domain.graph_query.graph_query_models import (
    GraphNeighborhood,
    GraphNodeView,
    GraphQueryKind,
    GraphQueryResult,
    GraphRelationshipView,
    GraphSnapshot,
    GraphStatistics,
    GraphTraversalResult,
)
from app.domain.graph_query.graph_query_repository import (
    GraphQueryRepository,
)
from app.domain.graph_query.graph_query_validator import (
    GraphQueryValidator,
)


def _require_existing_node(
    repository: GraphQueryRepository,
    project_id: int,
    graph_entity_id: GraphEntityId,
) -> GraphNodeView:
    node = repository.get_node(project_id, graph_entity_id)

    if node is None:
        raise EntityNotFoundError(project_id, graph_entity_id)

    return node


def get_entity(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    graph_entity_id: GraphEntityId,
    now: datetime,
) -> GraphQueryResult[GraphNodeView]:
    GraphQueryValidator.validate_same_project(project_id, graph_entity_id)
    node = _require_existing_node(repository, project_id, graph_entity_id)

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.ENTITY_BY_ID,
        payload=node,
        now=now,
    )


def list_entities(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    has_attribute: str | None,
    now: datetime,
) -> GraphQueryResult[tuple[GraphNodeView, ...]]:
    if has_attribute is not None:
        GraphQueryValidator.validate_attribute_name(has_attribute)
        nodes = repository.list_nodes_with_attribute(
            project_id,
            has_attribute,
        )
        kind = GraphQueryKind.ENTITIES_BY_ATTRIBUTE
    else:
        nodes = repository.list_nodes(project_id)
        kind = GraphQueryKind.ALL_ENTITIES

    ordered = tuple(
        sorted(nodes, key=lambda node: node.graph_entity_id.value)
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=kind,
        payload=ordered,
        now=now,
    )


def list_entities_by_type(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    entity_type: str,
    now: datetime,
) -> GraphQueryResult[tuple[GraphNodeView, ...]]:
    GraphQueryValidator.validate_entity_type(entity_type)

    nodes = tuple(
        sorted(
            repository.list_nodes_by_type(project_id, entity_type),
            key=lambda node: node.graph_entity_id.value,
        )
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.ENTITIES_BY_TYPE,
        payload=nodes,
        now=now,
    )


def list_outgoing_relationships(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    graph_entity_id: GraphEntityId,
    now: datetime,
) -> GraphQueryResult[tuple[GraphRelationshipView, ...]]:
    GraphQueryValidator.validate_same_project(project_id, graph_entity_id)
    _require_existing_node(repository, project_id, graph_entity_id)

    relationships = tuple(
        sorted(
            repository.list_outgoing_relationships(
                project_id, graph_entity_id
            ),
            key=lambda r: (
                r.relationship_type.value,
                r.target_entity_id.value,
            ),
        )
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.OUTGOING_RELATIONSHIPS,
        payload=relationships,
        now=now,
    )


def list_incoming_relationships(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    graph_entity_id: GraphEntityId,
    now: datetime,
) -> GraphQueryResult[tuple[GraphRelationshipView, ...]]:
    GraphQueryValidator.validate_same_project(project_id, graph_entity_id)
    _require_existing_node(repository, project_id, graph_entity_id)

    relationships = tuple(
        sorted(
            repository.list_incoming_relationships(
                project_id, graph_entity_id
            ),
            key=lambda r: (
                r.relationship_type.value,
                r.source_entity_id.value,
            ),
        )
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.INCOMING_RELATIONSHIPS,
        payload=relationships,
        now=now,
    )


def get_neighborhood(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    graph_entity_id: GraphEntityId,
    depth: int,
    now: datetime,
) -> GraphQueryResult[GraphNeighborhood]:
    GraphQueryValidator.validate_depth(depth)
    GraphQueryValidator.validate_same_project(project_id, graph_entity_id)
    center = _require_existing_node(repository, project_id, graph_entity_id)

    outgoing = repository.list_outgoing_relationships(
        project_id, graph_entity_id
    )
    incoming = repository.list_incoming_relationships(
        project_id, graph_entity_id
    )

    neighbor_ids: dict[str, GraphEntityId] = {}
    for relationship in outgoing:
        neighbor_ids[relationship.target_entity_id.value] = (
            relationship.target_entity_id
        )
    for relationship in incoming:
        neighbor_ids[relationship.source_entity_id.value] = (
            relationship.source_entity_id
        )

    neighbor_nodes = [
        node
        for node in (
            repository.get_node(project_id, entity_id)
            for entity_id in neighbor_ids.values()
        )
        if node is not None
    ]

    neighborhood = GraphNeighborhoodFactory.build(
        center=center,
        outgoing=outgoing,
        incoming=incoming,
        neighbor_nodes=neighbor_nodes,
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.NEIGHBORHOOD,
        payload=neighborhood,
        now=now,
    )


def get_traversal(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    graph_entity_id: GraphEntityId,
    depth: int,
    now: datetime,
) -> GraphTraversalResult:
    """
    The general, direction-agnostic depth-1 traversal primitive,
    derived from the same neighborhood data ``get_neighborhood`` builds.
    Not wired to a dedicated endpoint this milestone (the neighborhood
    endpoint already serves the one supported query); available for a
    future consumer that needs the direction-agnostic shape directly.
    """

    neighborhood_result = get_neighborhood(
        repository,
        project_id=project_id,
        graph_entity_id=graph_entity_id,
        depth=depth,
        now=now,
    )

    return GraphTraversalResultFactory.from_neighborhood(
        neighborhood_result.payload,
        depth=depth,
    )


def get_statistics(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    now: datetime,
) -> GraphQueryResult[GraphStatistics]:
    entities_by_type = repository.count_entities_by_type(project_id)
    relationships_by_type = repository.count_relationships_by_type(
        project_id
    )
    orphan_count = len(repository.list_orphan_nodes(project_id))

    statistics = GraphStatisticsFactory.build(
        entities_by_type=entities_by_type,
        relationships_by_type=relationships_by_type,
        orphan_count=orphan_count,
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.STATISTICS,
        payload=statistics,
        now=now,
    )


def list_orphans(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    now: datetime,
) -> GraphQueryResult[tuple[GraphNodeView, ...]]:
    nodes = tuple(
        sorted(
            repository.list_orphan_nodes(project_id),
            key=lambda node: node.graph_entity_id.value,
        )
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.ORPHANS,
        payload=nodes,
        now=now,
    )


def list_all_relationships(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    now: datetime,
) -> GraphQueryResult[tuple[GraphRelationshipView, ...]]:
    relationships = tuple(
        sorted(
            repository.list_relationships(project_id),
            key=lambda r: (
                r.relationship_type.value,
                r.source_entity_id.value,
                r.target_entity_id.value,
            ),
        )
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.ALL_RELATIONSHIPS,
        payload=relationships,
        now=now,
    )


def get_project_snapshot(
    repository: GraphQueryRepository,
    *,
    project_id: int,
    now: datetime,
) -> GraphQueryResult[GraphSnapshot]:
    nodes = tuple(
        sorted(
            repository.list_nodes(project_id),
            key=lambda node: node.graph_entity_id.value,
        )
    )
    relationships = tuple(
        sorted(
            repository.list_relationships(project_id),
            key=lambda r: (
                r.relationship_type.value,
                r.source_entity_id.value,
                r.target_entity_id.value,
            ),
        )
    )

    snapshot = GraphSnapshot(
        project_id=project_id,
        nodes=nodes,
        relationships=relationships,
    )

    return GraphQueryFactory.wrap(
        project_id=project_id,
        kind=GraphQueryKind.PROJECT_SNAPSHOT,
        payload=snapshot,
        now=now,
    )
