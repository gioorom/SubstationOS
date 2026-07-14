from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database.database import Base, SessionLocal, engine
from app.models import document
from app.routers import documents


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SubstationOS API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=[
        "*"
    ],
    allow_headers=[
        "*"
    ],
)


app.include_router(
    documents.router
)


@app.get("/")
def root():
    return {
        "message": "SubstationOS API running"
    }


@app.get("/health")
def health_check():
    database_status = "online"
    storage_status = "online"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "offline"

    storage_path = Path("../../storage/documents")

    try:
        storage_path.mkdir(
            parents=True,
            exist_ok=True
        )

        test_file = storage_path / ".healthcheck"
        test_file.write_text(
            "ok",
            encoding="utf-8"
        )
        test_file.unlink()
    except Exception:
        storage_status = "offline"

    overall_status = (
        "online"
        if database_status == "online"
        and storage_status == "online"
        else "warning"
    )

    return {
        "status": overall_status,
        "services": {
            "api": "online",
            "database": database_status,
            "storage": storage_status,
            "ai": "offline"
        }
    }