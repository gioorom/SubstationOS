from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecution,
    GraphExecutionStatus,
    GraphOperationExecutionResult,
)


class GraphExecutionFactory:
    """
    Builds and transitions ``GraphExecution`` instances. Because
    ``GraphExecution`` is frozen, a transition returns a new instance
    rather than mutating one in place (CLAUDE.md SS6).
    """

    @staticmethod
    def start(
        *,
        batch_id: int,
        batch_fingerprint: str,
        project_id: int,
        operation_count: int,
        now: datetime,
    ) -> GraphExecution:
        return GraphExecution(
            id=None,
            batch_id=batch_id,
            batch_fingerprint=batch_fingerprint,
            project_id=project_id,
            status=GraphExecutionStatus.PENDING,
            started_at=now,
            completed_at=None,
            operation_count=operation_count,
            failure_type=None,
            failure_message=None,
            operation_results=(),
        )

    @staticmethod
    def succeed(
        execution: GraphExecution,
        *,
        operation_results: tuple[GraphOperationExecutionResult, ...],
        now: datetime,
    ) -> GraphExecution:
        return replace(
            execution,
            status=GraphExecutionStatus.SUCCEEDED,
            completed_at=now,
            operation_results=operation_results,
        )

    @staticmethod
    def fail(
        *,
        batch_id: int,
        batch_fingerprint: str,
        project_id: int,
        operation_count: int,
        started_at: datetime,
        completed_at: datetime,
        failure_type: str,
        failure_message: str,
        operation_results: tuple[GraphOperationExecutionResult, ...],
    ) -> GraphExecution:
        """
        Builds a fresh, standalone ``FAILED`` execution record - never a
        transition of the rolled-back ``PENDING`` attempt, since that
        attempt's own row was rolled back along with every graph
        mutation it made (see ``graph_execution_service``).
        """

        return GraphExecution(
            id=None,
            batch_id=batch_id,
            batch_fingerprint=batch_fingerprint,
            project_id=project_id,
            status=GraphExecutionStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            operation_count=operation_count,
            failure_type=failure_type,
            failure_message=failure_message,
            operation_results=operation_results,
        )
