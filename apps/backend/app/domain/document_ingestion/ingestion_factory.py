"""
Builds and advances ``IngestionJob`` values (CLAUDE.md §4.2 - a factory
enforces invariants at construction time).

Every state change goes through ``transition_to``, which validates the
move against the lifecycle table and raises on an illegal one. There is
no other way to change a job's state: the dataclass is frozen, so a
caller cannot quietly assign one.

Pure and deterministic - ``now`` is always caller-supplied, never read
from the wall clock.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.document_ingestion.ingestion_exceptions import (
    InvalidIngestionTransitionError,
)
from app.domain.document_ingestion.ingestion_lifecycle import (
    IngestionState,
    is_transition_valid,
)
from app.domain.document_ingestion.ingestion_models import (
    IngestedDocumentSnapshot,
    IngestionFailure,
    IngestionJob,
    IngestionOutcome,
    IngestionPipelineResult,
)
from app.domain.document_ingestion.ingestion_policy import (
    INGESTION_PIPELINE_VERSION,
)


class IngestionJobFactory:
    @staticmethod
    def create(
        *,
        project_id: int | None,
        document_id: int,
        now: datetime,
        pipeline_version: str = INGESTION_PIPELINE_VERSION,
    ) -> IngestionJob:
        """A new job always starts ``UPLOADED``. It is never created
        already queued: "accepted" and "scheduled" are separate facts, and
        collapsing them would lose the moment a request was taken."""

        return IngestionJob(
            id=None,
            project_id=project_id,
            document_id=document_id,
            state=IngestionState.UPLOADED,
            pipeline_version=pipeline_version,
            created_at=now,
            updated_at=now,
        )


def transition_to(
    job: IngestionJob, target: IngestionState, *, now: datetime
) -> IngestionJob:
    """The only way a job's state changes. Raises
    ``InvalidIngestionTransitionError`` on an illegal move rather than
    tolerating it."""

    if not is_transition_valid(job.state, target):
        raise InvalidIngestionTransitionError(job.id, job.state, target)

    return replace(job, state=target, updated_at=now)


def queue(job: IngestionJob, *, now: datetime) -> IngestionJob:
    return transition_to(job, IngestionState.QUEUED, now=now)


def start_processing(job: IngestionJob, *, now: datetime) -> IngestionJob:
    return transition_to(job, IngestionState.PROCESSING, now=now)


def complete(
    job: IngestionJob, result: IngestionPipelineResult, *, now: datetime
) -> IngestionJob:
    """
    Writes one pipeline execution's conclusion onto the job, moving it to
    its terminal state.

    The pipeline's own outcome decides which terminal state that is - this
    function never re-judges it. A successful result carries a document
    snapshot and no failure; a failed one carries a failure and whatever
    snapshot was collected before the failure, so a reader can see how far
    the pipeline got.
    """

    target = (
        IngestionState.PROCESSED
        if result.succeeded
        else IngestionState.FAILED
    )
    advanced = transition_to(job, target, now=now)

    return replace(
        advanced,
        outcome=result.outcome,
        failure=result.failure,
        document=result.document,
        pipeline_version=result.pipeline_version,
        completed_at=now,
    )


def retry(job: IngestionJob, *, now: datetime) -> IngestionJob:
    """
    Returns a failed job to the queue for another attempt.

    The same job rather than a new one: the attempt history belongs to the
    record an engineer is already looking at. The previous failure and
    completion timestamp are cleared, because they describe the attempt
    that is now being replaced - but ``attempt_count`` remembers that it
    happened.
    """

    advanced = transition_to(job, IngestionState.QUEUED, now=now)

    return replace(
        advanced,
        attempt_count=job.attempt_count + 1,
        outcome=None,
        failure=None,
        completed_at=None,
    )


def with_snapshot(
    job: IngestionJob, snapshot: IngestedDocumentSnapshot
) -> IngestionJob:
    return replace(job, document=snapshot)


def failed_result(
    failure: IngestionFailure,
    *,
    document: IngestedDocumentSnapshot | None = None,
    pipeline_version: str = INGESTION_PIPELINE_VERSION,
) -> IngestionPipelineResult:
    return IngestionPipelineResult(
        outcome=IngestionOutcome.FAILED,
        pipeline_version=pipeline_version,
        document=document,
        failure=failure,
    )
