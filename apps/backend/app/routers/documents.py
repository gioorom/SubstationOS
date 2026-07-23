import logging
from pathlib import Path

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
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import MUTABLE_STATES
from app.models.document import Document
from app.models.project import Project
from app.services.knowledge_graph import ingest_document
from app.services.pdf_text_extractor import extract_text_from_pdf
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

    document = Document(
        filename=filename,
        file_path=str(saved_path),
        project_id=project.id if project else None,
        project_name=project.name if project else "Unknown",
        scope=scope,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    extracted_entities_count = 0
    knowledge_graph_status = "skipped"

    # Il Knowledge Graph richiede un progetto associato.
    if project is not None:
        file_extension = Path(saved_path).suffix.lower()

        if file_extension == ".pdf":
            try:
                text = extract_text_from_pdf(saved_path)

                if text:
                    entities = ingest_document(
                        db=db,
                        project_id=project.id,
                        text=text,
                        source_document=document.filename,
                    )

                    extracted_entities_count = len(entities)
                    knowledge_graph_status = "completed"
                else:
                    knowledge_graph_status = "no_text"

            except Exception:
                # L'upload rimane valido anche se l'analisi fallisce.
                logger.exception(
                    "Knowledge Graph ingestion failed for document %s",
                    document.id,
                )

                knowledge_graph_status = "failed"
        else:
            knowledge_graph_status = "unsupported_file_type"

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
        "knowledge_graph": {
            "status": knowledge_graph_status,
            "entities_found": extracted_entities_count,
        },
    }


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