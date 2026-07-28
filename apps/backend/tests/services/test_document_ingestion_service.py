"""
Service tests for Document Ingestion (Milestone 25.1), against a real
(in-memory) database through the real SQLAlchemy adapter - so the
lifecycle, the duplicate rule and the persisted record are proved
together rather than against a fake that could disagree with the schema.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.document_ingestion.ingestion_exceptions import (
    DuplicateIngestionRequestError,
    IngestionJobNotFoundError,
    IngestionJobNotRetryableError,
    InvalidIngestionTransitionError,
)
from app.domain.document_ingestion.ingestion_lifecycle import IngestionState
from app.domain.document_ingestion.ingestion_models import (
    IngestionFailureCode,
    IngestionOutcome,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.project import Project as ProjectRecord
from app.services import document_ingestion_service

NOW = datetime(2026, 1, 1, 9, 0, 0)
LATER = datetime(2026, 1, 1, 9, 5, 0)


def _project(db: Session, code: str = "ALPHA-001") -> ProjectRecord:
    project = ProjectRecord(
        name="Alpha Substation", code=code, customer="Acme Utilities"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project


def _document(db: Session, project: ProjectRecord, **overrides):
    defaults = dict(
        filename="montante-T2-schema.pdf",
        file_path="/tmp/montante-T2-schema.pdf",
        project_id=project.id,
        project_name=project.name,
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    defaults.update(overrides)

    document = DocumentRecord(**defaults)
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _repos(db: Session):
    return (
        SqlAlchemyIngestionJobRepository(db),
        SqlAlchemyDocumentMetadataRepository(db),
    )


# --- The full flow ------------------------------------------------------


def test_a_supported_document_ingests_to_ready_for_extraction(
    db_session: Session,
) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    assert job.state is IngestionState.PROCESSED
    assert job.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert job.is_ready_for_extraction is True
    assert job.failure is None
    assert job.completed_at == NOW
    assert job.attempt_count == 1


def test_the_document_snapshot_is_persisted_on_the_job(
    db_session: Session,
) -> None:
    project = _project(db_session)
    document = _document(db_session, project)
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    reread = repository.get_by_id(job.id)
    assert reread.document.title == "montante-T2-schema.pdf"
    assert reread.document.document_format == "pdf"
    assert reread.document.revision == "02"
    assert reread.document.scope is DocumentScope.PROJECT
    assert reread.project_id == project.id


def test_the_snapshot_does_not_follow_the_document_afterwards(
    db_session: Session,
) -> None:
    """A job that silently started describing the current document would
    make its own recorded outcome unexplainable."""

    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    document.revision = "03"
    db_session.commit()

    assert repository.get_by_id(job.id).document.revision == "02"


def test_the_stages_can_be_driven_separately(db_session: Session) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=document.id, now=NOW
    )
    assert job.state is IngestionState.UPLOADED

    job = document_ingestion_service.queue_ingestion(
        repository, job_id=job.id, now=NOW
    )
    assert job.state is IngestionState.QUEUED

    job = document_ingestion_service.execute_ingestion(
        repository, metadata_port, job_id=job.id, now=LATER
    )
    assert job.state is IngestionState.PROCESSED


def test_driving_the_stages_separately_produces_the_same_record(
    db_session: Session,
) -> None:
    project = _project(db_session)
    first = _document(db_session, project, filename="a.pdf")
    second = _document(db_session, project, filename="b.pdf")
    repository, metadata_port = _repos(db_session)

    staged = document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=first.id, now=NOW
    )
    staged = document_ingestion_service.queue_ingestion(
        repository, job_id=staged.id, now=NOW
    )
    staged = document_ingestion_service.execute_ingestion(
        repository, metadata_port, job_id=staged.id, now=NOW
    )

    combined = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=second.id, now=NOW
    )

    assert staged.state is combined.state
    assert staged.outcome is combined.outcome
    assert staged.attempt_count == combined.attempt_count


# --- Lifecycle enforcement through the service --------------------------


def test_executing_an_unqueued_job_is_an_illegal_transition(
    db_session: Session,
) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    with pytest.raises(InvalidIngestionTransitionError):
        document_ingestion_service.execute_ingestion(
            repository, metadata_port, job_id=job.id, now=NOW
        )


def test_queueing_a_completed_job_is_an_illegal_transition(
    db_session: Session,
) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    with pytest.raises(InvalidIngestionTransitionError):
        document_ingestion_service.queue_ingestion(
            repository, job_id=job.id, now=LATER
        )


def test_an_unknown_job_is_reported_as_not_found(
    db_session: Session,
) -> None:
    repository, _ = _repos(db_session)

    with pytest.raises(IngestionJobNotFoundError):
        document_ingestion_service.get_job(repository, 999)


# --- Duplicates and idempotency -----------------------------------------


def test_a_second_request_while_one_is_in_flight_is_refused(
    db_session: Session,
) -> None:
    """Two jobs racing over one document would produce two records of what
    "the" ingestion concluded, with nothing to say which is
    authoritative."""

    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    with pytest.raises(DuplicateIngestionRequestError) as raised:
        document_ingestion_service.request_ingestion(
            repository, metadata_port, document_id=document.id, now=NOW
        )

    assert raised.value.existing_state is IngestionState.UPLOADED
    assert len(repository.list_by_document(document.id)) == 1


@pytest.mark.parametrize(
    "state", [IngestionState.UPLOADED, IngestionState.QUEUED]
)
def test_a_duplicate_is_refused_from_every_active_state(
    db_session: Session, state: IngestionState
) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=document.id, now=NOW
    )
    if state is IngestionState.QUEUED:
        document_ingestion_service.queue_ingestion(
            repository, job_id=job.id, now=NOW
        )

    with pytest.raises(DuplicateIngestionRequestError):
        document_ingestion_service.request_ingestion(
            repository, metadata_port, document_id=document.id, now=NOW
        )


def test_ingesting_the_same_document_twice_is_refused_mid_flight(
    db_session: Session,
) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    document_ingestion_service.request_ingestion(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    with pytest.raises(DuplicateIngestionRequestError):
        document_ingestion_service.ingest_document(
            repository, metadata_port, document_id=document.id, now=NOW
        )


def test_a_completed_document_can_be_ingested_again_as_a_new_job(
    db_session: Session,
) -> None:
    """A document legitimately gets re-ingested over its life, and the new
    job is a new record rather than an overwrite of the old one."""

    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    first = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )
    second = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=LATER
    )

    assert first.id != second.id
    assert second.state is IngestionState.PROCESSED
    jobs = repository.list_by_document(document.id)
    assert [job.id for job in jobs] == [first.id, second.id]


def test_repeated_ingestion_of_an_unchanged_document_is_idempotent(
    db_session: Session,
) -> None:
    """Two runs over an unchanged document conclude identically - the
    pipeline is deterministic, so only the job identity and timestamps
    differ."""

    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    first = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )
    second = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    assert first.outcome is second.outcome
    assert first.state is second.state
    assert first.document == second.document
    assert first.pipeline_version == second.pipeline_version


# --- Failures ------------------------------------------------------------


def test_an_unclassified_document_ingests_normally(
    db_session: Session,
) -> None:
    """Today's upload endpoint sets no format, so every uploaded document
    is stored as ``other``. Refusing those would mean this pipeline could
    never mark a real document ready."""

    document = _document(
        db_session,
        _project(db_session),
        filename="notes.txt",
        file_format=DocumentFormat.OTHER,
    )
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    assert job.state is IngestionState.PROCESSED
    assert job.is_ready_for_extraction is True


def test_a_missing_document_fails_the_job_and_leaves_a_record(
    db_session: Session,
) -> None:
    """The attempt is visible rather than vanishing."""

    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=999, now=NOW
    )

    assert job.state is IngestionState.FAILED
    assert job.failure.code is IngestionFailureCode.DOCUMENT_NOT_FOUND
    assert repository.get_by_id(job.id) is not None


# --- Retry ----------------------------------------------------------------


def test_a_failed_job_is_retried_on_the_same_record(
    db_session: Session,
) -> None:
    repository, metadata_port = _repos(db_session)

    # A document that does not exist yet: the attempt is recorded as
    # failed rather than vanishing.
    failed = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=1, now=NOW
    )
    assert failed.state is IngestionState.FAILED

    retried = document_ingestion_service.retry_ingestion(
        repository, job_id=failed.id, now=LATER
    )

    assert retried.id == failed.id
    assert retried.state is IngestionState.QUEUED
    assert retried.attempt_count == 2
    assert retried.failure is None
    assert len(repository.list_by_document(1)) == 1


def test_a_retry_can_succeed_once_the_document_exists(
    db_session: Session,
) -> None:
    """The realistic retry: a job ran before its document row was
    visible, failed, and succeeds on the second attempt."""

    repository, metadata_port = _repos(db_session)

    failed = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=1, now=NOW
    )
    assert failed.failure.code is IngestionFailureCode.DOCUMENT_NOT_FOUND

    document = _document(db_session, _project(db_session))
    assert document.id == failed.document_id

    retried = document_ingestion_service.retry_ingestion(
        repository, job_id=failed.id, now=LATER
    )
    completed = document_ingestion_service.execute_ingestion(
        repository, metadata_port, job_id=retried.id, now=LATER
    )

    assert completed.state is IngestionState.PROCESSED
    assert completed.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert completed.attempt_count == 2
    assert completed.failure is None


def test_a_completed_job_cannot_be_retried(db_session: Session) -> None:
    document = _document(db_session, _project(db_session))
    repository, metadata_port = _repos(db_session)

    job = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=document.id, now=NOW
    )

    with pytest.raises(IngestionJobNotRetryableError):
        document_ingestion_service.retry_ingestion(
            repository, job_id=job.id, now=LATER
        )


def test_a_retried_job_blocks_a_new_request_while_it_is_active(
    db_session: Session,
) -> None:
    repository, metadata_port = _repos(db_session)

    failed = document_ingestion_service.ingest_document(
        repository, metadata_port, document_id=1, now=NOW
    )
    document_ingestion_service.retry_ingestion(
        repository, job_id=failed.id, now=LATER
    )

    with pytest.raises(DuplicateIngestionRequestError):
        document_ingestion_service.request_ingestion(
            repository, metadata_port, document_id=1, now=LATER
        )


# --- Reads ----------------------------------------------------------------


def test_jobs_are_listed_for_a_project(db_session: Session) -> None:
    project = _project(db_session)
    first = _document(db_session, project, filename="a.pdf")
    second = _document(db_session, project, filename="b.pdf")
    repository, metadata_port = _repos(db_session)

    for document in (first, second):
        document_ingestion_service.ingest_document(
            repository, metadata_port, document_id=document.id, now=NOW
        )

    jobs = document_ingestion_service.list_jobs_for_project(
        repository, project.id
    )

    assert [job.document_id for job in jobs] == [first.id, second.id]


def test_a_document_with_no_jobs_lists_none(db_session: Session) -> None:
    document = _document(db_session, _project(db_session))
    repository, _ = _repos(db_session)

    assert repository.list_by_document(document.id) == []
    assert repository.find_active_for_document(document.id) is None
