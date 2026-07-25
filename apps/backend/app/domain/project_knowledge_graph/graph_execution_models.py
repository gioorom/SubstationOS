from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class GraphExecutionStatus(str, Enum):
    """
    The lifecycle state of one attempt to execute a
    ``GraphOperationBatch``. Execution runs synchronously in this
    milestone, but the status is represented explicitly (rather than
    only ever observed as a final outcome) so a future asynchronous job
    processor can adopt this same model without a schema change -
    ``PENDING`` is a real, reachable state, not a placeholder.
    """

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GraphOperationExecutionResult:
    """
    The outcome of executing one operation within a
    ``GraphOperationBatch``, in batch order. ``detail`` is a short,
    human-readable note (e.g. "created", "already existed", or the
    failure that stopped execution) - never a copy of the operation's
    own payload, which the caller can already see on the batch itself.
    """

    sequence: int
    kind: str
    succeeded: bool
    detail: str | None


@dataclass(frozen=True, slots=True)
class GraphExecution:
    """
    The immutable audit record of one attempt to execute a
    ``GraphOperationBatch`` against the Project Knowledge Graph.
    ``batch_fingerprint`` is the deterministic content fingerprint
    (``graph_execution_fingerprint.compute_batch_fingerprint``) used to
    detect that a batch - this one or a different one with identical
    semantic content - has already been successfully executed.

    "Immutable" here follows this codebase's established meaning
    (CLAUDE.md SS6): the dataclass itself is frozen, and a lifecycle
    transition (``GraphExecutionFactory.succeed``/``fail``) returns a
    new instance rather than mutating one in place - it does not mean
    ``PENDING`` can never become ``SUCCEEDED``/``FAILED``, only that
    each state is its own value, and a *terminal* state is never
    further edited.
    """

    id: int | None
    batch_id: int
    batch_fingerprint: str
    project_id: int
    status: GraphExecutionStatus
    started_at: datetime
    completed_at: datetime | None
    operation_count: int
    failure_type: str | None
    failure_message: str | None
    operation_results: tuple[GraphOperationExecutionResult, ...]


@dataclass(frozen=True, slots=True)
class GraphExecutionResult:
    """
    The outcome of requesting execution of a batch: the resulting
    ``GraphExecution``, and whether this call actually executed the
    batch (``created=True``) or idempotently returned an already-
    successful execution for the same logical batch content
    (``created=False``, per the batch fingerprint) without reapplying
    any mutation.
    """

    execution: GraphExecution
    created: bool
