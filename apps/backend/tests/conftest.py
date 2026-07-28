from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.routers import canonical_pdf as canonical_pdf_router_module
from app.routers import canonical_text as canonical_text_router_module
from app.routers import canonicalization as canonicalization_router_module
from app.routers import context_builder as context_builder_router_module
from app.routers import conversation as conversation_router_module
from app.routers import document_ingestion as document_ingestion_router_module
from app.routers import documents as documents_router_module
from app.routers import engineering_engine as engineering_engine_router_module
from app.routers import engineering_evidence as engineering_evidence_router_module
from app.routers import engineering_index as engineering_index_router_module
from app.routers import engineering_intent as engineering_intent_router_module
from app.routers import (
    engineering_request_preparation as engineering_request_preparation_router_module,
)
from app.routers import engineering_response as engineering_response_router_module
from app.routers import engineering_session as engineering_session_router_module
from app.routers import graph_builder as graph_builder_router_module
from app.routers import graph_query as graph_query_router_module
from app.routers import (
    project_knowledge_graph as project_knowledge_graph_router_module,
)
from app.routers import llm_provider as llm_provider_router_module
from app.routers import projects as projects_router_module
from app.routers import prompt_builder as prompt_builder_router_module
from app.routers import proposed_claims as proposed_claims_router_module
from app.routers import review_workflow as review_workflow_router_module
from app.routers import (
    structured_retrieval as structured_retrieval_router_module,
)
from app.routers import working_memory as working_memory_router_module


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """
    A fresh, isolated, in-memory SQLite database for a single test.
    Never touches the on-disk dev databases in apps/backend/.
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = testing_session_local()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def api_client(db_session: Session) -> Iterator[TestClient]:
    """
    A FastAPI TestClient wired to the real Projects, Documents,
    Engineering Index, Proposed Claims, Review Workflow, and
    Canonicalization routers, backed by the isolated ``db_session``.
    Deliberately builds a minimal
    app rather than importing ``app.main``, since ``app.main`` creates
    tables against the real on-disk dev database as an import-time side
    effect.
    """

    test_app = FastAPI()
    test_app.include_router(projects_router_module.router)
    test_app.include_router(documents_router_module.router)
    test_app.include_router(document_ingestion_router_module.router)
    test_app.include_router(canonical_pdf_router_module.router)
    test_app.include_router(canonical_text_router_module.router)
    test_app.include_router(engineering_evidence_router_module.router)
    test_app.include_router(engineering_index_router_module.router)
    test_app.include_router(proposed_claims_router_module.router)
    test_app.include_router(review_workflow_router_module.router)
    test_app.include_router(canonicalization_router_module.router)
    test_app.include_router(graph_builder_router_module.router)
    test_app.include_router(project_knowledge_graph_router_module.router)
    test_app.include_router(graph_query_router_module.router)
    test_app.include_router(structured_retrieval_router_module.router)
    test_app.include_router(context_builder_router_module.router)
    test_app.include_router(prompt_builder_router_module.router)
    test_app.include_router(llm_provider_router_module.router)
    test_app.include_router(engineering_response_router_module.router)
    test_app.include_router(engineering_session_router_module.router)
    test_app.include_router(conversation_router_module.router)
    test_app.include_router(working_memory_router_module.router)
    test_app.include_router(engineering_intent_router_module.router)
    test_app.include_router(
        engineering_request_preparation_router_module.router
    )
    test_app.include_router(engineering_engine_router_module.router)

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    test_app.dependency_overrides[
        projects_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        documents_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        document_ingestion_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        canonical_pdf_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        canonical_text_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        engineering_evidence_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        engineering_index_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        proposed_claims_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        review_workflow_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        canonicalization_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        graph_builder_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        project_knowledge_graph_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        graph_query_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        structured_retrieval_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        engineering_engine_router_module.get_db
    ] = _override_get_db

    with TestClient(test_app) as client:
        yield client
