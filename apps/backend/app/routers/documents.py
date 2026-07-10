from fastapi import APIRouter, UploadFile, File

from app.services.storage import save_file


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...)
):

    saved_path = save_file(
        file.file,
        file.filename
    )


    return {
        "filename": file.filename,
        "path": str(saved_path)
    }