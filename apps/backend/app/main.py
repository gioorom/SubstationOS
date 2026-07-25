from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database.database import SessionLocal

# Imported for their side effect of registering every table/relationship
# with the ORM mapper before any request is handled - not for schema
# creation (see the Alembic note below). Kept explicit, rather than
# relying on routers transitively importing the same modules, so mapper
# configuration does not depend on router import order.
from app.models import (  # noqa: F401
    canonicalization,
    document,
    engineering_index,
    graph_builder,
    knowledge_graph,
    project,
    project_knowledge_graph,
    proposed_claims,
    review_workflow,
)
from app.routers import (
    canonicalization as canonicalization_router,
    documents,
    engineering_index as engineering_index_router,
    graph_builder as graph_builder_router,
    graph_query as graph_query_router,
    knowledge_graph,
    project_knowledge_graph as project_knowledge_graph_router,
    projects,
    proposed_claims as proposed_claims_router,
    review_workflow as review_workflow_router,
    structured_retrieval as structured_retrieval_router,
)

load_dotenv()

# Schema lifecycle is managed by Alembic (see
# docs/architecture/database_migrations.md), not by application startup.
# Startup deliberately does not create or alter tables - a database that
# has not been migrated (`alembic upgrade head`) is expected to fail
# loudly at first query, not be silently patched into shape. The one
# exception is the isolated, in-memory test database
# (tests/conftest.py's `db_session` fixture), which still uses
# `Base.metadata.create_all()` because it is disposable and rebuilt
# fresh for every test - never this application's real schema.


app = FastAPI(
    title="SubstationOS API",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=[
        "*",
    ],
    allow_headers=[
        "*",
    ],
)


app.include_router(documents.router)
app.include_router(projects.router)
app.include_router(knowledge_graph.router)
app.include_router(engineering_index_router.router)
app.include_router(proposed_claims_router.router)
app.include_router(review_workflow_router.router)
app.include_router(canonicalization_router.router)
app.include_router(graph_builder_router.router)
app.include_router(project_knowledge_graph_router.router)
app.include_router(graph_query_router.router)
app.include_router(structured_retrieval_router.router)


@app.get("/")
def root():
    return {
        "message": "SubstationOS API running",
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
            exist_ok=True,
        )

        test_file = storage_path / ".healthcheck"

        test_file.write_text(
            "ok",
            encoding="utf-8",
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
            "ai": "offline",
        },
    }