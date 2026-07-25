from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.project_knowledge_graph.graph_execution_factory import (
    GraphExecutionFactory,
)
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecutionStatus,
    GraphOperationExecutionResult,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_execution_repository import (
    SqlAlchemyGraphExecutionRepository,
)
from app.models.project_knowledge_graph import (
    GraphExecutionFingerprintRecord,
)

STARTED_AT = datetime(2026, 1, 1, 10, 0, 0)
COMPLETED_AT = datetime(2026, 1, 1, 10, 0, 5)


def test_save_persists_a_pending_execution(db_session: Session) -> None:
    repository = SqlAlchemyGraphExecutionRepository(db_session)

    execution = repository.save(
        GraphExecutionFactory.start(
            batch_id=1,
            batch_fingerprint="fp-1",
            project_id=10,
            operation_count=2,
            now=STARTED_AT,
        )
    )
    db_session.commit()

    assert execution.id is not None
    assert execution.status is GraphExecutionStatus.PENDING


def test_update_transitions_to_succeeded_and_records_results(
    db_session: Session,
) -> None:
    repository = SqlAlchemyGraphExecutionRepository(db_session)
    pending = repository.save(
        GraphExecutionFactory.start(
            batch_id=1,
            batch_fingerprint="fp-2",
            project_id=10,
            operation_count=1,
            now=STARTED_AT,
        )
    )

    succeeded = GraphExecutionFactory.succeed(
        pending,
        operation_results=(
            GraphOperationExecutionResult(
                sequence=0,
                kind="create_node",
                succeeded=True,
                detail="node ensured",
            ),
        ),
        now=COMPLETED_AT,
    )
    updated = repository.update(succeeded)
    db_session.commit()

    assert updated.status is GraphExecutionStatus.SUCCEEDED
    assert len(updated.operation_results) == 1

    reloaded = repository.get_by_id(updated.id)  # type: ignore[arg-type]
    assert reloaded is not None
    assert reloaded.status is GraphExecutionStatus.SUCCEEDED
    assert reloaded.operation_results[0].detail == "node ensured"


def test_get_successful_by_fingerprint_finds_a_succeeded_execution(
    db_session: Session,
) -> None:
    repository = SqlAlchemyGraphExecutionRepository(db_session)
    pending = repository.save(
        GraphExecutionFactory.start(
            batch_id=1,
            batch_fingerprint="fp-3",
            project_id=10,
            operation_count=0,
            now=STARTED_AT,
        )
    )
    repository.update(
        GraphExecutionFactory.succeed(
            pending,
            operation_results=(),
            now=COMPLETED_AT,
        )
    )
    db_session.commit()

    found = repository.get_successful_by_fingerprint("fp-3")

    assert found is not None
    assert found.id == pending.id


def test_get_successful_by_fingerprint_returns_none_for_a_failed_execution(
    db_session: Session,
) -> None:
    repository = SqlAlchemyGraphExecutionRepository(db_session)
    repository.save(
        GraphExecutionFactory.fail(
            batch_id=1,
            batch_fingerprint="fp-4",
            project_id=10,
            operation_count=1,
            started_at=STARTED_AT,
            completed_at=COMPLETED_AT,
            failure_type="GraphNodeNotFoundError",
            failure_message="boom",
            operation_results=(),
        )
    )
    db_session.commit()

    assert repository.get_successful_by_fingerprint("fp-4") is None


def test_list_by_batch_returns_every_attempt_oldest_first(
    db_session: Session,
) -> None:
    repository = SqlAlchemyGraphExecutionRepository(db_session)
    repository.save(
        GraphExecutionFactory.fail(
            batch_id=7,
            batch_fingerprint="fp-5a",
            project_id=10,
            operation_count=1,
            started_at=STARTED_AT,
            completed_at=COMPLETED_AT,
            failure_type="GraphNodeNotFoundError",
            failure_message="boom",
            operation_results=(),
        )
    )
    pending = repository.save(
        GraphExecutionFactory.start(
            batch_id=7,
            batch_fingerprint="fp-5b",
            project_id=10,
            operation_count=1,
            now=COMPLETED_AT,
        )
    )
    repository.update(
        GraphExecutionFactory.succeed(
            pending,
            operation_results=(),
            now=COMPLETED_AT,
        )
    )
    db_session.commit()

    executions = repository.list_by_batch(7)

    assert len(executions) == 2
    assert executions[-1].status is GraphExecutionStatus.SUCCEEDED


def test_database_enforces_fingerprint_uniqueness(
    db_session: Session,
) -> None:
    db_session.add(
        GraphExecutionFingerprintRecord(
            fingerprint="fp-unique",
            execution_id=1,
        )
    )
    db_session.commit()

    db_session.add(
        GraphExecutionFingerprintRecord(
            fingerprint="fp-unique",
            execution_id=2,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
