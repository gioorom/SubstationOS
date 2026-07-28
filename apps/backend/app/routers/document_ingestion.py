"""
The Document Ingestion API (Milestone 25.1).

```
POST /documents/ingestion/jobs          request + queue + execute
POST /documents/ingestion/jobs/{id}/retry
GET  /documents/ingestion/jobs/{id}
GET  /documents/{document_id}/ingestion/jobs
GET  /projects/{project_id}/ingestion/jobs
```

**A pipeline failure returns HTTP 200 with a `failed` job**, not a client
error: the request was well-formed and ingestion answered it correctly
("this document's format is not one we recognise"). The same discipline
the Engineering Engine already follows for unsupported intents, keeping
`422` meaning exactly one thing across this codebase - a structurally
invalid request.

The two failures that *are* client errors are the ones where no job could
legitimately exist at all: a duplicate request while one is already in
flight (`409`), and a request to retry a job that is not failed (`409`).

This router is the composition root for ingestion: it constructs the
storage-location and content adapters (Milestone 25.2) and hands them to
the service, which knows only the ports. Swapping the filesystem for an
object store is a change to this file and one adapter.

This router performs no extraction, invokes no provider, and writes
neither the Engineering Index nor the Knowledge Graph.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.document_ingestion.ingestion_exceptions import (
    DuplicateIngestionRequestError,
    IngestionJobNotFoundError,
    IngestionJobNotRetryableError,
)
from app.infrastructure.document_identity.filesystem_document_content import (  # noqa: E501
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_storage_location import (  # noqa: E501
    SqlAlchemyDocumentStorageLocation,
)
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.schemas.document_ingestion import (
    IngestDocumentRequestBody,
    IngestionJobRead,
)
from app.services import document_ingestion_service

router = APIRouter(
    tags=["Document Ingestion"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/documents/ingestion/jobs",
    response_model=IngestionJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an already-uploaded document: create, queue and run "
    "its ingestion job",
)
def ingest_document(
    body: IngestDocumentRequestBody,
    db: Session = Depends(get_db),
) -> IngestionJobRead:
    try:
        job = document_ingestion_service.ingest_document(
            SqlAlchemyIngestionJobRepository(db),
            SqlAlchemyDocumentMetadataRepository(db),
            document_id=body.document_id,
            now=datetime.utcnow(),
            content_port=FilesystemDocumentContentAdapter(),
            storage_location_port=SqlAlchemyDocumentStorageLocation(db),
        )
    except DuplicateIngestionRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return IngestionJobRead.from_domain(job)


@router.post(
    "/documents/ingestion/jobs/{job_id}/retry",
    response_model=IngestionJobRead,
    summary="Return a failed ingestion job to the queue and run it again",
)
def retry_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> IngestionJobRead:
    repository = SqlAlchemyIngestionJobRepository(db)
    metadata_port = SqlAlchemyDocumentMetadataRepository(db)

    try:
        job = document_ingestion_service.retry_ingestion(
            repository, job_id=job_id, now=datetime.utcnow()
        )
        job = document_ingestion_service.execute_ingestion(
            repository,
            metadata_port,
            job_id=job.id,
            now=datetime.utcnow(),
            content_port=FilesystemDocumentContentAdapter(),
            storage_location_port=SqlAlchemyDocumentStorageLocation(db),
        )
    except IngestionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except IngestionJobNotRetryableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    return IngestionJobRead.from_domain(job)


@router.get(
    "/documents/ingestion/jobs/{job_id}",
    response_model=IngestionJobRead,
    summary="Read one ingestion job",
)
def read_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> IngestionJobRead:
    try:
        job = document_ingestion_service.get_job(
            SqlAlchemyIngestionJobRepository(db), job_id
        )
    except IngestionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    return IngestionJobRead.from_domain(job)


@router.get(
    "/documents/{document_id}/ingestion/jobs",
    response_model=list[IngestionJobRead],
    summary="Every ingestion job recorded for one document, oldest first",
)
def list_ingestion_jobs_for_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> list[IngestionJobRead]:
    jobs = document_ingestion_service.list_jobs_for_document(
        SqlAlchemyIngestionJobRepository(db), document_id
    )

    return [IngestionJobRead.from_domain(job) for job in jobs]


@router.get(
    "/projects/{project_id}/ingestion/jobs",
    response_model=list[IngestionJobRead],
    summary="Every ingestion job recorded for one project",
)
def list_ingestion_jobs_for_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[IngestionJobRead]:
    if project_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid project id: '{project_id}'.",
        )

    jobs = document_ingestion_service.list_jobs_for_project(
        SqlAlchemyIngestionJobRepository(db), project_id
    )

    return [IngestionJobRead.from_domain(job) for job in jobs]
