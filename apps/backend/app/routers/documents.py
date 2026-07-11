from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from app.services.storage import save_file

from app.database.database import SessionLocal
from app.models.document import Document


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
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
    db: Session = Depends(get_db)
):

    saved_path = save_file(
        file.file,
        file.filename
    )


    document = Document(
        filename=file.filename,
        file_path=str(saved_path)
    )


    db.add(document)
    db.commit()
    db.refresh(document)


    return {
        "id": document.id,
        "filename": document.filename,
        "path": document.file_path,
        "uploaded_at": document.uploaded_at
    }