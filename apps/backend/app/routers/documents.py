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
from app.models.document import Document
from app.models.project import Project
from app.services.storage import save_file


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
    db: Session = Depends(get_db),
):
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

    saved_path = save_file(
        file.file,
        file.filename,
    )

    document = Document(
        filename=file.filename,
        file_path=str(saved_path),
        project_id=project.id if project else None,
        project_name=project.name if project else "Unknown",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "id": document.id,
        "project_id": document.project_id,
        "filename": document.filename,
        "file_path": document.file_path,
        "file_format": document.file_format,
        "category": document.category,
        "revision": document.revision,
        "project_name": document.project_name,
        "uploaded_at": document.uploaded_at,
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