from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.project_knowledge_graph.graph_node_models import (
    GraphNodeProperties,
    ProjectGraphNode,
)
from app.domain.project_knowledge_graph.graph_relationship_models import (
    GraphRelationshipProperties,
    ProjectGraphRelationship,
)
from app.domain.project_knowledge_graph.graph_store import GraphStore
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    ConcurrentGraphMutationError,
    GraphNodeNotFoundError,
)
from app.models.project_knowledge_graph import (
    ProjectGraphNodeRecord,
    ProjectGraphRelationshipRecord,
)


class SqlAlchemyGraphStore(GraphStore):
    """
    SQLAlchemy adapter for the ``GraphStore`` port, backed by plain
    relational tables (``ProjectGraphNodeRecord``/
    ``ProjectGraphRelationshipRecord``) - the reference implementation
    this milestone's ADR calls for, deliberately not any native graph
    database or query language.

    Mutation methods only ``add``/``flush`` - never ``commit`` - so
    ``GraphExecutionService`` can execute an entire batch and commit or
    roll it back as one unit via ``GraphUnitOfWork``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_node(
        self,
        *,
        graph_entity_id: GraphEntityId,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphNode:
        existing = self._find_node_record(graph_entity_id)

        if existing is not None:
            return self._node_to_domain(existing)

        record = ProjectGraphNodeRecord(
            project_id=graph_entity_id.project_id,
            entity_type=graph_entity_id.entity_type,
            canonical_id=graph_entity_id.canonical_id,
            properties={},
            created_by_execution_id=execution_id,
            updated_by_execution_id=execution_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)

        try:
            self._session.flush()
        except IntegrityError as error:
            raise ConcurrentGraphMutationError(
                graph_entity_id.value
            ) from error

        return self._node_to_domain(record)

    def merge_node_property(
        self,
        *,
        graph_entity_id: GraphEntityId,
        attribute: str,
        value: str,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphNode:
        record = self._find_node_record(graph_entity_id)

        if record is None:
            raise GraphNodeNotFoundError(
                graph_entity_id.project_id,
                graph_entity_id,
            )

        properties = GraphNodeProperties(
            values=tuple(sorted(record.properties.items()))
        ).merged_with(attribute, value)

        record.properties = properties.as_dict()
        record.updated_by_execution_id = execution_id
        record.updated_at = now

        self._session.flush()

        return self._node_to_domain(record)

    def upsert_relationship(
        self,
        *,
        source_entity_id: GraphEntityId,
        relationship_type: GraphRelationshipType,
        target_entity_id: GraphEntityId,
        execution_id: int,
        now: datetime,
    ) -> ProjectGraphRelationship:
        if self._find_node_record(source_entity_id) is None:
            raise GraphNodeNotFoundError(
                source_entity_id.project_id,
                source_entity_id,
            )

        if self._find_node_record(target_entity_id) is None:
            raise GraphNodeNotFoundError(
                target_entity_id.project_id,
                target_entity_id,
            )

        existing = self._find_relationship_record(
            source_entity_id,
            relationship_type,
            target_entity_id,
        )

        if existing is not None:
            return self._relationship_to_domain(existing)

        record = ProjectGraphRelationshipRecord(
            project_id=source_entity_id.project_id,
            source_entity_type=source_entity_id.entity_type,
            source_canonical_id=source_entity_id.canonical_id,
            relationship_type=relationship_type.value,
            target_entity_type=target_entity_id.entity_type,
            target_canonical_id=target_entity_id.canonical_id,
            properties={},
            created_by_execution_id=execution_id,
            updated_by_execution_id=execution_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)

        try:
            self._session.flush()
        except IntegrityError as error:
            natural_key = (
                f"{source_entity_id.value}-{relationship_type.value}"
                f"->{target_entity_id.value}"
            )
            raise ConcurrentGraphMutationError(natural_key) from error

        return self._relationship_to_domain(record)

    def get_node(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> ProjectGraphNode | None:
        record = self._find_node_record(graph_entity_id)

        return self._node_to_domain(record) if record is not None else None

    def list_nodes(self, project_id: int) -> list[ProjectGraphNode]:
        records = (
            self._session.query(ProjectGraphNodeRecord)
            .filter(ProjectGraphNodeRecord.project_id == project_id)
            .order_by(ProjectGraphNodeRecord.id.asc())
            .all()
        )

        return [self._node_to_domain(record) for record in records]

    def list_relationships(
        self,
        project_id: int,
    ) -> list[ProjectGraphRelationship]:
        records = (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id == project_id
            )
            .order_by(ProjectGraphRelationshipRecord.id.asc())
            .all()
        )

        return [self._relationship_to_domain(record) for record in records]

    def list_outgoing_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[ProjectGraphRelationship]:
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

        return [self._relationship_to_domain(record) for record in records]

    def list_incoming_relationships(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> list[ProjectGraphRelationship]:
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

        return [self._relationship_to_domain(record) for record in records]

    def _find_node_record(
        self,
        graph_entity_id: GraphEntityId,
    ) -> ProjectGraphNodeRecord | None:
        return (
            self._session.query(ProjectGraphNodeRecord)
            .filter(
                ProjectGraphNodeRecord.project_id
                == graph_entity_id.project_id,
                ProjectGraphNodeRecord.entity_type
                == graph_entity_id.entity_type,
                ProjectGraphNodeRecord.canonical_id
                == graph_entity_id.canonical_id,
            )
            .first()
        )

    def _find_relationship_record(
        self,
        source_entity_id: GraphEntityId,
        relationship_type: GraphRelationshipType,
        target_entity_id: GraphEntityId,
    ) -> ProjectGraphRelationshipRecord | None:
        return (
            self._session.query(ProjectGraphRelationshipRecord)
            .filter(
                ProjectGraphRelationshipRecord.project_id
                == source_entity_id.project_id,
                ProjectGraphRelationshipRecord.source_entity_type
                == source_entity_id.entity_type,
                ProjectGraphRelationshipRecord.source_canonical_id
                == source_entity_id.canonical_id,
                ProjectGraphRelationshipRecord.relationship_type
                == relationship_type.value,
                ProjectGraphRelationshipRecord.target_entity_type
                == target_entity_id.entity_type,
                ProjectGraphRelationshipRecord.target_canonical_id
                == target_entity_id.canonical_id,
            )
            .first()
        )

    @staticmethod
    def _node_to_domain(record: ProjectGraphNodeRecord) -> ProjectGraphNode:
        return ProjectGraphNode(
            id=record.id,
            project_id=record.project_id,
            graph_entity_id=GraphEntityId(
                project_id=record.project_id,
                entity_type=record.entity_type,
                canonical_id=record.canonical_id,
            ),
            entity_type=record.entity_type,
            canonical_id=record.canonical_id,
            properties=GraphNodeProperties(
                values=tuple(sorted(record.properties.items()))
            ),
            created_by_execution_id=record.created_by_execution_id,
            updated_by_execution_id=record.updated_by_execution_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _relationship_to_domain(
        record: ProjectGraphRelationshipRecord,
    ) -> ProjectGraphRelationship:
        return ProjectGraphRelationship(
            id=record.id,
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
            properties=GraphRelationshipProperties(
                values=tuple(sorted(record.properties.items()))
            ),
            created_by_execution_id=record.created_by_execution_id,
            updated_by_execution_id=record.updated_by_execution_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
