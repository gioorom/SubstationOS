"""
The ingestion lifecycle (EPIC 2, Milestone 25.1) - the explicit,
deterministic record of where one document stands on its way to being
extractable.

Modelled on ``project_lifecycle.py``'s own shape: a state enum, an
explicit ``VALID_TRANSITIONS`` table, and one predicate. Nothing infers a
transition and nothing skips one - a job that reached ``PROCESSED``
without passing through ``PROCESSING`` would be a record of something
that never happened.

This module holds **no orchestration**. It says which moves are legal;
``ingestion_pipeline.py`` decides which to make.
"""

from __future__ import annotations

from enum import Enum


class IngestionState(str, Enum):
    """
    Where one ingestion job stands.

    ``UPLOADED`` is the state a job is *created* in, not a property of the
    document: the document was already uploaded before any job existed,
    and this records that a job now exists for it and has not yet been
    queued. Keeping it distinct from ``QUEUED`` means "accepted" and
    "scheduled" never become the same fact.

    ``PROCESSED`` and ``FAILED`` are the two terminal outcomes. There is
    deliberately no ``CANCELLED``: nothing in this milestone can cancel a
    job, and a state nothing can reach would be a false promise.
    """

    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# The legal moves, and only these.
#
# UPLOADED -> QUEUED -> PROCESSING -> PROCESSED
#                                  -> FAILED -> QUEUED   (retry)
#
# PROCESSED is terminal: a document that needs ingesting again gets a new
# job, so the record of what was processed when is never overwritten.
# FAILED is terminal *unless retried*, and a retry returns the same job to
# the queue rather than creating a second one - the attempt history
# belongs to the job an engineer is already looking at.
VALID_TRANSITIONS: dict[IngestionState, frozenset[IngestionState]] = {
    IngestionState.UPLOADED: frozenset({IngestionState.QUEUED}),
    IngestionState.QUEUED: frozenset({IngestionState.PROCESSING}),
    IngestionState.PROCESSING: frozenset(
        {IngestionState.PROCESSED, IngestionState.FAILED}
    ),
    IngestionState.PROCESSED: frozenset(),
    IngestionState.FAILED: frozenset({IngestionState.QUEUED}),
}

# States in which a job is still on its way somewhere. A document with a
# job in any of these must not accept a second request - see
# ``DuplicateIngestionRequestError``.
ACTIVE_STATES: frozenset[IngestionState] = frozenset(
    {
        IngestionState.UPLOADED,
        IngestionState.QUEUED,
        IngestionState.PROCESSING,
    }
)

# States from which nothing further happens on its own.
TERMINAL_STATES: frozenset[IngestionState] = frozenset(
    {IngestionState.PROCESSED, IngestionState.FAILED}
)


def is_transition_valid(
    current: IngestionState, target: IngestionState
) -> bool:
    return target in VALID_TRANSITIONS[current]


def is_active(state: IngestionState) -> bool:
    return state in ACTIVE_STATES
