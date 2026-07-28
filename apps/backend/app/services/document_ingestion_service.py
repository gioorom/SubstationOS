"""
Application service for Document Ingestion (EPIC 2, Milestone 25.1) - the
orchestration this milestone exists to provide:

    Upload            (the existing /documents/upload endpoint)
        -> Register    (the document repository, unchanged)
        -> Request     request_ingestion  - creates the job, UPLOADED
        -> Queue       queue_ingestion    - UPLOADED -> QUEUED
        -> Execute     execute_ingestion  - QUEUED -> PROCESSING -> terminal
        -> Persist     the repository writes each state as it happens

Each stage is a separate call on purpose. A single "ingest this" function
would collapse five distinct facts - accepted, scheduled, started,
concluded, recorded - into one, and the whole point of this milestone is
that a document's progress is *governed and visible* rather than
implied.

It orchestrates existing capabilities and adds none of its own:

- the **document repository** is read through ``DocumentMetadataPort``,
  the port Milestone 23B.1 already introduced - no new document contract;
- the **pipeline** is the pure domain function, which performs no I/O;
- the **lifecycle** is the domain's transition table, which raises on an
  illegal move;
- **document identity** (Milestone 25.2) is ``document_identity_service``,
  the same one the upload endpoint uses, so a document's format is decided
  by one rule wherever it is looked at.

It invokes no LLM and writes neither the Engineering Index nor the Project
Knowledge Graph. Since Milestone 25.2 it does read bytes - a leading
signature and a streamed checksum, through a read-only port - which
identifies a file without interpreting one. ``now`` is always
caller-supplied, so the whole flow stays reproducible (CLAUDE.md §16).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.domain.document_ingestion import ingestion_factory
from app.domain.document_ingestion.ingestion_exceptions import (
    DuplicateIngestionRequestError,
    IngestionJobNotFoundError,
    IngestionJobNotRetryableError,
)
from app.domain.document_ingestion.ingestion_lifecycle import IngestionState
from app.domain.document_ingestion.ingestion_models import IngestionJob
from app.domain.document_ingestion.ingestion_pipeline import (
    execute_ingestion_pipeline,
)
from app.domain.document_ingestion.ingestion_repository import (
    IngestionJobRepository,
)
from app.domain.engineering_index.document_metadata import (
    DocumentMetadata,
    DocumentMetadataPort,
)
from app.services.document_identity_service import (
    ResolvedDocumentIdentity,
    resolve_document_identity,
)


def _find_document(
    document_metadata_port: DocumentMetadataPort, document_id: int
) -> DocumentMetadata | None:
    """The port reads in batches; one document is a batch of one. Reused
    rather than given a new single-document method, so this context adds
    no second contract onto the document repository."""

    found = document_metadata_port.find_many((document_id,))

    return found[0] if found else None


def request_ingestion(
    repository: IngestionJobRepository,
    document_metadata_port: DocumentMetadataPort,
    *,
    document_id: int,
    now: datetime,
) -> IngestionJob:
    """
    Creates the ingestion job for one document, in ``UPLOADED``.

    **Idempotent where it matters and refusing where it must.** A document
    that already has a job in flight raises
    ``DuplicateIngestionRequestError`` rather than gaining a second: two
    jobs racing over one document would produce two records of what "the"
    ingestion concluded, with nothing to say which is authoritative.

    A document whose previous job *completed* may be requested again - a
    document legitimately gets re-ingested over its life, and the new job
    is a new record rather than an overwrite of the old one. Retrying a
    *failed* job is ``retry_ingestion``, which keeps the same record.

    A document that does not exist is not refused here: the job is created
    and the pipeline records ``DOCUMENT_NOT_FOUND`` as its outcome, so the
    attempt is visible rather than vanishing. Only the *duplicate* rule
    can prevent a job existing at all.
    """

    active = repository.find_active_for_document(document_id)

    if active is not None:
        raise DuplicateIngestionRequestError(
            document_id, active.id, active.state
        )

    metadata = _find_document(document_metadata_port, document_id)

    job = ingestion_factory.IngestionJobFactory.create(
        project_id=metadata.project_id if metadata is not None else None,
        document_id=document_id,
        now=now,
    )

    return repository.save(job)


def queue_ingestion(
    repository: IngestionJobRepository,
    *,
    job_id: int,
    now: datetime,
) -> IngestionJob:
    """``UPLOADED`` -> ``QUEUED``. An illegal move raises."""

    job = _require_job(repository, job_id)

    return repository.update(ingestion_factory.queue(job, now=now))


def execute_ingestion(
    repository: IngestionJobRepository,
    document_metadata_port: DocumentMetadataPort,
    *,
    job_id: int,
    now: datetime,
    content_port: DocumentContentPort | None = None,
    storage_location_port: DocumentStorageLocationPort | None = None,
) -> IngestionJob:
    """
    Runs the pipeline for one queued job: ``QUEUED`` -> ``PROCESSING`` ->
    ``PROCESSED``/``FAILED``.

    ``PROCESSING`` is persisted **before** the pipeline runs, not after.
    That is deliberate: a job that fell over mid-execution would otherwise
    still read as ``QUEUED``, and nothing would show that it had ever been
    picked up.

    The pipeline's outcome decides the terminal state; this function never
    re-judges it.

    **Content identity and format classification (Milestone 25.2) are
    resolved here, not in the pipeline**, because they need the bytes and
    the pipeline performs no I/O. Both ports are optional and must be
    supplied together: given neither, the job runs the metadata-only
    pipeline Milestone 25.1 shipped, which is a shallower ingestion but an
    honest one - it claims nothing about content it never looked at.
    """

    job = _require_job(repository, job_id)
    job = repository.update(
        ingestion_factory.start_processing(job, now=now)
    )

    metadata = _find_document(document_metadata_port, job.document_id)
    identity = _resolve_identity(
        content_port,
        storage_location_port,
        document_id=job.document_id,
        metadata=metadata,
    )

    result = execute_ingestion_pipeline(
        document_id=job.document_id,
        metadata=metadata,
        content_identity=identity.content if identity is not None else None,
        format_classification=(
            identity.format if identity is not None else None
        ),
    )

    return repository.update(
        ingestion_factory.complete(job, result, now=now)
    )


def _resolve_identity(
    content_port: DocumentContentPort | None,
    storage_location_port: DocumentStorageLocationPort | None,
    *,
    document_id: int,
    metadata: DocumentMetadata | None,
) -> ResolvedDocumentIdentity | None:
    """
    Looks at the document's stored bytes, if this caller supplied the
    ports to do so and there is a document to look at.

    Returns ``None`` - "nobody looked" - rather than a failed identity
    when the ports are absent or the document does not exist. The two are
    genuinely different: a job with no content port never examined the
    content, while a job with one and no readable bytes examined it and
    found nothing. Only the second is a content failure, and collapsing
    them would report every metadata-only ingestion as broken storage.
    """

    if content_port is None or storage_location_port is None:
        return None

    if metadata is None:
        return None

    return resolve_document_identity(
        content_port,
        storage_reference=storage_location_port.find_storage_reference(
            document_id
        ),
        filename=metadata.title,
    )


def retry_ingestion(
    repository: IngestionJobRepository,
    *,
    job_id: int,
    now: datetime,
) -> IngestionJob:
    """
    Returns a failed job to the queue for another attempt, on the **same**
    record - the attempt history belongs to the job an engineer is already
    looking at.

    Only a failed job is retryable. A completed one is re-ingested by
    requesting a new job, so what was processed when is never overwritten.
    """

    job = _require_job(repository, job_id)

    if job.state is not IngestionState.FAILED:
        raise IngestionJobNotRetryableError(job_id, job.state)

    return repository.update(ingestion_factory.retry(job, now=now))


def ingest_document(
    repository: IngestionJobRepository,
    document_metadata_port: DocumentMetadataPort,
    *,
    document_id: int,
    now: datetime,
    content_port: DocumentContentPort | None = None,
    storage_location_port: DocumentStorageLocationPort | None = None,
) -> IngestionJob:
    """
    The whole flow for one document, for callers that do not need to
    schedule the stages separately: request, queue, execute.

    A convenience over the four functions above, never a shortcut past
    them - every state is still entered, validated and persisted in turn,
    so the record is identical to one built stage by stage.
    """

    job = request_ingestion(
        repository,
        document_metadata_port,
        document_id=document_id,
        now=now,
    )
    job = queue_ingestion(repository, job_id=job.id, now=now)

    return execute_ingestion(
        repository,
        document_metadata_port,
        job_id=job.id,
        now=now,
        content_port=content_port,
        storage_location_port=storage_location_port,
    )


def get_job(
    repository: IngestionJobRepository, job_id: int
) -> IngestionJob:
    return _require_job(repository, job_id)


def list_jobs_for_document(
    repository: IngestionJobRepository, document_id: int
) -> list[IngestionJob]:
    return repository.list_by_document(document_id)


def list_jobs_for_project(
    repository: IngestionJobRepository, project_id: int
) -> list[IngestionJob]:
    return repository.list_by_project(project_id)


def _require_job(
    repository: IngestionJobRepository, job_id: int
) -> IngestionJob:
    job = repository.get_by_id(job_id)

    if job is None:
        raise IngestionJobNotFoundError(job_id)

    return job
