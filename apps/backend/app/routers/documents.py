"""
The Document API.

Hardened in Milestone 30.1.3. What changed, and why:

- ``GET /documents/`` declared no response model, so it returned ORM rows
  including ``file_path``. It now returns ``DocumentListResponse``, built
  from governed value objects that have no storage field, and the server
  does the paging, filtering and sorting.
- ``POST /documents/upload`` returned a bare ``dict`` that OpenAPI could
  not describe and that also carried ``file_path``. It now returns
  ``DocumentUploadResponse``.
- ``GET /documents/{id}`` did not exist, so a client had to reconstruct a
  document's details from the list.
- ``GET /documents/{id}/content`` did not exist, so a stored document
  could not be retrieved at all.

Route naming: the download is ``/content``, not ``/download``. Every
other per-document route in this API is a noun naming the artefact it
serves - ``/canonical-representation``, ``/canonical-text``,
``/engineering-evidence``. ``content`` is the noun for the original
bytes, and it is the name of the port that serves them.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.document_identity.document_format import FormatClassification
from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.domain.document_registry.document_failures import (
    DocumentContentAccessError,
    DocumentContentNotFoundError,
    DocumentNotFoundError,
    DocumentPersistenceError,
)
from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentFormat,
)
from app.domain.document_registry.document_query import (
    DEFAULT_DOCUMENT_DIRECTION,
    DEFAULT_DOCUMENT_SORT,
    DocumentQuery,
    DocumentSearchTerm,
    DocumentSortField,
)
from app.domain.document_registry.document_repository import (
    DocumentRegistryRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import MUTABLE_STATES
from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageRequest,
    SortDirection,
)
from app.domain.shared_kernel.pagination_exceptions import PaginationError
from app.infrastructure.canonical_pdf.pymupdf_parser import PyMuPdfParser
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
)
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_storage_location import (  # noqa: E501
    SqlAlchemyDocumentStorageLocation,
)
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.document_registry.sqlalchemy_document_registry import (  # noqa: E501
    SqlAlchemyDocumentRegistryRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.models.document import Document
from app.models.document import DocumentFormat as PersistedFormat
from app.models.project import Project
from app.schemas.document import (
    DocumentDetailRead,
    DocumentListResponse,
    DocumentSummaryRead,
    DocumentUploadResponse,
    UploadAnalysisRead,
    UploadPipelineFailureRead,
)
from app.schemas.pagination import PageMetadata
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.routers.security import require_capability
from app.services import (
    audit_service,
    document_pipeline_service,
    document_registry_service,
)
from app.services.document_identity_service import resolve_document_identity
from app.services.document_pipeline_service import PipelineStage
from app.services.knowledge_graph import ingest_document
from app.services.storage import safe_storage_name, save_file


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _registry(db: Session) -> DocumentRegistryRepository:
    return SqlAlchemyDocumentRegistryRepository(db)


def _content_port() -> FilesystemDocumentContentAdapter:
    return FilesystemDocumentContentAdapter()


def _storage_location(db: Session) -> SqlAlchemyDocumentStorageLocation:
    return SqlAlchemyDocumentStorageLocation(db)


def _persisted_format(
    classification: FormatClassification,
) -> PersistedFormat:
    """
    Maps the classifier's verdict onto the stored format.

    An unknown or contradictory verdict stores ``OTHER``, which in this
    schema means *unclassified* - the honest record of a document the
    classifier looked at and could not name. It is deliberately not a
    rejection: the upload is a valid document either way, and refusing it
    over an unrecognised extension would lose the file to protect a
    column.
    """

    if not classification.is_classified:
        return PersistedFormat.OTHER

    return PersistedFormat(classification.detected_format.value)


# --- Listing --------------------------------------------------------------


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary=(
        "List documents, filtered, sorted and paginated by the server"
    ),
)
def get_documents(
    page: int = Query(default=1, ge=1, description="1-based page index."),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page. Maximum {MAX_PAGE_SIZE}.",
    ),
    project_id: int | None = Query(default=None),
    scope: DocumentScope | None = Query(default=None),
    file_format: DocumentFormat | None = Query(default=None),
    category: DocumentCategory | None = Query(default=None),
    search: str | None = Query(
        default=None,
        description=(
            "Case-insensitive partial match over filename and project "
            "name. Trimmed at both ends; internal whitespace is "
            "significant."
        ),
    ),
    sort_by: DocumentSortField = Query(default=DEFAULT_DOCUMENT_SORT),
    direction: SortDirection = Query(default=DEFAULT_DOCUMENT_DIRECTION),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    try:
        page_request = PageRequest(page=page, page_size=page_size)
    except PaginationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    try:
        result = document_registry_service.list_documents(
            _registry(db),
            DocumentQuery(
                page=page_request,
                project_id=project_id,
                scope=scope,
                document_format=file_format,
                category=category,
                search=DocumentSearchTerm.of(search),
                sort_by=sort_by,
                direction=direction,
            ),
        )
    except DocumentPersistenceError as error:
        raise _persistence_failure(error) from error

    return DocumentListResponse(
        items=tuple(
            DocumentSummaryRead.of(summary) for summary in result.items
        ),
        pagination=PageMetadata.of(result),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailRead,
    responses={404: {"description": "No such document."}},
    summary="One document's full public record",
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentDetailRead:
    try:
        detail = document_registry_service.get_document_detail(
            _registry(db),
            _content_port(),
            _storage_location(db),
            document_id=document_id,
        )
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentPersistenceError as error:
        raise _persistence_failure(error) from error

    return DocumentDetailRead.of_detail(detail)


@router.get(
    "/{document_id}/content",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "The document's original bytes.",
            "content": {"application/octet-stream": {"schema": {
                "type": "string",
                "format": "binary",
            }}},
        },
        404: {
            "description": (
                "No such document, or its stored content no longer "
                "exists. The two are distinguished by the message."
            )
        },
        500: {"description": "The content exists and could not be read."},
    },
    summary="Download a document's original bytes",
)
def download_document_content(
    document_id: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Streams the stored document.

    The only input is the document id. The storage reference comes from
    the registry and goes straight back to the content port - **no path
    is ever accepted from, or disclosed to, the caller**, which is why
    traversal is not merely blocked but unrepresentable.

    Every failure is resolved before the first byte is written: once a
    stream has begun the status code is already sent, and a failure could
    no longer be reported as one.
    """

    content_port = _content_port()

    try:
        download = document_registry_service.resolve_download(
            _registry(db),
            content_port,
            _storage_location(db),
            document_id=document_id,
        )
    except (DocumentNotFoundError, DocumentContentNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentContentAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    except DocumentPersistenceError as error:
        raise _persistence_failure(error) from error

    return StreamingResponse(
        document_registry_service.stream_download(content_port, download),
        media_type=download.media_type,
        headers={
            "Content-Disposition": download.content_disposition,
            "Content-Length": str(download.size_bytes),
        },
    )


def _persistence_failure(error: DocumentPersistenceError) -> HTTPException:
    """
    A registry read that failed for an infrastructure reason.

    The response says the registry could not be read and stops there. The
    driver's message, the table name and the connection string stay in
    the log, where they help, rather than in the response, where they
    only help an attacker.
    """

    logger.exception("Document registry read failed: %s", error.detail)

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The document registry could not be read.",
    )


# --- Upload ---------------------------------------------------------------


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    # Deliberately 200, not 201. Every other create in this API answers
    # 201, and this endpoint should too - but changing it is a breaking
    # change this milestone was not asked to make, and the response body
    # is already changing. Recorded as debt rather than smuggled in.
    responses={
        404: {"description": "The referenced project does not exist."},
        409: {"description": "The project is archived or deleted."},
        422: {"description": "The scope and project reference disagree."},
    },
    summary="Upload one document",
)
async def upload_document(
    file: UploadFile = File(...),
    project_id: int | None = Form(default=None),
    scope: DocumentScope = Form(default=DocumentScope.PROJECT),
    actor: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    # Repository rule (ADR-0005): every document belongs to exactly one
    # Project, or to the Canonical Library - never both, never neither.
    if scope is DocumentScope.PROJECT and project_id is None:
        raise HTTPException(
            status_code=422,
            detail="A project_id is required for scope 'project'",
        )

    if scope is DocumentScope.CANONICAL_LIBRARY and project_id is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Canonical Library documents must not reference a project"
            ),
        )

    project = None

    if project_id is not None:
        project = (
            db.query(Project).filter(Project.id == project_id).first()
        )

        if project is None:
            raise HTTPException(
                status_code=404,
                detail="Project not found",
            )

        if project.lifecycle_state not in MUTABLE_STATES:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Project '{project.code}' is "
                    f"'{project.lifecycle_state.value}' and is read-only"
                ),
            )

    filename = file.filename or "unnamed_document"

    # The uploaded name never becomes a path; see `save_file`.
    saved_path = save_file(file.file, filename)

    # Milestone 25.2: the format is classified from the bytes just
    # written, plus the declared MIME type and the filename, by the same
    # classifier ingestion uses.
    identity = resolve_document_identity(
        FilesystemDocumentContentAdapter(),
        storage_reference=str(saved_path),
        filename=filename,
        declared_mime_type=file.content_type,
    )

    document = Document(
        filename=filename,
        file_path=str(saved_path),
        file_format=_persisted_format(identity.format),
        project_id=project.id if project else None,
        project_name=project.name if project else "Unknown",
        scope=scope,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    analysis = _run_document_pipeline(db, document, project)

    detail = document_registry_service.get_document_detail(
        _registry(db),
        _content_port(),
        _storage_location(db),
        document_id=document.id,
    )

    # Who put this document into the platform. Recorded on the *action*;
    # nothing about the document row or anything derived from it changes.
    audit_service.record_for_identity(
        SqlAlchemyAuditRepository(db),
        identity=actor,
        action=AuditAction.DOCUMENT_UPLOADED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource("document", str(document.id)),
        now=datetime.utcnow(),
        detail=f"scope={scope.value}",
    )

    return DocumentUploadResponse(
        document=DocumentDetailRead.of_detail(detail),
        scope=scope,
        analysis=analysis,
        warnings=_upload_warnings(identity, filename),
    )


def _upload_warnings(
    identity, original_filename: str
) -> tuple[str, ...]:
    """
    Non-fatal observations about what was stored.

    Both are things a caller can act on and neither is an error: an
    unclassified format may still be a perfectly good document, and a
    sanitised storage name changes nothing an engineer sees.
    """

    warnings: list[str] = []

    if not identity.format.is_classified:
        warnings.append(
            "The document format could not be determined from its "
            "content, declared type or extension; it is recorded as "
            "unclassified."
        )

    if not _is_storage_safe(original_filename):
        warnings.append(
            "The original filename was sanitised for storage. The "
            "document is still listed under the name you uploaded."
        )

    return tuple(warnings)


def _is_storage_safe(filename: str) -> bool:
    """
    Whether the uploaded name survived sanitisation unchanged, apart from
    the uniqueness suffix every stored name receives.

    Asked of the sanitiser rather than guessed from the result, so the
    two can never disagree about what "changed" means.
    """

    sanitised = safe_storage_name(filename)

    stem, _, extension = filename.rpartition(".")
    original_stem = stem or filename

    return sanitised.startswith(original_stem) and (
        not extension or sanitised.endswith(f".{extension}")
    )


# The pipeline stage that produced a failure, mapped onto the status
# string this endpoint has always reported. A table rather than a branch
# chain, and deliberately lossy in one direction only: the status keeps
# its long-standing vocabulary, while ``failure`` beside it carries the
# stage and the failing stage's own typed code.
_LEGACY_STATUS_FOR_STAGE: dict[PipelineStage, str] = {
    PipelineStage.INGESTION: "failed",
    PipelineStage.CANONICAL_REPRESENTATION: "failed",
    PipelineStage.SEGMENTATION: "failed",
    PipelineStage.TEXT_ASSEMBLY: "no_text",
    PipelineStage.DOWNSTREAM_CONSUMER: "failed",
}

# The one canonicalisation refusal that is not a failure of this upload:
# the document is simply not a PDF.
_UNSUPPORTED_FORMAT_CODE = "unsupported_format"

# Canonicalisation's own name for "pages, and no text anywhere".
_NO_EXTRACTABLE_TEXT_CODE = "no_extractable_text"


def _run_document_pipeline(
    db: Session, document: Document, project
) -> UploadAnalysisRead:
    """
    Runs the uploaded document through the one supported pipeline and
    reports what the Knowledge Graph made of it.

    **The router orchestrates and decides nothing.** Every processing
    rule lives in ``document_pipeline_service`` and the services beneath
    it; what happens here is dependency construction and the mapping of a
    typed result onto this endpoint's reported shape.

    A pipeline failure never fails the upload. The document is stored,
    identified and recorded whatever the Knowledge Graph makes of it -
    losing an uploaded file because a downstream analysis stumbled would
    be the worst possible trade.
    """

    if project is None:
        # The Knowledge Graph is per-project. A canonical-library
        # document has no project to be ingested into.
        return UploadAnalysisRead(
            status="skipped", entities_found=0, failure=None
        )

    result = document_pipeline_service.process_uploaded_document(
        document_id=document.id,
        ingestion_repository=SqlAlchemyIngestionJobRepository(db),
        document_metadata_port=SqlAlchemyDocumentMetadataRepository(db),
        content_port=FilesystemDocumentContentAdapter(),
        storage_location_port=SqlAlchemyDocumentStorageLocation(db),
        parser=PyMuPdfParser(),
        representation_repository=(
            SqlAlchemyCanonicalRepresentationRepository(db)
        ),
        text_repository=SqlAlchemyCanonicalTextRepository(db),
        now=datetime.utcnow(),
        consumer=lambda text: ingest_document(
            db=db,
            project_id=project.id,
            text=text,
            source_document=document.filename,
        ),
    )

    if result.succeeded:
        return UploadAnalysisRead(
            status="completed",
            entities_found=len(result.consumer_result or []),
            failure=None,
        )

    logger.info(
        "Document pipeline stopped at %s for document %s: %s",
        result.failure.stage.value,
        document.id,
        result.failure.code,
    )

    return UploadAnalysisRead(
        status=_legacy_status(result.failure),
        entities_found=0,
        failure=UploadPipelineFailureRead(
            stage=result.failure.stage.value,
            code=result.failure.code,
            message=result.failure.message,
        ),
    )


def _legacy_status(failure) -> str:
    """The status vocabulary this endpoint reported before Milestone
    26.2, preserved exactly - a client reading only ``status`` sees no
    change beyond its new position under ``analysis``."""

    if failure.code == _UNSUPPORTED_FORMAT_CODE:
        return "unsupported_file_type"

    if failure.code == _NO_EXTRACTABLE_TEXT_CODE:
        return "no_text"

    return _LEGACY_STATUS_FOR_STAGE[failure.stage]
