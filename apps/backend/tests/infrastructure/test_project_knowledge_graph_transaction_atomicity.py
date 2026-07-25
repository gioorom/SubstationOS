"""
DB-level (real SQLAlchemy session, no fakes) regression coverage for
Project Knowledge Graph execution atomicity - part of Milestone 12's
transaction boundary audit. The service-level tests
(tests/services/test_graph_execution_service.py) already prove this
behavior against fake ports; this file proves the same guarantee holds
against the real SqlAlchemyGraphStore/SqlAlchemyGraphExecutionRepository/
SqlAlchemyGraphUnitOfWork stack and a real database.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperationBatch,
    GraphOperationBatchScope,
    GraphOperationBatchSource,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
    GraphRelationshipType,
)
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecutionStatus,
)
from app.infrastructure.graph_builder.sqlalchemy_graph_operation_batch_repository import (
    SqlAlchemyGraphOperationBatchRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_execution_repository import (
    SqlAlchemyGraphExecutionRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store import (
    SqlAlchemyGraphStore,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_unit_of_work import (
    SqlAlchemyGraphUnitOfWork,
)
from app.models.project import Project as ProjectRecord
from app.models.project_knowledge_graph import (
    GraphExecutionRecord,
    ProjectGraphNodeRecord,
)
from app.services import graph_execution_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project(db_session: Session) -> int:
    project = ProjectRecord(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project.id


def test_a_mid_batch_failure_leaves_no_partial_graph_state(
    db_session: Session,
) -> None:
    project_id = _persist_project(db_session)

    cable = GraphEntityId(
        project_id=project_id, entity_type="CABLE", canonical_id="C-295"
    )
    transformer = GraphEntityId(
        project_id=project_id,
        entity_type="TRANSFORMER",
        canonical_id="TR-02",
    )

    batch_repository = SqlAlchemyGraphOperationBatchRepository(db_session)
    batch = batch_repository.save(
        GraphOperationBatch(
            id=None,
            project_id=project_id,
            source=GraphOperationBatchSource(
                scope=GraphOperationBatchScope.PROJECT,
                scope_id=project_id,
            ),
            operations=(
                # 1: valid - would create a node if committed.
                GraphNodeOperation(
                    kind=GraphNodeOperationKind.CREATE_NODE,
                    entity_id=cable,
                    attribute=None,
                    value=None,
                    source_fact_id=1,
                ),
                # 2: unsupported - Graph Persistence only executes
                # CREATE_RELATIONSHIP, never SUPERSEDE_RELATIONSHIP.
                GraphRelationshipOperation(
                    kind=GraphRelationshipOperationKind.SUPERSEDE_RELATIONSHIP,
                    subject_id=cable,
                    relationship_type=GraphRelationshipType(value="FEEDS"),
                    object_id=transformer,
                    source_fact_id=1,
                ),
            ),
            created_at=CREATED_AT,
        )
    )

    execution_repository = SqlAlchemyGraphExecutionRepository(db_session)
    graph_store = SqlAlchemyGraphStore(db_session)
    project_repository = SqlAlchemyProjectRepository(db_session)
    unit_of_work = SqlAlchemyGraphUnitOfWork(db_session)

    result = graph_execution_service.execute_batch(
        batch_repository,
        execution_repository,
        graph_store,
        project_repository,
        unit_of_work,
        batch_id=batch.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    assert result.execution.status is GraphExecutionStatus.FAILED

    # The CREATE_NODE that ran before the failing operation must not
    # have survived the rollback - zero rows, not one.
    node_count = (
        db_session.query(ProjectGraphNodeRecord)
        .filter(ProjectGraphNodeRecord.project_id == project_id)
        .count()
    )
    assert node_count == 0

    # Exactly one execution row exists: the standalone FAILED record.
    # The PENDING attempt that was rolled back left nothing behind.
    execution_count = (
        db_session.query(GraphExecutionRecord)
        .filter(GraphExecutionRecord.batch_id == batch.id)
        .count()
    )
    assert execution_count == 1

    # The session remains fully usable after the rollback - proves
    # GraphUnitOfWork.rollback() did not leave the connection in a
    # broken state.
    db_session.query(ProjectGraphNodeRecord).count()
