from pathlib import Path
import shutil


BASE_STORAGE = Path(
    "../../storage"
)


def save_file(
    uploaded_file,
    filename: str,
    folder: str = "documents"
):

    storage_path = BASE_STORAGE / folder

    storage_path.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = storage_path / filename


    with file_path.open("wb") as buffer:
        shutil.copyfileobj(
            uploaded_file,
            buffer
        )


    return file_path