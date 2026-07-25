from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperationBatchScope,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
    GraphRelationshipType,
)
from app.domain.project_knowledge_graph.graph_execution_fingerprint import (
    compute_batch_fingerprint,
)


def _node_op(source_fact_id: int = 1) -> GraphNodeOperation:
    return GraphNodeOperation(
        kind=GraphNodeOperationKind.CREATE_NODE,
        entity_id=GraphEntityId(
            project_id=10,
            entity_type="CABLE",
            canonical_id="C-295",
        ),
        attribute=None,
        value=None,
        source_fact_id=source_fact_id,
    )


def test_fingerprint_is_deterministic_across_calls() -> None:
    operations = (_node_op(),)

    first = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=operations,
    )
    second = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=operations,
    )

    assert first == second


def test_fingerprint_ignores_source_fact_id() -> None:
    first = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(source_fact_id=1),),
    )
    second = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(source_fact_id=999),),
    )

    assert first == second


def test_fingerprint_differs_for_different_operation_content() -> None:
    base = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(),),
    )

    different_entity = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=GraphEntityId(
                    project_id=10,
                    entity_type="TRANSFORMER",
                    canonical_id="TR-02",
                ),
                attribute=None,
                value=None,
                source_fact_id=1,
            ),
        ),
    )

    assert base != different_entity


def test_fingerprint_differs_for_different_scope_id() -> None:
    a = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(),),
    )
    b = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.DOCUMENT,
        scope_id=5,
        operations=(_node_op(),),
    )

    assert a != b


def test_fingerprint_accounts_for_relationship_operations() -> None:
    relationship = GraphRelationshipOperation(
        kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
        subject_id=GraphEntityId(
            project_id=10,
            entity_type="CABLE",
            canonical_id="C-295",
        ),
        relationship_type=GraphRelationshipType(value="FEEDS"),
        object_id=GraphEntityId(
            project_id=10,
            entity_type="TRANSFORMER",
            canonical_id="TR-02",
        ),
        source_fact_id=1,
    )

    with_relationship = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(), relationship),
    )
    without_relationship = compute_batch_fingerprint(
        project_id=10,
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=10,
        operations=(_node_op(),),
    )

    assert with_relationship != without_relationship
