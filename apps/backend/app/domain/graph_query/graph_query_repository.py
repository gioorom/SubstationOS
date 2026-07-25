from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphRelationshipView,
)


class GraphQueryRepository(ABC):
    """
    Port for Graph Query's own, read-only view of the Project Knowledge
    Graph. Deliberately not ``GraphStore`` (Graph Persistence's write
    port, which also happens to expose reads for its own execution
    needs) - this is Graph Query's own read model, returning its own
    view types (``GraphNodeView``/``GraphRelationshipView``), so a
    future reporting/read-replica store could implement this port
    without Graph Persistence's write concerns ever being touched.

    No mutation method exists on this port by design: Graph Query never
    modifies graph state.
    """

    @abstractmethod
    def get_node(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> GraphNodeView | None:
        raise NotImplementedError

    @abstractmethod
    def list_nodes(self, project_id: int) -> list[GraphNodeView]:
        raise NotImplementedError

    @abstractmethod
    def list_nodes_by_type(
        self,
        project_id: int,
        entity_type: str,
    ) -> list[GraphNodeView]:
        raise NotImplementedError

    @abstractmethod
    def list_nodes_with_attribute(
        self,
        project_id: int,
        attribute: str,
    ) -> list[GraphNodeView]:
        raise NotImplementedError

    @abstractmethod
    def list_orphan_nodes(self, project_id: int) -> list[GraphNodeView]:
        """Nodes with neither an outgoing nor an incoming
        relationship."""

        raise NotImplementedError

    @abstractmethod
    def list_relationships(
        self,
        project_id: int,
    ) -> list[GraphRelationshipView]:
        raise NotImplementedError

    @abstractmethod
    def list_outgoing_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[GraphRelationshipView]:
        raise NotImplementedError

    @abstractmethod
    def list_incoming_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[GraphRelationshipView]:
        raise NotImplementedError

    @abstractmethod
    def count_entities_by_type(self, project_id: int) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def count_relationships_by_type(
        self,
        project_id: int,
    ) -> dict[str, int]:
        raise NotImplementedError
