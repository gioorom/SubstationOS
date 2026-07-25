"""
Deterministic content fingerprinting for a ``GraphOperationBatch``,
used to make batch execution idempotent (see ``graph_execution_service``).
Two batches - the same batch retried, or two different batches whose
operations have identical semantic effect - must fingerprint identically;
two batches whose effect differs even in one operation must not.

Deliberately excludes anything that is not part of an operation's
semantic effect: ``source_fact_id`` (which Canonical Fact happened to
produce an operation does not change what the operation does to the
graph), and no random id or timestamp is included anywhere.
"""

from __future__ import annotations

import hashlib
import json

from app.domain.graph_builder.graph_builder_models import (
    GraphNodeOperation,
    GraphOperation,
    GraphOperationBatchScope,
)


def _operation_payload(operation: GraphOperation) -> dict[str, str | None]:
    if isinstance(operation, GraphNodeOperation):
        return {
            "category": "node",
            "kind": operation.kind.value,
            "entity_id": operation.entity_id.value,
            "attribute": operation.attribute,
            "value": operation.value,
        }

    return {
        "category": "relationship",
        "kind": operation.kind.value,
        "subject_id": operation.subject_id.value,
        "relationship_type": operation.relationship_type.value,
        "object_id": operation.object_id.value,
    }


def compute_batch_fingerprint(
    *,
    project_id: int,
    scope: GraphOperationBatchScope,
    scope_id: int,
    operations: tuple[GraphOperation, ...],
) -> str:
    payload = {
        "project_id": project_id,
        "scope": scope.value,
        "scope_id": scope_id,
        "operations": [
            _operation_payload(operation) for operation in operations
        ],
    }
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
