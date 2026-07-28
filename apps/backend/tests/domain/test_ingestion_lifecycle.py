"""
Domain tests for the ingestion lifecycle and pipeline (Milestone 25.1).

The lifecycle is the whole point of the milestone, so it is tested
exhaustively: **every** state pair is asserted legal or illegal, rather
than a handful of happy paths.

Pure and fast: no I/O, no database, no provider.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.document_ingestion import ingestion_factory
from app.domain.document_ingestion.ingestion_exceptions import (
    InvalidIngestionTransitionError,
)
from app.domain.document_ingestion.ingestion_lifecycle import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    IngestionState,
    is_active,
    is_transition_valid,
)
from app.domain.document_ingestion.ingestion_models import (
    IngestionFailure,
    IngestionFailureCode,
    IngestionOutcome,
)
from app.domain.document_ingestion.ingestion_pipeline import (
    execute_ingestion_pipeline,
)
from app.domain.document_ingestion.ingestion_policy import (
    INGESTION_PIPELINE_VERSION,
    SUPPORTED_INGESTION_FORMATS,
    is_supported_format,
)
from app.domain.engineering_index.document_metadata import DocumentMetadata
from app.domain.project.project_document_scope import DocumentScope

# A value no schema version of this system has ever defined - the only
# thing UNSUPPORTED_FORMAT claims.
UNDEFINED_FORMAT = "quantum_hologram"

NOW = datetime(2026, 1, 1, 9, 0, 0)
LATER = datetime(2026, 1, 1, 9, 5, 0)

# Every legal move, spelled out here independently of the table under
# test - a test that read VALID_TRANSITIONS to check VALID_TRANSITIONS
# would assert nothing.
LEGAL_TRANSITIONS = {
    (IngestionState.UPLOADED, IngestionState.QUEUED),
    (IngestionState.QUEUED, IngestionState.PROCESSING),
    (IngestionState.PROCESSING, IngestionState.PROCESSED),
    (IngestionState.PROCESSING, IngestionState.FAILED),
    (IngestionState.FAILED, IngestionState.QUEUED),
}


def _metadata(**overrides) -> DocumentMetadata:
    defaults = dict(
        document_id=10,
        project_id=1,
        title="montante-T2-schema.pdf",
        document_format="pdf",
        document_category="functional_schematic",
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    defaults.update(overrides)

    return DocumentMetadata(**defaults)


def _job(state: IngestionState = IngestionState.UPLOADED):
    job = ingestion_factory.IngestionJobFactory.create(
        project_id=1, document_id=10, now=NOW
    )

    from dataclasses import replace

    return replace(job, id=1, state=state)


# --- The transition table, exhaustively ------------------------------------


@pytest.mark.parametrize("current", list(IngestionState))
@pytest.mark.parametrize("target", list(IngestionState))
def test_every_state_pair_is_legal_or_illegal_as_declared(
    current: IngestionState, target: IngestionState
) -> None:
    expected = (current, target) in LEGAL_TRANSITIONS

    assert is_transition_valid(current, target) is expected


def test_every_state_has_a_transition_entry() -> None:
    """A state missing from the table would raise a KeyError at the worst
    possible moment rather than reporting an illegal move."""

    assert set(VALID_TRANSITIONS) == set(IngestionState)


def test_processed_is_terminal() -> None:
    """A document needing ingestion again gets a new job, so what was
    processed when is never overwritten."""

    assert VALID_TRANSITIONS[IngestionState.PROCESSED] == frozenset()


def test_a_job_can_never_skip_processing() -> None:
    assert not is_transition_valid(
        IngestionState.QUEUED, IngestionState.PROCESSED
    )
    assert not is_transition_valid(
        IngestionState.UPLOADED, IngestionState.PROCESSING
    )


def test_no_state_transitions_to_itself() -> None:
    for state in IngestionState:
        assert not is_transition_valid(state, state)


def test_active_and_terminal_states_partition_the_lifecycle() -> None:
    assert ACTIVE_STATES | TERMINAL_STATES == set(IngestionState)
    assert not (ACTIVE_STATES & TERMINAL_STATES)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (IngestionState.UPLOADED, True),
        (IngestionState.QUEUED, True),
        (IngestionState.PROCESSING, True),
        (IngestionState.PROCESSED, False),
        (IngestionState.FAILED, False),
    ],
)
def test_is_active_reports_jobs_still_in_flight(
    state: IngestionState, expected: bool
) -> None:
    assert is_active(state) is expected


# --- The factory enforces the table ----------------------------------------


def test_a_new_job_starts_uploaded() -> None:
    """"Accepted" and "scheduled" are separate facts."""

    job = ingestion_factory.IngestionJobFactory.create(
        project_id=1, document_id=10, now=NOW
    )

    assert job.state is IngestionState.UPLOADED
    assert job.id is None
    assert job.attempt_count == 1
    assert job.outcome is None
    assert job.completed_at is None
    assert job.pipeline_version == INGESTION_PIPELINE_VERSION


def test_a_legal_transition_advances_the_job() -> None:
    queued = ingestion_factory.queue(_job(), now=LATER)

    assert queued.state is IngestionState.QUEUED
    assert queued.updated_at == LATER


def test_an_illegal_transition_raises() -> None:
    with pytest.raises(InvalidIngestionTransitionError):
        ingestion_factory.start_processing(_job(), now=LATER)


def test_a_terminal_job_cannot_advance() -> None:
    with pytest.raises(InvalidIngestionTransitionError):
        ingestion_factory.queue(
            _job(IngestionState.PROCESSED), now=LATER
        )


def test_transitions_never_mutate_the_original_job() -> None:
    job = _job()

    ingestion_factory.queue(job, now=LATER)

    assert job.state is IngestionState.UPLOADED


def test_completing_a_successful_run_records_the_outcome() -> None:
    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata()
    )
    completed = ingestion_factory.complete(
        _job(IngestionState.PROCESSING), result, now=LATER
    )

    assert completed.state is IngestionState.PROCESSED
    assert completed.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert completed.is_ready_for_extraction is True
    assert completed.failure is None
    assert completed.document is not None
    assert completed.completed_at == LATER


def test_completing_a_failed_run_records_the_failure() -> None:
    result = execute_ingestion_pipeline(document_id=10, metadata=None)
    completed = ingestion_factory.complete(
        _job(IngestionState.PROCESSING), result, now=LATER
    )

    assert completed.state is IngestionState.FAILED
    assert completed.outcome is IngestionOutcome.FAILED
    assert completed.is_ready_for_extraction is False
    assert completed.failure.code is (
        IngestionFailureCode.DOCUMENT_NOT_FOUND
    )


def test_retrying_a_failed_job_keeps_the_record_and_counts_the_attempt() -> (
    None
):
    from dataclasses import replace

    failed = replace(
        _job(IngestionState.FAILED),
        outcome=IngestionOutcome.FAILED,
        completed_at=NOW,
        failure=IngestionFailure(
            code=IngestionFailureCode.PIPELINE_EXECUTION_FAILURE,
            message="boom",
        ),
    )

    retried = ingestion_factory.retry(failed, now=LATER)

    assert retried.id == failed.id
    assert retried.state is IngestionState.QUEUED
    assert retried.attempt_count == 2
    # The previous attempt's conclusion is cleared - it describes the
    # attempt now being replaced - but that it happened is remembered.
    assert retried.outcome is None
    assert retried.failure is None
    assert retried.completed_at is None


def test_only_a_failed_job_can_be_retried() -> None:
    with pytest.raises(InvalidIngestionTransitionError):
        ingestion_factory.retry(
            _job(IngestionState.PROCESSED), now=LATER
        )


# --- The pipeline ------------------------------------------------------------


def test_a_supported_document_is_ready_for_extraction() -> None:
    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata()
    )

    assert result.succeeded is True
    assert result.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert result.failure is None
    assert result.pipeline_version == INGESTION_PIPELINE_VERSION


def test_the_snapshot_copies_repository_facts_and_derives_nothing() -> None:
    metadata = _metadata()

    snapshot = execute_ingestion_pipeline(
        document_id=10, metadata=metadata
    ).document

    assert snapshot.title == metadata.title
    assert snapshot.document_format == metadata.document_format
    assert snapshot.document_category == metadata.document_category
    assert snapshot.revision == metadata.revision
    assert snapshot.scope is metadata.scope
    assert snapshot.project_id == metadata.project_id


def test_a_missing_document_fails_with_document_not_found() -> None:
    result = execute_ingestion_pipeline(document_id=999, metadata=None)

    assert result.succeeded is False
    assert result.failure.code is (
        IngestionFailureCode.DOCUMENT_NOT_FOUND
    )
    assert result.document is None


def test_a_format_this_system_does_not_define_is_refused() -> None:
    """A data-integrity condition - a row written under a different schema
    version - not a judgement about a document."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(document_format=UNDEFINED_FORMAT),
    )

    assert result.succeeded is False
    assert result.failure.code is IngestionFailureCode.UNSUPPORTED_FORMAT
    # The snapshot is still carried, so a reader can see what was refused.
    assert result.document is not None
    assert result.document.document_format == UNDEFINED_FORMAT


def test_an_unclassified_document_ingests_normally() -> None:
    """``other`` is the value a document takes when nothing classified it -
    today's upload endpoint sets no format at all. Refusing it would mean
    judging a document on a field nobody ever filled in, which is the same
    absence-of-evidence error this system refuses everywhere else."""

    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata(document_format="other")
    )

    assert result.succeeded is True


@pytest.mark.parametrize("document_format", sorted(SUPPORTED_INGESTION_FORMATS))
def test_every_supported_format_is_treated_identically(
    document_format: str,
) -> None:
    """No drawing-specific behaviour: a DWG goes through exactly the same
    steps as a PDF."""

    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata(document_format=document_format)
    )

    assert result.succeeded is True


def test_every_format_the_repository_can_hold_is_ingestible() -> None:
    """A format added to the persistence enum must not silently become
    un-ingestible."""

    from app.models.document import DocumentFormat

    persisted = {member.value for member in DocumentFormat}

    assert SUPPORTED_INGESTION_FORMATS == persisted
    assert not is_supported_format(UNDEFINED_FORMAT)


def test_the_pipeline_is_deterministic() -> None:
    metadata = _metadata()

    assert execute_ingestion_pipeline(
        document_id=10, metadata=metadata
    ) == execute_ingestion_pipeline(document_id=10, metadata=metadata)


def test_a_canonical_library_document_is_ingestible() -> None:
    """Every document the repository manages is ingestible. Whether a
    canonical-library document may feed a *project's* index is the
    extractor's rule to apply (ADR-0005), and pre-judging it here would
    refuse a document this milestone has no basis to refuse."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(
            project_id=None, scope=DocumentScope.CANONICAL_LIBRARY
        ),
    )

    assert result.succeeded is True
    assert result.document.scope is DocumentScope.CANONICAL_LIBRARY
