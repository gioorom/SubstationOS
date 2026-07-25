from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

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
from app.domain.graph_builder.graph_operation_batch_repository import (
    GraphOperationBatchRepository,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecution,
    GraphExecutionStatus,
)
from app.domain.project_knowledge_graph.graph_execution_repository import (
    GraphExecutionRepository,
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
from app.domain.project_knowledge_graph.graph_unit_of_work import (
    GraphUnitOfWork,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    BatchMissingProjectError,
    GraphNodeNotFoundError,
    GraphOperationBatchNotFoundError,
    ProjectNotGraphExecutableError,
)
from app.services import graph_execution_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


class FakeGraphOperationBatchRepository(GraphOperationBatchRepository):
    def __init__(self) -> None:
        self._batches: dict[int, GraphOperationBatch] = {}

    def register(self, batch: GraphOperationBatch) -> None:
        self._batches[batch.id] = batch  # type: ignore[index]

    def save(self, batch: GraphOperationBatch) -> GraphOperationBatch:
        raise NotImplementedError

    def get_by_id(self, batch_id: int) -> GraphOperationBatch | None:
        return self._batches.get(batch_id)


class FakeGraphExecutionRepository(GraphExecutionRepository):
    def __init__(self) -> None:
        self._executions: dict[int, GraphExecution] = {}
        self._fingerprints: dict[str, int] = {}
        self._next_id = 1

    def save(self, execution: GraphExecution) -> GraphExecution:
        execution = replace(execution, id=self._next_id)
        self._next_id += 1
        self._executions[execution.id] = execution  # type: ignore[index]

        if execution.status is GraphExecutionStatus.SUCCEEDED:
            self._fingerprints[execution.batch_fingerprint] = execution.id  # type: ignore[assignment]

        return execution

    def update(self, execution: GraphExecution) -> GraphExecution:
        self._executions[execution.id] = execution  # type: ignore[index]

        if execution.status is GraphExecutionStatus.SUCCEEDED:
            self._fingerprints[execution.batch_fingerprint] = execution.id  # type: ignore[assignment]

        return execution

    def get_by_id(self, execution_id: int) -> GraphExecution | None:
        return self._executions.get(execution_id)

    def get_successful_by_fingerprint(
        self,
        batch_fingerprint: str,
    ) -> GraphExecution | None:
        execution_id = self._fingerprints.get(batch_fingerprint)

        return (
            self._executions.get(execution_id)
            if execution_id is not None
            else None
        )

    def list_by_batch(self, batch_id: int) -> list[GraphExecution]:
        return [
            execution
            for execution in self._executions.values()
            if execution.batch_id == batch_id
        ]


class FakeGraphStore(GraphStore):
    def __init__(self) -> None:
        self._nodes: dict[str, ProjectGraphNode] = {}
        self._relationships: dict[str, ProjectGraphRelationship] = {}
        self.committed_nodes: dict[str, ProjectGraphNode] = {}

    def upsert_node(self, *, graph_entity_id, execution_id, now):
        existing = self._nodes.get(graph_entity_id.value)
        if existing is not None:
            return existing

        node = ProjectGraphNode(
            id=len(self._nodes) + 1,
            project_id=graph_entity_id.project_id,
            graph_entity_id=graph_entity_id,
            entity_type=graph_entity_id.entity_type,
            canonical_id=graph_entity_id.canonical_id,
            properties=GraphNodeProperties(),
            created_by_execution_id=execution_id,
            updated_by_execution_id=execution_id,
            created_at=now,
            updated_at=now,
        )
        self._nodes[graph_entity_id.value] = node

        return node

    def merge_node_property(
        self, *, graph_entity_id, attribute, value, execution_id, now
    ):
        existing = self._nodes.get(graph_entity_id.value)
        if existing is None:
            raise GraphNodeNotFoundError(
                graph_entity_id.project_id,
                graph_entity_id,
            )

        updated = replace(
            existing,
            properties=existing.properties.merged_with(attribute, value),
            updated_by_execution_id=execution_id,
            updated_at=now,
        )
        self._nodes[graph_entity_id.value] = updated

        return updated

    def upsert_relationship(
        self,
        *,
        source_entity_id,
        relationship_type,
        target_entity_id,
        execution_id,
        now,
    ):
        if source_entity_id.value not in self._nodes:
            raise GraphNodeNotFoundError(
                source_entity_id.project_id, source_entity_id
            )
        if target_entity_id.value not in self._nodes:
            raise GraphNodeNotFoundError(
                target_entity_id.project_id, target_entity_id
            )

        key = (
            f"{source_entity_id.value}-{relationship_type.value}->"
            f"{target_entity_id.value}"
        )
        existing = self._relationships.get(key)
        if existing is not None:
            return existing

        relationship = ProjectGraphRelationship(
            id=len(self._relationships) + 1,
            project_id=source_entity_id.project_id,
            source_entity_id=source_entity_id,
            relationship_type=relationship_type,
            target_entity_id=target_entity_id,
            properties=GraphRelationshipProperties(),
            created_by_execution_id=execution_id,
            updated_by_execution_id=execution_id,
            created_at=now,
            updated_at=now,
        )
        self._relationships[key] = relationship

        return relationship

    def get_node(self, project_id, graph_entity_id):
        return self._nodes.get(graph_entity_id.value)

    def list_nodes(self, project_id):
        return [
            node
            for node in self._nodes.values()
            if node.project_id == project_id
        ]

    def list_relationships(self, project_id):
        return [
            relationship
            for relationship in self._relationships.values()
            if relationship.project_id == project_id
        ]

    def list_outgoing_relationships(self, project_id, graph_entity_id):
        return [
            relationship
            for relationship in self._relationships.values()
            if relationship.source_entity_id.value == graph_entity_id.value
        ]

    def list_incoming_relationships(self, project_id, graph_entity_id):
        return [
            relationship
            for relationship in self._relationships.values()
            if relationship.target_entity_id.value == graph_entity_id.value
        ]

    def snapshot(self) -> dict[str, ProjectGraphNode]:
        return dict(self._nodes)

    def clear(self) -> None:
        self._nodes.clear()
        self._relationships.clear()


class FakeProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[int, Project] = {}

    def register(self, project: Project) -> None:
        self._projects[project.id] = project  # type: ignore[index]

    def get_by_id(self, project_id: int) -> Project | None:
        return self._projects.get(project_id)

    def get_by_code(self, code: str) -> Project | None:
        raise NotImplementedError

    def save(self, project: Project) -> Project:
        raise NotImplementedError

    def list_all(self, *, include_deleted: bool = False):
        raise NotImplementedError


class FakeGraphUnitOfWork(GraphUnitOfWork):
    def __init__(self, graph_store: FakeGraphStore) -> None:
        self._graph_store = graph_store
        self.commits = 0
        self.rollbacks = 0
        self._snapshot_before_commit: dict | None = None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
        self._graph_store.clear()


def _project(project_id: int = 10) -> Project:
    return replace(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        ),
        id=project_id,
        lifecycle_state=ProjectLifecycleState.ACTIVE,
    )


def _cable() -> GraphEntityId:
    return GraphEntityId(project_id=10, entity_type="CABLE", canonical_id="C-295")


def _transformer() -> GraphEntityId:
    return GraphEntityId(
        project_id=10, entity_type="TRANSFORMER", canonical_id="TR-02"
    )


def _relationship_batch(batch_id: int = 1) -> GraphOperationBatch:
    return GraphOperationBatch(
        id=batch_id,
        project_id=10,
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.PROJECT,
            scope_id=10,
        ),
        operations=(
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=_cable(),
                attribute=None,
                value=None,
                source_fact_id=1,
            ),
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=_transformer(),
                attribute=None,
                value=None,
                source_fact_id=1,
            ),
            GraphRelationshipOperation(
                kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
                subject_id=_cable(),
                relationship_type=GraphRelationshipType(value="FEEDS"),
                object_id=_transformer(),
                source_fact_id=1,
            ),
        ),
        created_at=CREATED_AT,
    )


@pytest.fixture()
def env():
    batch_repository = FakeGraphOperationBatchRepository()
    execution_repository = FakeGraphExecutionRepository()
    graph_store = FakeGraphStore()
    project_repository = FakeProjectRepository()
    unit_of_work = FakeGraphUnitOfWork(graph_store)

    return (
        batch_repository,
        execution_repository,
        graph_store,
        project_repository,
        unit_of_work,
    )


def test_execute_batch_applies_operations_in_order(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(_relationship_batch())

    result = graph_execution_service.execute_batch(
        batch_repository,
        execution_repository,
        graph_store,
        project_repository,
        unit_of_work,
        batch_id=1,
        now=CREATED_AT,
    )

    assert result.created is True
    assert result.execution.status is GraphExecutionStatus.SUCCEEDED
    assert result.execution.operation_count == 3
    assert [r.succeeded for r in result.execution.operation_results] == [
        True,
        True,
        True,
    ]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0
    assert len(graph_store.list_relationships(10)) == 1


def test_execute_batch_retry_of_the_same_batch_is_idempotent(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(_relationship_batch())

    first = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )
    second = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )

    assert first.created is True
    assert second.created is False
    assert first.execution.id == second.execution.id
    assert unit_of_work.commits == 1


def test_execute_batch_for_a_different_batch_with_identical_content_is_idempotent(
    env,
) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(_relationship_batch(batch_id=1))
    batch_repository.register(_relationship_batch(batch_id=2))

    first = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )
    second = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=2, now=CREATED_AT,
    )

    assert first.created is True
    assert second.created is False
    assert second.execution.batch_id == first.execution.batch_id


def test_execute_batch_raises_for_an_unknown_batch(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env

    with pytest.raises(GraphOperationBatchNotFoundError):
        graph_execution_service.execute_batch(
            batch_repository, execution_repository, graph_store,
            project_repository, unit_of_work, batch_id=999, now=CREATED_AT,
        )


def test_execute_batch_raises_for_a_batch_without_a_project(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    batch_repository.register(
        GraphOperationBatch(
            id=1,
            project_id=None,
            source=GraphOperationBatchSource(
                scope=GraphOperationBatchScope.DOCUMENT,
                scope_id=99,
            ),
            operations=(),
            created_at=CREATED_AT,
        )
    )

    with pytest.raises(BatchMissingProjectError):
        graph_execution_service.execute_batch(
            batch_repository, execution_repository, graph_store,
            project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
        )


def test_execute_batch_raises_for_an_archived_project(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(
        replace(_project(), lifecycle_state=ProjectLifecycleState.ARCHIVED)
    )
    batch_repository.register(_relationship_batch())

    with pytest.raises(ProjectNotGraphExecutableError):
        graph_execution_service.execute_batch(
            batch_repository, execution_repository, graph_store,
            project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
        )


def test_execute_batch_with_an_unsupported_operation_rolls_back_and_records_failure(
    env,
) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(
        GraphOperationBatch(
            id=1,
            project_id=10,
            source=GraphOperationBatchSource(
                scope=GraphOperationBatchScope.PROJECT,
                scope_id=10,
            ),
            operations=(
                GraphNodeOperation(
                    kind=GraphNodeOperationKind.CREATE_NODE,
                    entity_id=_cable(),
                    attribute=None,
                    value=None,
                    source_fact_id=1,
                ),
                GraphRelationshipOperation(
                    kind=GraphRelationshipOperationKind.SUPERSEDE_RELATIONSHIP,
                    subject_id=_cable(),
                    relationship_type=GraphRelationshipType(value="FEEDS"),
                    object_id=_transformer(),
                    source_fact_id=1,
                ),
            ),
            created_at=CREATED_AT,
        )
    )

    result = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )

    assert result.execution.status is GraphExecutionStatus.FAILED
    assert result.execution.failure_type == "UnsupportedGraphOperationError"
    assert unit_of_work.rollbacks == 1
    # Complete rollback: the CREATE_NODE that ran before the failing
    # operation must not survive.
    assert graph_store.list_nodes(10) == []


def test_execute_batch_missing_relationship_endpoint_rolls_back(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(
        GraphOperationBatch(
            id=1,
            project_id=10,
            source=GraphOperationBatchSource(
                scope=GraphOperationBatchScope.PROJECT,
                scope_id=10,
            ),
            operations=(
                GraphNodeOperation(
                    kind=GraphNodeOperationKind.CREATE_NODE,
                    entity_id=_cable(),
                    attribute=None,
                    value=None,
                    source_fact_id=1,
                ),
                GraphRelationshipOperation(
                    kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
                    subject_id=_cable(),
                    relationship_type=GraphRelationshipType(value="FEEDS"),
                    object_id=_transformer(),
                    source_fact_id=1,
                ),
            ),
            created_at=CREATED_AT,
        )
    )

    result = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )

    assert result.execution.status is GraphExecutionStatus.FAILED
    assert result.execution.failure_type == "GraphNodeNotFoundError"
    assert graph_store.list_nodes(10) == []


def test_execute_batch_with_no_operations_succeeds_trivially(env) -> None:
    batch_repository, execution_repository, graph_store, project_repository, unit_of_work = env
    project_repository.register(_project())
    batch_repository.register(
        GraphOperationBatch(
            id=1,
            project_id=10,
            source=GraphOperationBatchSource(
                scope=GraphOperationBatchScope.PROJECT,
                scope_id=10,
            ),
            operations=(),
            created_at=CREATED_AT,
        )
    )

    result = graph_execution_service.execute_batch(
        batch_repository, execution_repository, graph_store,
        project_repository, unit_of_work, batch_id=1, now=CREATED_AT,
    )

    assert result.execution.status is GraphExecutionStatus.SUCCEEDED
    assert result.execution.operation_count == 0
