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
from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.session_commit import commit_or_restore
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
from app.infrastructure.canonical_spreadsheet.openpyxl_workbook_reader import (  # noqa: E501
    OpenpyxlWorkbookReader,
)
from app.infrastructure.canonical_spreadsheet.sqlalchemy_canonical_workbook_repository import (  # noqa: E501
    SqlAlchemyCanonicalWorkbookRepository,
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
from app.services.document_pipeline_service import (
    DocumentLineage,
    DocumentPipelineResult,
    PipelineStage,
    SpreadsheetPipelineResult,
)
from app.services.storage import (
    discard_file,
    safe_storage_name,
    save_file,
)


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

    # The uploaded name never becomes a path; see `save_file`. The bytes
    # are hashed as they are written, so the identity recorded below
    # covers the bytes that were actually stored.
    stored = save_file(file.file, filename)
    saved_path = stored.path

    # Everything from here to the commit runs with bytes already on disk
    # and no row referencing them, so every exit from this block that is
    # not a commit has to take the file with it. The window is wider
    # than the commit itself: classification and row construction can
    # both raise, and a file orphaned by those is orphaned just as
    # thoroughly as one orphaned by a failed commit.
    try:
        # Milestone 25.2: the format is classified from the bytes just
        # written, plus the declared MIME type and the filename, by the
        # same classifier ingestion uses. ADR-0036: the content identity
        # comes from the write rather than a second read of the file.
        identity = resolve_document_identity(
            FilesystemDocumentContentAdapter(),
            storage_reference=str(saved_path),
            filename=filename,
            declared_mime_type=file.content_type,
            content=stored.content,
        )

        content_identity = (
            identity.content.identity if identity.content.resolved else None
        )

        document = Document(
            filename=filename,
            file_path=str(saved_path),
            file_format=_persisted_format(identity.format),
            project_id=project.id if project else None,
            project_name=project.name if project else "Unknown",
            scope=scope,
            # ADR-0036 §18: written once, here, and never updated. A
            # file that could not be identified - an empty upload is the
            # reachable case - records no identity rather than a
            # placeholder for one.
            content_checksum=(
                content_identity.checksum if content_identity else None
            ),
            content_checksum_algorithm=(
                content_identity.checksum_algorithm
                if content_identity
                else None
            ),
            content_size_bytes=(
                content_identity.size_bytes if content_identity else None
            ),
        )

        db.add(document)
        commit_or_restore(db)
    except Exception:
        # The bytes were written before the row existed, which is the
        # right order - the alternative leaves a committed row pointing
        # at nothing, and that is a lie in the registry rather than
        # invisible waste. So the compensation belongs here.
        discard_file(saved_path)
        raise

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
    PipelineStage.CANONICAL_WORKBOOK: "failed",
}

# The one canonicalisation refusal that is not a failure of this upload:
# the document belongs to no lineage that can read it.
_UNSUPPORTED_FORMAT_CODE = "unsupported_format"

# Reported when the records a workflow needs cannot be reached at all -
# a table that does not exist yet being the realistic cause. Named here
# rather than in any context's failure vocabulary because it describes
# the deployment, not the document.
_STORAGE_UNAVAILABLE_CODE = "storage_unavailable"

# Where a storage fault is reported to have stopped a run. The workflow
# never concluded, so this names the lineage the router had dispatched
# to rather than a stage the workflow claimed to reach.
_STAGE_FOR_LINEAGE: dict[DocumentLineage, PipelineStage] = {
    DocumentLineage.CANONICAL_PDF: PipelineStage.CANONICAL_REPRESENTATION,
    DocumentLineage.CANONICAL_SPREADSHEET: (
        PipelineStage.CANONICAL_WORKBOOK
    ),
}

# Each lineage's own name for "the document opened, it had content to
# hold, and it held nothing". A set rather than one string because the
# same observation has a different word in each lineage - a PDF reports
# pages with no text span, a workbook reports worksheets with no
# populated cell - and reporting one as `no_text` while the other became
# the generic `failed` would give a client two answers to one question.
#
# `empty_workbook` is deliberately **not** here. It names a container
# with no worksheet at all, which is the analogue of `empty_document`
# (no pages), not of `no_extractable_text` - and `empty_document`
# reports `failed`. Nothing was empty of text; there was nowhere for
# text to be.
_NOTHING_TO_READ_CODES = frozenset(
    {"no_extractable_text", "no_populated_cell"}
)


def _run_document_pipeline(
    db: Session, document: Document, project
) -> UploadAnalysisRead:
    """
    Runs the uploaded document through the workflow for its lineage and
    reports where that workflow stopped.

    **The router orchestrates and decides nothing.** Every processing
    rule lives in ``document_pipeline_service`` and the services beneath
    it; what happens here is dependency construction and the mapping of a
    typed result onto this endpoint's reported shape.

    A pipeline failure never fails the upload. The document is stored,
    identified and recorded whatever the workflow makes of it - losing
    an uploaded file because a downstream analysis stumbled would be the
    worst possible trade.
    """

    if project is None:
        # A canonical-library document belongs to no project. Nothing
        # downstream of canonicalisation is per-project any more, but the
        # reported status keeps its long-standing vocabulary.
        return UploadAnalysisRead(
            status="skipped", entities_found=0, failure=None
        )

    # Which lineage this document belongs to is a processing rule, and
    # the workflow layer owns it (ADR-0034 §1). What the router does
    # with the answer is construct that lineage's adapters - which is
    # its job as the composition root, and the only thing it decides.
    lineage = document_pipeline_service.lineage_for_format(
        document.file_format.value
    )

    # The document's own id, read before the workflow runs. A storage
    # fault leaves the session unusable until it is rolled back, and the
    # instance is expired by the stages' own commits - so reading it
    # afterwards would itself raise, inside the handler meant to report
    # the fault.
    document_id = document.id

    try:
        return _run_lineage(db, lineage, document_id=document_id)
    except (InterfaceError, OperationalError, ProgrammingError):
        # **The store could not answer.** A missing table is the
        # realistic case - code deployed ahead of its migration - and it
        # is not something any workflow can report, because the fault
        # prevents the workflow concluding at all.
        #
        # Mapped here rather than given a domain failure code: no
        # bounded context owns "the database is not ready", and
        # inventing a canonicalisation cause for it would put an
        # infrastructure condition into a vocabulary that describes
        # documents. This endpoint's promise is a router-level promise,
        # so this is where it is kept.
        #
        # **Narrow on purpose.** These three are the "the database
        # could not do that" errors - an absent table, a refused
        # statement, a connection that is gone. The wider
        # ``SQLAlchemyError`` would also swallow
        # ``MultipleResultsFound`` and ``InvalidRequestError``, which
        # are integrity and programming faults: reporting one of those
        # as an unreachable store would tell an operator to look at the
        # deployment for a bug that is in the code.
        db.rollback()

        logger.exception(
            "Storage was unavailable while processing document %s",
            document_id,
        )

        return UploadAnalysisRead(
            status="failed",
            entities_found=0,
            failure=UploadPipelineFailureRead(
                stage=_STAGE_FOR_LINEAGE[lineage].value,
                code=_STORAGE_UNAVAILABLE_CODE,
                message=(
                    f"Document '{document_id}' was stored, and the "
                    "analysis could not run because its records were "
                    "unreachable."
                ),
            ),
        )


def _run_lineage(
    db: Session,
    lineage: DocumentLineage,
    *,
    document_id: int,
) -> UploadAnalysisRead:
    """Construct the adapters this lineage needs, run its workflow, and
    map the result. Dependency construction and nothing else."""

    if lineage is DocumentLineage.CANONICAL_SPREADSHEET:
        return _report(
            document_pipeline_service.process_uploaded_spreadsheet(
                document_id=document_id,
                ingestion_repository=SqlAlchemyIngestionJobRepository(db),
                document_metadata_port=(
                    SqlAlchemyDocumentMetadataRepository(db)
                ),
                content_port=FilesystemDocumentContentAdapter(),
                storage_location_port=SqlAlchemyDocumentStorageLocation(db),
                reader=OpenpyxlWorkbookReader(),
                workbook_repository=(
                    SqlAlchemyCanonicalWorkbookRepository(db)
                ),
                now=datetime.utcnow(),
            ),
            document_id=document_id,
        )

    result = document_pipeline_service.process_uploaded_document(
        document_id=document_id,
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
        # **No downstream consumer, since EPIC 31.1.**
        #
        # This callback used to be `knowledge_graph.ingest_document`,
        # which wrote LLM-extracted entities and relationships straight
        # into the queryable graph on every upload - with no review gate,
        # no reviewer and no provenance. ADR-0004 recorded from
        # Architecture Freeze v1.0 that this must not happen and that it
        # was happening anyway; this is where it stopped.
        #
        # Knowledge now enters the graph only through an explicit,
        # capability-gated promotion of a statement an engineer approved.
        # Uploading a document produces canonical artefacts and nothing
        # else, which is what makes "the graph contains only governed
        # knowledge" true rather than aspirational.
        consumer=None,
    )

    return _report(result, document_id=document_id)


def _report(
    result: DocumentPipelineResult | SpreadsheetPipelineResult,
    *,
    document_id: int,
) -> UploadAnalysisRead:
    """
    Map either lineage's result onto this endpoint's reported shape.

    **One mapping, not one per lineage.** The two result types differ in
    what they carry about their own stages, and agree exactly on what
    this endpoint reports - ``succeeded``, and a ``failure`` whose
    ``stage``, ``code`` and ``message`` come from the shared,
    lineage-neutral type. Reading only those keeps the response a single
    contract however many source families exist.
    """

    if result.succeeded:
        return UploadAnalysisRead(
            status="completed",
            # Always zero since EPIC 31.1: an upload no longer writes
            # any graph. Kept in the response, at zero, rather than
            # removed - see `public_api.md` on why this field survives
            # its cause.
            entities_found=0,
            failure=None,
        )

    logger.info(
        "Document pipeline stopped at %s for document %s: %s",
        result.failure.stage.value,
        document_id,
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

    if failure.code in _NOTHING_TO_READ_CODES:
        return "no_text"

    return _LEGACY_STATUS_FOR_STAGE[failure.stage]
