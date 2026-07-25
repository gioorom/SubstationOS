from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperation,
    GraphOperationBatch,
    GraphOperationBatchSource,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
    GraphRelationshipType,
)
from app.domain.graph_builder.graph_operation_batch_repository import (
    GraphOperationBatchRepository,
)
from app.models.graph_builder import (
    GraphOperationBatchRecord,
    GraphOperationRecord,
)

_NODE_OPERATION_KINDS = frozenset(
    kind.value for kind in GraphNodeOperationKind
)


class SqlAlchemyGraphOperationBatchRepository(GraphOperationBatchRepository):
    """
    SQLAlchemy adapter for the ``GraphOperationBatchRepository`` port,
    backed by ``app.models.graph_builder.GraphOperationBatchRecord`` and
    ``GraphOperationRecord``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, batch: GraphOperationBatch) -> GraphOperationBatch:
        record = GraphOperationBatchRecord(
            project_id=batch.project_id,
            scope=batch.source.scope,
            scope_id=batch.source.scope_id,
            created_at=batch.created_at,
        )
        self._session.add(record)
        self._session.flush()

        operation_records = [
            self._to_operation_record(record.id, sequence, operation)
            for sequence, operation in enumerate(batch.operations)
        ]
        self._session.add_all(operation_records)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, batch_id: int) -> GraphOperationBatch | None:
        record = self._session.get(GraphOperationBatchRecord, batch_id)

        return self._to_domain(record) if record is not None else None

    @staticmethod
    def _to_operation_record(
        batch_id: int,
        sequence: int,
        operation: GraphOperation,
    ) -> GraphOperationRecord:
        if isinstance(operation, GraphNodeOperation):
            return GraphOperationRecord(
                batch_id=batch_id,
                sequence=sequence,
                kind=operation.kind.value,
                source_fact_id=operation.source_fact_id,
                entity_project_id=operation.entity_id.project_id,
                entity_type=operation.entity_id.entity_type,
                entity_canonical_id=operation.entity_id.canonical_id,
                attribute=operation.attribute,
                value=operation.value,
            )

        return GraphOperationRecord(
            batch_id=batch_id,
            sequence=sequence,
            kind=operation.kind.value,
            source_fact_id=operation.source_fact_id,
            subject_project_id=operation.subject_id.project_id,
            subject_entity_type=operation.subject_id.entity_type,
            subject_canonical_id=operation.subject_id.canonical_id,
            relationship_type=operation.relationship_type.value,
            object_project_id=operation.object_id.project_id,
            object_entity_type=operation.object_id.entity_type,
            object_canonical_id=operation.object_id.canonical_id,
        )

    @staticmethod
    def _to_domain_operation(
        record: GraphOperationRecord,
    ) -> GraphOperation:
        if record.kind in _NODE_OPERATION_KINDS:
            return GraphNodeOperation(
                kind=GraphNodeOperationKind(record.kind),
                entity_id=GraphEntityId(
                    project_id=record.entity_project_id,  # type: ignore[arg-type]
                    entity_type=record.entity_type,  # type: ignore[arg-type]
                    canonical_id=record.entity_canonical_id,  # type: ignore[arg-type]
                ),
                attribute=record.attribute,
                value=record.value,
                source_fact_id=record.source_fact_id,
            )

        return GraphRelationshipOperation(
            kind=GraphRelationshipOperationKind(record.kind),
            subject_id=GraphEntityId(
                project_id=record.subject_project_id,  # type: ignore[arg-type]
                entity_type=record.subject_entity_type,  # type: ignore[arg-type]
                canonical_id=record.subject_canonical_id,  # type: ignore[arg-type]
            ),
            relationship_type=GraphRelationshipType(
                value=record.relationship_type  # type: ignore[arg-type]
            ),
            object_id=GraphEntityId(
                project_id=record.object_project_id,  # type: ignore[arg-type]
                entity_type=record.object_entity_type,  # type: ignore[arg-type]
                canonical_id=record.object_canonical_id,  # type: ignore[arg-type]
            ),
            source_fact_id=record.source_fact_id,
        )

    def _to_domain(
        self,
        record: GraphOperationBatchRecord,
    ) -> GraphOperationBatch:
        operation_records = (
            self._session.query(GraphOperationRecord)
            .filter(GraphOperationRecord.batch_id == record.id)
            .order_by(GraphOperationRecord.sequence.asc())
            .all()
        )

        return GraphOperationBatch(
            id=record.id,
            project_id=record.project_id,
            source=GraphOperationBatchSource(
                scope=record.scope,
                scope_id=record.scope_id,
            ),
            operations=tuple(
                self._to_domain_operation(operation_record)
                for operation_record in operation_records
            ),
            created_at=record.created_at,
        )
