import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.document_identity.document_format import FormatClassification
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import MUTABLE_STATES
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
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.models.document import Document, DocumentFormat
from app.models.project import Project
from app.services import document_pipeline_service
from app.services.document_identity_service import resolve_document_identity
from app.services.document_pipeline_service import PipelineStage
from app.services.knowledge_graph import ingest_document
from app.services.storage import save_file


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


def _persisted_format(
    classification: FormatClassification,
) -> DocumentFormat:
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
        return DocumentFormat.OTHER

    return DocumentFormat(classification.detected_format.value)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    project_id: int | None = Form(default=None),
    scope: DocumentScope = Form(default=DocumentScope.PROJECT),
    db: Session = Depends(get_db),
):
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
                "Canonical Library documents must not reference a "
                "project"
            ),
        )

    project = None

    if project_id is not None:
        project = (
            db.query(Project)
            .filter(Project.id == project_id)
            .first()
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
                    f"'{project.lifecycle_state.value}' and is "
                    "read-only"
                ),
            )

    filename = file.filename or "unnamed_document"

    saved_path = save_file(
        file.file,
        filename,
    )

    # Milestone 25.2: the format is classified from the bytes just
    # written, plus the declared MIME type and the filename, by the same
    # classifier ingestion uses. Before this, every upload was stored as
    # OTHER regardless of what it was.
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

    knowledge_graph = _run_document_pipeline(db, document, project)

    return {
        "id": document.id,
        "project_id": document.project_id,
        "filename": document.filename,
        "file_path": document.file_path,
        "file_format": document.file_format,
        "category": document.category,
        "revision": document.revision,
        "project_name": document.project_name,
        "scope": document.scope,
        "uploaded_at": document.uploaded_at,
        "knowledge_graph": knowledge_graph,
    }


# The pipeline stage that produced a failure, mapped onto the status
# string this endpoint has always returned. A table rather than a branch
# chain, and deliberately lossy in one direction only: the response keeps
# its long-standing shape, while ``failure`` beside it carries the stage
# and the failing stage's own typed code, so a caller who wants the real
# cause is no longer told merely "failed".
_LEGACY_STATUS_FOR_STAGE: dict[PipelineStage, str] = {
    PipelineStage.INGESTION: "failed",
    PipelineStage.CANONICAL_REPRESENTATION: "failed",
    PipelineStage.SEGMENTATION: "failed",
    PipelineStage.TEXT_ASSEMBLY: "no_text",
    PipelineStage.DOWNSTREAM_CONSUMER: "failed",
}

# The one canonicalisation refusal that is not a failure of this upload:
# the document is simply not a PDF. Reported as it always was.
_UNSUPPORTED_FORMAT_CODE = "unsupported_format"

# Canonicalisation's own name for "pages, and no text anywhere". The
# pre-26.2 endpoint reported that as ``no_text``, and still does.
_NO_EXTRACTABLE_TEXT_CODE = "no_extractable_text"


def _run_document_pipeline(db: Session, document: Document, project) -> dict:
    """
    Runs the uploaded document through the one supported pipeline and
    reports what the Knowledge Graph made of it.

    **The router orchestrates and decides nothing.** Every processing
    rule lives in ``document_pipeline_service`` and the services beneath
    it; what happens here is dependency construction and the mapping of a
    typed result onto this endpoint's long-standing response shape.

    A pipeline failure never fails the upload. The document is stored,
    identified and recorded whatever the Knowledge Graph makes of it -
    losing an uploaded file because a downstream analysis stumbled would
    be the worst possible trade.
    """

    if project is None:
        # The Knowledge Graph is per-project. A canonical-library
        # document has no project to be ingested into.
        return {"status": "skipped", "entities_found": 0, "failure": None}

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
        return {
            "status": "completed",
            "entities_found": len(result.consumer_result or []),
            "failure": None,
        }

    logger.info(
        "Document pipeline stopped at %s for document %s: %s",
        result.failure.stage.value,
        document.id,
        result.failure.code,
    )

    return {
        "status": _legacy_status(result.failure),
        "entities_found": 0,
        "failure": {
            "stage": result.failure.stage.value,
            "code": result.failure.code,
            "message": result.failure.message,
        },
    }


def _legacy_status(failure) -> str:
    """The status string this endpoint returned before Milestone 26.2,
    preserved exactly - a client that reads only ``status`` sees no
    change."""

    if failure.code == _UNSUPPORTED_FORMAT_CODE:
        return "unsupported_file_type"

    if failure.code == _NO_EXTRACTABLE_TEXT_CODE:
        return "no_text"

    return _LEGACY_STATUS_FOR_STAGE[failure.stage]


@router.get("/")
def get_documents(
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Document)

    if project_id is not None:
        query = query.filter(
            Document.project_id == project_id
        )

    return (
        query
        .order_by(Document.uploaded_at.desc())
        .all()
    )