from __future__ import annotations

from datetime import datetime

from app.domain.project_knowledge_graph.graph_execution_factory import (
    GraphExecutionFactory,
)
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecutionStatus,
    GraphOperationExecutionResult,
)

STARTED_AT = datetime(2026, 1, 1, 10, 0, 0)
COMPLETED_AT = datetime(2026, 1, 1, 10, 0, 5)


def test_start_builds_a_pending_execution() -> None:
    execution = GraphExecutionFactory.start(
        batch_id=1,
        batch_fingerprint="abc",
        project_id=10,
        operation_count=3,
        now=STARTED_AT,
    )

    assert execution.id is None
    assert execution.status is GraphExecutionStatus.PENDING
    assert execution.started_at == STARTED_AT
    assert execution.completed_at is None
    assert execution.operation_results == ()


def test_succeed_transitions_to_succeeded_without_mutating_original() -> (
    None
):
    pending = GraphExecutionFactory.start(
        batch_id=1,
        batch_fingerprint="abc",
        project_id=10,
        operation_count=1,
        now=STARTED_AT,
    )
    results = (
        GraphOperationExecutionResult(
            sequence=0,
            kind="create_node",
            succeeded=True,
            detail="node ensured",
        ),
    )

    succeeded = GraphExecutionFactory.succeed(
        pending,
        operation_results=results,
        now=COMPLETED_AT,
    )

    assert succeeded.status is GraphExecutionStatus.SUCCEEDED
    assert succeeded.completed_at == COMPLETED_AT
    assert succeeded.operation_results == results
    assert pending.status is GraphExecutionStatus.PENDING


def test_fail_builds_a_standalone_failed_execution() -> None:
    failed = GraphExecutionFactory.fail(
        batch_id=1,
        batch_fingerprint="abc",
        project_id=10,
        operation_count=2,
        started_at=STARTED_AT,
        completed_at=COMPLETED_AT,
        failure_type="GraphNodeNotFoundError",
        failure_message="No node found",
        operation_results=(),
    )

    assert failed.id is None
    assert failed.status is GraphExecutionStatus.FAILED
    assert failed.failure_type == "GraphNodeNotFoundError"
    assert failed.failure_message == "No node found"
