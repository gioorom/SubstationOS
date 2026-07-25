from __future__ import annotations

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
from app.domain.project_knowledge_graph.graph_execution_validator import (
    GraphExecutionValidator,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    BatchMissingProjectError,
    MalformedGraphOperationError,
    TransientBatchNotExecutableError,
    UnsupportedGraphOperationError,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _entity(canonical_id: str = "C-295") -> GraphEntityId:
    return GraphEntityId(
        project_id=10,
        entity_type="CABLE",
        canonical_id=canonical_id,
    )


def test_validate_executable_batch_accepts_a_persisted_batch_with_a_project() -> (
    None
):
    batch = GraphOperationBatch(
        id=1,
        project_id=10,
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.PROJECT,
            scope_id=10,
        ),
        operations=(),
        created_at=CREATED_AT,
    )

    GraphExecutionValidator.validate_executable_batch(batch)


def test_validate_executable_batch_rejects_a_transient_batch() -> None:
    batch = GraphOperationBatch(
        id=None,
        project_id=None,
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.DOCUMENT,
            scope_id=5,
        ),
        operations=(),
        created_at=CREATED_AT,
    )

    with pytest.raises(TransientBatchNotExecutableError):
        GraphExecutionValidator.validate_executable_batch(batch)


def test_validate_executable_batch_rejects_a_batch_with_no_project() -> (
    None
):
    batch = GraphOperationBatch(
        id=1,
        project_id=None,
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.DOCUMENT,
            scope_id=5,
        ),
        operations=(),
        created_at=CREATED_AT,
    )

    with pytest.raises(BatchMissingProjectError):
        GraphExecutionValidator.validate_executable_batch(batch)


def test_validate_supported_operation_accepts_create_node() -> None:
    GraphExecutionValidator.validate_supported_operation(
        GraphNodeOperation(
            kind=GraphNodeOperationKind.CREATE_NODE,
            entity_id=_entity(),
            attribute=None,
            value=None,
            source_fact_id=1,
        )
    )


def test_validate_supported_operation_accepts_create_relationship() -> (
    None
):
    GraphExecutionValidator.validate_supported_operation(
        GraphRelationshipOperation(
            kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
            subject_id=_entity("C-295"),
            relationship_type=GraphRelationshipType(value="FEEDS"),
            object_id=_entity("TR-02"),
            source_fact_id=1,
        )
    )


def test_validate_supported_operation_rejects_update_relationship() -> (
    None
):
    with pytest.raises(UnsupportedGraphOperationError):
        GraphExecutionValidator.validate_supported_operation(
            GraphRelationshipOperation(
                kind=GraphRelationshipOperationKind.UPDATE_RELATIONSHIP,
                subject_id=_entity("C-295"),
                relationship_type=GraphRelationshipType(value="FEEDS"),
                object_id=_entity("TR-02"),
                source_fact_id=1,
            )
        )


def test_validate_supported_operation_rejects_a_malformed_update_node() -> (
    None
):
    with pytest.raises(MalformedGraphOperationError):
        GraphExecutionValidator.validate_supported_operation(
            GraphNodeOperation(
                kind=GraphNodeOperationKind.UPDATE_NODE,
                entity_id=_entity(),
                attribute=None,
                value=None,
                source_fact_id=1,
            )
        )
