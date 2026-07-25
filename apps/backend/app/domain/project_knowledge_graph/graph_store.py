from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.project_knowledge_graph.graph_node_models import (
    ProjectGraphNode,
)
from app.domain.project_knowledge_graph.graph_relationship_models import (
    ProjectGraphRelationship,
)


class GraphStore(ABC):
    """
    Port for executing graph mutations and reading Project Knowledge
    Graph state. An adapter (e.g. ``SqlAlchemyGraphStore``) implements
    this against a specific storage technology - plain SQL tables
    today, perhaps a native graph database later - without this
    bounded context's domain or service layer ever depending on that
    choice. This is the database-agnostic seam Graph Persistence exists
    to provide (see this milestone's ADR).

    The mutation methods deliberately do not commit their own
    transaction - see ``GraphUnitOfWork``. They only ``flush``, so a
    caller executing many operations across one batch can commit or
    roll back the whole set atomically.
    """

    @abstractmethod
    def upsert_node(
        self,
        *,
        graph_entity_id: GraphEntityId,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphNode:
        """
        ``CREATE_NODE`` semantics: create the node (empty properties)
        if absent, or return it unchanged if it already exists. Never
        creates a duplicate for the same
        ``(project_id, entity_type, canonical_id)``.
        """

        raise NotImplementedError

    @abstractmethod
    def merge_node_property(
        self,
        *,
        graph_entity_id: GraphEntityId,
        attribute: str,
        value: str,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphNode:
        """
        ``UPDATE_NODE`` semantics: requires the node to already exist -
        raises ``GraphNodeNotFoundError`` if not - merges ``attribute``
        into its properties (overwriting any prior value for the same
        key, preserving every other key), and returns the updated node.
        """

        raise NotImplementedError

    @abstractmethod
    def upsert_relationship(
        self,
        *,
        source_entity_id: GraphEntityId,
        relationship_type: GraphRelationshipType,
        target_entity_id: GraphEntityId,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphRelationship:
        """
        ``CREATE_RELATIONSHIP`` semantics: idempotent upsert. Both
        endpoints must already exist as nodes in the same project -
        raises ``GraphNodeNotFoundError`` otherwise. Never infers a
        reverse relationship.
        """

        raise NotImplementedError

    @abstractmethod
    def get_node(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> ProjectGraphNode | None:
        raise NotImplementedError

    @abstractmethod
    def list_nodes(self, project_id: int) -> list[ProjectGraphNode]:
        raise NotImplementedError

    @abstractmethod
    def list_relationships(
        self,
        project_id: int,
    ) -> list[ProjectGraphRelationship]:
        raise NotImplementedError

    @abstractmethod
    def list_outgoing_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[ProjectGraphRelationship]:
        raise NotImplementedError

    @abstractmethod
    def list_incoming_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[ProjectGraphRelationship]:
        raise NotImplementedError
