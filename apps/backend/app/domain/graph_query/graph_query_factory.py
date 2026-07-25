from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from app.domain.graph_query.graph_query_models import (
    GraphNeighborhood,
    GraphNodeView,
    GraphQuery,
    GraphQueryKind,
    GraphQueryResult,
    GraphRelationshipView,
    GraphStatistics,
    GraphTraversalResult,
)

T = TypeVar("T")


class GraphQueryFactory:
    """Wraps a query's payload in the uniform ``GraphQueryResult``
    envelope every service function returns."""

    @staticmethod
    def wrap(
        *,
        project_id: int,
        kind: GraphQueryKind,
        payload: T,
        now: datetime,
    ) -> GraphQueryResult[T]:
        return GraphQueryResult(
            query=GraphQuery(
                project_id=project_id,
                kind=kind,
                requested_at=now,
            ),
            payload=payload,
        )


class GraphStatisticsFactory:
    @staticmethod
    def build(
        *,
        entities_by_type: dict[str, int],
        relationships_by_type: dict[str, int],
        orphan_count: int,
    ) -> GraphStatistics:
        return GraphStatistics(
            total_entities=sum(entities_by_type.values()),
            total_relationships=sum(relationships_by_type.values()),
            entities_by_type=tuple(sorted(entities_by_type.items())),
            relationships_by_type=tuple(
                sorted(relationships_by_type.items())
            ),
            orphan_count=orphan_count,
        )


class GraphNeighborhoodFactory:
    """
    Assembles a ``GraphNeighborhood`` from already-fetched repository
    data, owning the ordering and deduplication rules the "Order every
    collection consistently" traversal requirement demands - the
    service layer fetches, this factory arranges.
    """

    @staticmethod
    def build(
        *,
        center: GraphNodeView,
        outgoing: list[GraphRelationshipView],
        incoming: list[GraphRelationshipView],
        neighbor_nodes: list[GraphNodeView],
    ) -> GraphNeighborhood:
        return GraphNeighborhood(
            center=center,
            outgoing=tuple(
                sorted(
                    outgoing,
                    key=lambda r: (
                        r.relationship_type.value,
                        r.target_entity_id.value,
                    ),
                )
            ),
            incoming=tuple(
                sorted(
                    incoming,
                    key=lambda r: (
                        r.relationship_type.value,
                        r.source_entity_id.value,
                    ),
                )
            ),
            neighbors=tuple(
                sorted(
                    neighbor_nodes,
                    key=lambda n: n.graph_entity_id.value,
                )
            ),
        )


class GraphTraversalResultFactory:
    """Derives the general, direction-agnostic ``GraphTraversalResult``
    from an already-built ``GraphNeighborhood`` - never duplicates the
    fetch or the ordering logic ``GraphNeighborhoodFactory`` already
    owns."""

    @staticmethod
    def from_neighborhood(
        neighborhood: GraphNeighborhood,
        *,
        depth: int,
    ) -> GraphTraversalResult:
        relationships = tuple(
            sorted(
                neighborhood.outgoing + neighborhood.incoming,
                key=lambda r: (
                    r.relationship_type.value,
                    r.source_entity_id.value,
                    r.target_entity_id.value,
                ),
            )
        )

        return GraphTraversalResult(
            origin=neighborhood.center.graph_entity_id,
            depth=depth,
            visited_nodes=neighborhood.neighbors,
            traversed_relationships=relationships,
        )
