from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import (
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperation,
    GraphOperationBatch,
    GraphRelationshipOperationKind,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    BatchMissingProjectError,
    MalformedGraphOperationError,
    TransientBatchNotExecutableError,
    UnsupportedGraphOperationError,
)

_SUPPORTED_NODE_KINDS = frozenset(
    {GraphNodeOperationKind.CREATE_NODE, GraphNodeOperationKind.UPDATE_NODE}
)

_SUPPORTED_RELATIONSHIP_KINDS = frozenset(
    {GraphRelationshipOperationKind.CREATE_RELATIONSHIP}
)


class GraphExecutionValidator:
    """
    Stateless validation rules for executing a ``GraphOperationBatch``.
    Whole-batch checks (``validate_executable_batch``) run once, before
    any operation is executed, and are request-level: they raise
    exceptions the router maps to an HTTP 4xx. Per-operation checks
    (``validate_supported_operation``) run for each operation and are
    execution-level: the service catches them, rolls the transaction
    back, and records a ``FAILED`` ``GraphExecution`` instead of
    propagating them.
    """

    @staticmethod
    def validate_executable_batch(batch: GraphOperationBatch) -> None:
        if batch.id is None:
            raise TransientBatchNotExecutableError()

        if batch.project_id is None:
            raise BatchMissingProjectError(batch.id)

    @staticmethod
    def validate_supported_operation(operation: GraphOperation) -> None:
        if isinstance(operation, GraphNodeOperation):
            if operation.kind not in _SUPPORTED_NODE_KINDS:
                raise UnsupportedGraphOperationError(operation.kind.value)

            if (
                operation.kind is GraphNodeOperationKind.UPDATE_NODE
                and (operation.attribute is None or operation.value is None)
            ):
                raise MalformedGraphOperationError(
                    operation.kind.value,
                    "an UPDATE_NODE operation requires both an "
                    "attribute and a value",
                )

            return

        if operation.kind not in _SUPPORTED_RELATIONSHIP_KINDS:
            raise UnsupportedGraphOperationError(operation.kind.value)
