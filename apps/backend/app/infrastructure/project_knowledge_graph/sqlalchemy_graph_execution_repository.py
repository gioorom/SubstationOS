from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecution,
    GraphExecutionStatus,
    GraphOperationExecutionResult,
)
from app.domain.project_knowledge_graph.graph_execution_repository import (
    GraphExecutionRepository,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    ConcurrentGraphMutationError,
    GraphExecutionNotFoundError,
)
from app.models.project_knowledge_graph import (
    GraphExecutionFingerprintRecord,
    GraphExecutionOperationResultRecord,
    GraphExecutionRecord,
)


class SqlAlchemyGraphExecutionRepository(GraphExecutionRepository):
    """
    SQLAlchemy adapter for the ``GraphExecutionRepository`` port. Like
    ``SqlAlchemyGraphStore``, writes only ``flush`` - never
    ``commit`` - so an execution's audit record and the graph mutations
    it describes commit or roll back together, as one unit, via
    ``GraphUnitOfWork``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, execution: GraphExecution) -> GraphExecution:
        record = GraphExecutionRecord(
            batch_id=execution.batch_id,
            batch_fingerprint=execution.batch_fingerprint,
            project_id=execution.project_id,
            status=execution.status,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            operation_count=execution.operation_count,
            failure_type=execution.failure_type,
            failure_message=execution.failure_message,
        )
        self._session.add(record)
        self._session.flush()

        self._save_operation_results(record.id, execution.operation_results)

        if execution.status is GraphExecutionStatus.SUCCEEDED:
            self._record_fingerprint(
                execution.batch_fingerprint,
                record.id,
            )

        self._session.flush()

        return self._to_domain(record)

    def update(self, execution: GraphExecution) -> GraphExecution:
        record = self._session.get(GraphExecutionRecord, execution.id)

        if record is None:
            raise GraphExecutionNotFoundError(execution.id)  # type: ignore[arg-type]

        record.status = execution.status
        record.completed_at = execution.completed_at
        record.operation_count = execution.operation_count
        record.failure_type = execution.failure_type
        record.failure_message = execution.failure_message

        self._save_operation_results(record.id, execution.operation_results)

        if execution.status is GraphExecutionStatus.SUCCEEDED:
            self._record_fingerprint(
                execution.batch_fingerprint,
                record.id,
            )

        self._session.flush()

        return self._to_domain(record)

    def get_by_id(self, execution_id: int) -> GraphExecution | None:
        record = self._session.get(GraphExecutionRecord, execution_id)

        return self._to_domain(record) if record is not None else None

    def get_successful_by_fingerprint(
        self,
        batch_fingerprint: str,
    ) -> GraphExecution | None:
        mapping = self._session.get(
            GraphExecutionFingerprintRecord,
            batch_fingerprint,
        )

        if mapping is None:
            return None

        record = self._session.get(
            GraphExecutionRecord,
            mapping.execution_id,
        )

        return self._to_domain(record) if record is not None else None

    def list_by_batch(self, batch_id: int) -> list[GraphExecution]:
        records = (
            self._session.query(GraphExecutionRecord)
            .filter(GraphExecutionRecord.batch_id == batch_id)
            .order_by(GraphExecutionRecord.started_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def _save_operation_results(
        self,
        execution_id: int,
        results: tuple[GraphOperationExecutionResult, ...],
    ) -> None:
        records = [
            GraphExecutionOperationResultRecord(
                execution_id=execution_id,
                sequence=result.sequence,
                kind=result.kind,
                succeeded=result.succeeded,
                detail=result.detail,
            )
            for result in results
        ]
        self._session.add_all(records)

    def _record_fingerprint(
        self,
        fingerprint: str,
        execution_id: int,
    ) -> None:
        self._session.add(
            GraphExecutionFingerprintRecord(
                fingerprint=fingerprint,
                execution_id=execution_id,
            )
        )

        try:
            self._session.flush()
        except IntegrityError as error:
            raise ConcurrentGraphMutationError(fingerprint) from error

    def _to_domain(self, record: GraphExecutionRecord) -> GraphExecution:
        result_records = (
            self._session.query(GraphExecutionOperationResultRecord)
            .filter(
                GraphExecutionOperationResultRecord.execution_id
                == record.id
            )
            .order_by(GraphExecutionOperationResultRecord.sequence.asc())
            .all()
        )

        return GraphExecution(
            id=record.id,
            batch_id=record.batch_id,
            batch_fingerprint=record.batch_fingerprint,
            project_id=record.project_id,
            status=record.status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            operation_count=record.operation_count,
            failure_type=record.failure_type,
            failure_message=record.failure_message,
            operation_results=tuple(
                GraphOperationExecutionResult(
                    sequence=result_record.sequence,
                    kind=result_record.kind,
                    succeeded=result_record.succeeded,
                    detail=result_record.detail,
                )
                for result_record in result_records
            ),
        )
