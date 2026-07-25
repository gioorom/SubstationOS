from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphRelationshipView,
)
from app.domain.graph_query.graph_query_repository import (
    GraphQueryRepository,
)
from app.models.project_knowledge_graph import (
    ProjectGraphNodeRecord,
    ProjectGraphRelationshipRecord,
)


class SqlAlchemyGraphQueryRepository(GraphQueryRepository):
    """
    SQLAlchemy adapter for the ``GraphQueryRepository`` port. Reads the
    same tables ``SqlAlchemyGraphStore`` writes
    (``project_graph_nodes``/``project_graph_relationships``) - no
    schema change, read-only - but is its own, separate class: Graph
    Query never imports or instantiates ``SqlAlchemyGraphStore``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_node(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> GraphNodeView | None:
        record = self._find_node_record(project_id, graph_entity_id)

        return self._node_to_view(record) if record is not None else None

    def list_nodes(self, project_id: int) -> list[GraphNodeView]:
        records = (
            self._session.query(ProjectGraphNodeRecord)
            .filter(ProjectGraphNodeRecord.project_id == project_id)
            .order_by(ProjectGraphNodeRecord.id.asc())
            .all()
        )

        return [self._node_to_view(record) for record in records]

    def list_nodes_by_type(
        self,
        project_id: int,
        entity_type: str,
    ) -> list[GraphNodeView]:
        records = (
            self._session.query(ProjectGraphNodeRecord)
            .filter(
                ProjectGraphNodeRecord.project_id == project_id,
                ProjectGraphNodeRecord.entity_type == entity_type,
            )
            .order_by(ProjectGraphNodeRecord.id.asc())
            .all()
        )

        return [self._node_to_view(record) for record in records]

    def list_nodes_with_attribute(
        self,
        project_id: int,
        attribute: str,
    ) -> list[GraphNodeView]:
        records = (
            self._session.query(ProjectGraphNodeRecord)
            .filter(ProjectGraphNodeRecord.project_id == project_id)
            .order_by(ProjectGraphNodeRecord.id.asc())
            .all()
        )

        return [
            self._node_to_view(record)
            for record in records
            if attribute in record.properties
        ]

    def list_orphan_nodes(self, project_id: int) -> list[GraphNodeView]:
        node_records = (
            self._session.query(ProjectGraphNodeRecord)
            .filter(ProjectGraphNodeRecord.project_id == project_id)
            .order_by(ProjectGraphNodeRecord.id.asc())
            .all()
        )
        relationship_records = (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id
            )
            .all()
        )

        connected_keys: set[tuple[str, str]] = set()
        for relationship in relationship_records:
            connected_keys.add(
                (
                    relationship.source_entity_type,
                    relationship.source_canonical_id,
                )
            )
            connected_keys.add(
                (
                    relationship.target_entity_type,
                    relationship.target_canonical_id,
                )
            )

        return [
            self._node_to_view(record)
            for record in node_records
            if (record.entity_type, record.canonical_id)
            not in connected_keys
        ]

    def list_relationships(
        self,
        project_id: int,
    ) -> list[GraphRelationshipView]:
        records = (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id
            )
            .order_by(ProjectGraphRelationshipRecord.id.asc())
            .all()
        )

        return [self._relationship_to_view(record) for record in records]

    def list_outgoing_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[GraphRelationshipView]:
        records = (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id,
                ProjectGraphRelationshipRecord.source_entity_type
                == graph_entity_id.entity_type,
                ProjectGraphRelationshipRecord.source_canonical_id
                == graph_entity_id.canonical_id,
            )
            .order_by(ProjectGraphRelationshipRecord.id.asc())
            .all()
        )

        return [self._relationship_to_view(record) for record in records]

    def list_incoming_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[GraphRelationshipView]:
        records = (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id,
                ProjectGraphRelationshipRecord.target_entity_type
                == graph_entity_id.entity_type,
                ProjectGraphRelationshipRecord.target_canonical_id
                == graph_entity_id.canonical_id,
            )
            .order_by(ProjectGraphRelationshipRecord.id.asc())
            .all()
        )

        return [self._relationship_to_view(record) for record in records]

    def count_entities_by_type(self, project_id: int) -> dict[str, int]:
        rows = (
            self._session.query(
                ProjectGraphNodeRecord.entity_type,
                func.count(ProjectGraphNodeRecord.id),
            )
            .filter(ProjectGraphNodeRecord.project_id == project_id)
            .group_by(ProjectGraphNodeRecord.entity_type)
            .all()
        )

        return {entity_type: count for entity_type, count in rows}

    def count_relationships_by_type(
        self,
        project_id: int,
    ) -> dict[str, int]:
        rows = (
            self._session.query(
                ProjectGraphRelationshipRecord.relationship_type,
                func.count(ProjectGraphRelationshipRecord.id),
            )
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id
            )
            .group_by(ProjectGraphRelationshipRecord.relationship_type)
            .all()
        )

        return {
            relationship_type: count
            for relationship_type, count in rows
        }

    def _find_node_record(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> ProjectGraphNodeRecord | None:
        return (
            self._session.query(ProjectGraphNodeRecord)
            .filter(
                ProjectGraphNodeRecord.project_id == project_id,
                ProjectGraphNodeRecord.entity_type
                == graph_entity_id.entity_type,
                ProjectGraphNodeRecord.canonical_id
                == graph_entity_id.canonical_id,
            )
            .first()
        )

    @staticmethod
    def _node_to_view(record: ProjectGraphNodeRecord) -> GraphNodeView:
        return GraphNodeView(
            project_id=record.project_id,
            graph_entity_id=GraphEntityId(
                project_id=record.project_id,
                entity_type=record.entity_type,
                canonical_id=record.canonical_id,
            ),
            entity_type=record.entity_type,
            canonical_id=record.canonical_id,
            properties=dict(record.properties),
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by_execution_id=record.created_by_execution_id,
            updated_by_execution_id=record.updated_by_execution_id,
        )

    @staticmethod
    def _relationship_to_view(
        record: ProjectGraphRelationshipRecord,
    ) -> GraphRelationshipView:
        return GraphRelationshipView(
            project_id=record.project_id,
            source_entity_id=GraphEntityId(
                project_id=record.project_id,
                entity_type=record.source_entity_type,
                canonical_id=record.source_canonical_id,
            ),
            relationship_type=GraphRelationshipType(
                value=record.relationship_type
            ),
            target_entity_id=GraphEntityId(
                project_id=record.project_id,
                entity_type=record.target_entity_type,
                canonical_id=record.target_canonical_id,
            ),
            properties=dict(record.properties),
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by_execution_id=record.created_by_execution_id,
            updated_by_execution_id=record.updated_by_execution_id,
        )
