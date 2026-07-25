"""
Application services for Project Knowledge Graph Persistence (Milestone
11.2). Each function is a single use case, orchestrating the domain
(``app.domain.project_knowledge_graph``) through the ``GraphStore``,
``GraphExecutionRepository``, and ``GraphUnitOfWork`` ports, together
with Graph Builder's own ``GraphOperationBatchRepository`` (read-only)
and the Project bounded context's ``ProjectRepository`` (read-only) -
never a raw database session.

This module executes the operations a ``GraphOperationBatch`` already
contains. It does not canonicalize raw values, interpret Proposed
Claims, inspect Review Workflow, or rebuild operations - it trusts
Graph Builder's translation completely and only applies it.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperation,
)
from app.domain.graph_builder.graph_operation_batch_repository import (
    GraphOperationBatchRepository,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.project_knowledge_graph.graph_execution_factory import (
    GraphExecutionFactory,
)
from app.domain.project_knowledge_graph.graph_execution_fingerprint import (
    compute_batch_fingerprint,
)
from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecution,
    GraphExecutionResult,
    GraphOperationExecutionResult,
)
from app.domain.project_knowledge_graph.graph_execution_repository import (
    GraphExecutionRepository,
)
from app.domain.project_knowledge_graph.graph_execution_validator import (
    GraphExecutionValidator,
)
from app.domain.project_knowledge_graph.graph_node_models import (
    ProjectGraphNode,
)
from app.domain.project_knowledge_graph.graph_relationship_models import (
    ProjectGraphRelationship,
)
from app.domain.project_knowledge_graph.graph_store import GraphStore
from app.domain.project_knowledge_graph.graph_unit_of_work import (
    GraphUnitOfWork,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    GraphExecutionNotFoundError,
    GraphExecutionOperationError,
    GraphExecutionProjectNotFoundError,
    GraphNodeNotFoundError,
    GraphOperationBatchNotFoundError,
    ProjectNotGraphExecutableError,
)


def _require_graph_executable_project(
    project_repository: ProjectRepository,
    project_id: int,
) -> None:
    project = project_repository.get_by_id(project_id)

    if project is None:
        raise GraphExecutionProjectNotFoundError(project_id)

    if not project.is_mutable():
        raise ProjectNotGraphExecutableError(
            project.id,  # type: ignore[arg-type]
            project.lifecycle_state,
        )


def _execute_operation(
    graph_store: GraphStore,
    operation: GraphOperation,
    *,
    execution_id: int,
    now: datetime,
) -> str:
    GraphExecutionValidator.validate_supported_operation(operation)

    if isinstance(operation, GraphNodeOperation):
        if operation.kind is GraphNodeOperationKind.CREATE_NODE:
            node = graph_store.upsert_node(
                graph_entity_id=operation.entity_id,
                execution_id=execution_id,
                now=now,
            )

            return f"node '{node.graph_entity_id.value}' ensured"

        node = graph_store.merge_node_property(
            graph_entity_id=operation.entity_id,
            attribute=operation.attribute,  # type: ignore[arg-type]
            value=operation.value,  # type: ignore[arg-type]
            execution_id=execution_id,
            now=now,
        )

        return (
            f"node '{node.graph_entity_id.value}'."
            f"{operation.attribute} set"
        )

    relationship = graph_store.upsert_relationship(
        source_entity_id=operation.subject_id,
        relationship_type=operation.relationship_type,
        target_entity_id=operation.object_id,
        execution_id=execution_id,
        now=now,
    )

    return (
        f"relationship '{relationship.source_entity_id.value}' "
        f"-{relationship.relationship_type.value}-> "
        f"'{relationship.target_entity_id.value}' ensured"
    )


def execute_batch(
    batch_repository: GraphOperationBatchRepository,
    execution_repository: GraphExecutionRepository,
    graph_store: GraphStore,
    project_repository: ProjectRepository,
    unit_of_work: GraphUnitOfWork,
    *,
    batch_id: int,
    now: datetime,
) -> GraphExecutionResult:
    """
    Executes every operation in a persisted ``GraphOperationBatch``,
    atomically: either every operation is applied and one ``SUCCEEDED``
    ``GraphExecution`` is recorded, or none is (a full rollback) and one
    ``FAILED`` ``GraphExecution`` is recorded instead.

    Idempotent by batch content, not by batch id: retrying the same
    batch, or executing a different batch with identical semantic
    content, returns the existing ``SUCCEEDED`` execution
    (``created=False``) without reapplying anything.

    Raises (request-level, mapped to an HTTP 4xx by the router):
    ``GraphOperationBatchNotFoundError``, ``TransientBatchNotExecutableError``,
    ``BatchMissingProjectError``, ``GraphExecutionProjectNotFoundError``,
    ``ProjectNotGraphExecutableError``. Never raises for an
    operation-level failure (unsupported kind, missing endpoint, absent
    node) - that is recorded as a ``FAILED`` execution and returned
    normally.
    """

    batch = batch_repository.get_by_id(batch_id)

    if batch is None:
        raise GraphOperationBatchNotFoundError(batch_id)

    GraphExecutionValidator.validate_executable_batch(batch)
    _require_graph_executable_project(
        project_repository,
        batch.project_id,  # type: ignore[arg-type]
    )

    fingerprint = compute_batch_fingerprint(
        project_id=batch.project_id,  # type: ignore[arg-type]
        scope=batch.source.scope,
        scope_id=batch.source.scope_id,
        operations=batch.operations,
    )

    existing = execution_repository.get_successful_by_fingerprint(
        fingerprint
    )

    if existing is not None:
        return GraphExecutionResult(execution=existing, created=False)

    pending = GraphExecutionFactory.start(
        batch_id=batch.id,  # type: ignore[arg-type]
        batch_fingerprint=fingerprint,
        project_id=batch.project_id,  # type: ignore[arg-type]
        operation_count=len(batch.operations),
        now=now,
    )
    saved_pending = execution_repository.save(pending)

    operation_results: list[GraphOperationExecutionResult] = []

    try:
        for sequence, operation in enumerate(batch.operations):
            detail = _execute_operation(
                graph_store,
                operation,
                execution_id=saved_pending.id,  # type: ignore[arg-type]
                now=now,
            )
            operation_results.append(
                GraphOperationExecutionResult(
                    sequence=sequence,
                    kind=operation.kind.value,
                    succeeded=True,
                    detail=detail,
                )
            )

        succeeded = GraphExecutionFactory.succeed(
            saved_pending,
            operation_results=tuple(operation_results),
            now=now,
        )
        final = execution_repository.update(succeeded)
        unit_of_work.commit()

        return GraphExecutionResult(execution=final, created=True)
    except GraphExecutionOperationError as error:
        unit_of_work.rollback()

        failed_sequence = len(operation_results)
        operation_results.append(
            GraphOperationExecutionResult(
                sequence=failed_sequence,
                kind=batch.operations[failed_sequence].kind.value,
                succeeded=False,
                detail=str(error),
            )
        )

        failed = GraphExecutionFactory.fail(
            batch_id=batch.id,  # type: ignore[arg-type]
            batch_fingerprint=fingerprint,
            project_id=batch.project_id,  # type: ignore[arg-type]
            operation_count=len(batch.operations),
            started_at=now,
            completed_at=now,
            failure_type=type(error).__name__,
            failure_message=str(error),
            operation_results=tuple(operation_results),
        )
        persisted = execution_repository.save(failed)
        unit_of_work.commit()

        return GraphExecutionResult(execution=persisted, created=True)


def get_execution(
    execution_repository: GraphExecutionRepository,
    execution_id: int,
) -> GraphExecution:
    execution = execution_repository.get_by_id(execution_id)

    if execution is None:
        raise GraphExecutionNotFoundError(execution_id)

    return execution


def list_executions_for_batch(
    execution_repository: GraphExecutionRepository,
    batch_id: int,
) -> list[GraphExecution]:
    return execution_repository.list_by_batch(batch_id)


def get_graph_node(
    graph_store: GraphStore,
    project_id: int,
    graph_entity_id: GraphEntityId,
) -> ProjectGraphNode:
    node = graph_store.get_node(project_id, graph_entity_id)

    if node is None:
        raise GraphNodeNotFoundError(project_id, graph_entity_id)

    return node


def list_graph_nodes(
    graph_store: GraphStore,
    project_id: int,
) -> list[ProjectGraphNode]:
    return graph_store.list_nodes(project_id)


def list_graph_relationships(
    graph_store: GraphStore,
    project_id: int,
) -> list[ProjectGraphRelationship]:
    return graph_store.list_relationships(project_id)


def list_outgoing_relationships(
    graph_store: GraphStore,
    project_id: int,
    graph_entity_id: GraphEntityId,
) -> list[ProjectGraphRelationship]:
    return graph_store.list_outgoing_relationships(
        project_id,
        graph_entity_id,
    )


def list_incoming_relationships(
    graph_store: GraphStore,
    project_id: int,
    graph_entity_id: GraphEntityId,
) -> list[ProjectGraphRelationship]:
    return graph_store.list_incoming_relationships(
        project_id,
        graph_entity_id,
    )
