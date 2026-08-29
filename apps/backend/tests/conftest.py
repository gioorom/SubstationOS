from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.routers import audit as audit_router_module
from app.routers import authentication as authentication_router_module
from app.routers import canonical_pdf as canonical_pdf_router_module
from app.routers import canonical_text as canonical_text_router_module
from app.routers import canonicalization as canonicalization_router_module
from app.routers import conversation as conversation_router_module
from app.routers import document_ingestion as document_ingestion_router_module
from app.routers import documents as documents_router_module
from app.routers import engineering_engine as engineering_engine_router_module
from app.routers import engineering_entities as engineering_entities_router_module
from app.routers import engineering_evidence as engineering_evidence_router_module
from app.routers import engineering_facts as engineering_facts_router_module
from app.routers import engineering_semantics as engineering_semantics_router_module
from app.routers import engineering_index as engineering_index_router_module
from app.routers import evidence_evaluation as evidence_evaluation_router_module
from app.routers import governed_retrieval as governed_retrieval_router_module
from app.routers import engineering_intent as engineering_intent_router_module
from app.routers import (
    engineering_request_preparation as engineering_request_preparation_router_module,
)
from app.routers import engineering_response as engineering_response_router_module
from app.routers import engineering_session as engineering_session_router_module
from app.routers import governed_knowledge_graph as governed_graph_router_module
from app.routers import human_review as human_review_router_module
from app.routers import llm_provider as llm_provider_router_module
from app.routers import projects as projects_router_module
from app.routers import prompt_builder as prompt_builder_router_module
from app.routers import proposed_claims as proposed_claims_router_module
from app.routers import review_workflow as review_workflow_router_module
from app.routers import users as users_router_module
from app.routers import working_memory as working_memory_router_module
from app.routers.security import install_security


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker]:
    """
    A fresh, isolated, in-memory SQLite database for a single test, as a
    **factory**.

    A factory rather than a session, because the authentication
    middleware opens and closes one of its own on every request - it runs
    outside any route's dependency graph, so it cannot be handed the
    session a router was given. Both come from here and share one
    connection, so what a request writes is what the test reads.
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    try:
        yield sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(session_factory: sessionmaker) -> Iterator[Session]:
    """The session a test and its routers share."""

    session = session_factory()

    try:
        yield session
    finally:
        session.close()


# --- Identity ------------------------------------------------------------
#
# Since EPIC 30.3 the API denies anonymous callers by default, so a test
# client has to be somebody. These fixtures make it cheap to be.
#
# The credential below is a **fixed, non-secret literal**. Sessions are
# created directly rather than through `POST /auth/login`, so no test
# fixture ever verifies it, and paying for a memory-hard key derivation
# per test would add minutes to the suite for no assertion. The tests
# that exercise login itself create their users properly and pay the real
# cost - see `tests/api/test_authentication_api.py`.

UNUSED_TEST_CREDENTIAL = "scrypt$n=2,r=8,p=1$dGVzdHNhbHQ$dGVzdGRpZ2VzdA"


def _make_user(
    db_session: Session,
    *,
    email: str,
    display_name: str,
    role: "Role",
) -> "User":
    from app.domain.identity.identity_models import (
        DisplayName,
        EmailAddress,
        User,
        UserStatus,
    )
    from app.infrastructure.identity.sqlalchemy_user_repository import (
        SqlAlchemyUserRepository,
    )

    now = datetime(2026, 7, 30, 9, 0, 0)

    return SqlAlchemyUserRepository(db_session).add(
        User(
            user_id=None,
            email=EmailAddress(email),
            display_name=DisplayName(display_name),
            role=role,
            status=UserStatus.ACTIVE,
            encoded_credential=UNUSED_TEST_CREDENTIAL,
            created_at=now,
            credential_updated_at=now,
        )
    )


@pytest.fixture()
def engineer(db_session: Session):
    """The ordinary authenticated user every engineering test acts as."""

    from app.domain.identity.identity_roles import Role

    return _make_user(
        db_session,
        email="engineer@substationos.test",
        display_name="Test Engineer",
        role=Role.ENGINEER,
    )


@pytest.fixture()
def administrator(db_session: Session):
    from app.domain.identity.identity_roles import Role

    return _make_user(
        db_session,
        email="administrator@substationos.test",
        display_name="Test Administrator",
        role=Role.ADMINISTRATOR,
    )


def authenticate(client: TestClient, db_session: Session, user) -> str:
    """
    Opens a session for ``user`` and points ``client`` at it.

    Writes the session row directly and sets both cookies, which is
    exactly what a real login produces - minus the key derivation. The
    CSRF header is set once on the client because every unsafe request a
    test makes would otherwise need it, and forgetting it would fail
    tests for a reason unrelated to what they assert.
    """

    from app.domain.identity.session_models import AuthenticationSession
    from app.domain.identity.session_policy import DEFAULT_SESSION_POLICY
    from app.infrastructure.identity.secrets_token_generator import (
        SecretsTokenGenerator,
    )
    from app.infrastructure.identity.sqlalchemy_session_repository import (
        SqlAlchemySessionRepository,
    )
    from app.routers.security import (
        CSRF_COOKIE,
        CSRF_HEADER,
        SESSION_COOKIE,
        csrf_token_for,
    )

    tokens = SecretsTokenGenerator()
    token = tokens.issue()
    now = datetime.utcnow()

    SqlAlchemySessionRepository(db_session).add(
        AuthenticationSession(
            session_id=None,
            user_id=user.user_id,
            token_fingerprint=tokens.fingerprint(token),
            issued_at=now,
            last_seen_at=now,
            expires_at=DEFAULT_SESSION_POLICY.expires_at(now),
            revoked_at=None,
        )
    )

    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE, csrf_token_for(token))
    client.headers[CSRF_HEADER] = csrf_token_for(token)

    return token


@pytest.fixture()
def secured_app(db_session: Session, session_factory: sessionmaker):
    """
    The application under test, wired to the isolated database and
    **protected exactly as the real one is**.

    Deliberately builds a minimal app rather than importing ``app.main``,
    which creates tables against the on-disk dev database as an
    import-time side effect.

    Since EPIC 30.3 it installs the same authentication middleware
    ``app.main`` does, through the same function. A test suite running
    against an unprotected copy of the application would assert nothing
    at all about its security, and `test_api_security.py` in particular
    would be theatre.
    """

    test_app = FastAPI()
    test_app.include_router(authentication_router_module.router)
    test_app.include_router(users_router_module.router)
    test_app.include_router(audit_router_module.router)
    test_app.include_router(human_review_router_module.router)
    test_app.include_router(governed_graph_router_module.router)
    test_app.include_router(governed_retrieval_router_module.router)
    test_app.include_router(projects_router_module.router)
    test_app.include_router(documents_router_module.router)
    test_app.include_router(document_ingestion_router_module.router)
    test_app.include_router(canonical_pdf_router_module.router)
    test_app.include_router(canonical_text_router_module.router)
    test_app.include_router(engineering_evidence_router_module.router)
    test_app.include_router(engineering_entities_router_module.router)
    test_app.include_router(engineering_facts_router_module.router)
    test_app.include_router(engineering_semantics_router_module.router)
    test_app.include_router(evidence_evaluation_router_module.router)
    test_app.include_router(engineering_index_router_module.router)
    test_app.include_router(proposed_claims_router_module.router)
    test_app.include_router(review_workflow_router_module.router)
    test_app.include_router(canonicalization_router_module.router)
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
        engineering_entities_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        engineering_facts_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        engineering_semantics_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        evidence_evaluation_router_module.get_db
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
        engineering_engine_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        governed_retrieval_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        authentication_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        users_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        audit_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        human_review_router_module.get_db
    ] = _override_get_db
    test_app.dependency_overrides[
        governed_graph_router_module.get_db
    ] = _override_get_db

    # The middleware runs outside every route's dependency graph, so it
    # cannot be handed an override - it is given the factory instead, and
    # opens a session from the same connection the test is using.
    install_security(test_app, session_factory=session_factory)

    return test_app


@pytest.fixture()
def anonymous_client(secured_app) -> Iterator[TestClient]:
    """A client with no session. Every protected route answers it 401."""

    with TestClient(secured_app) as client:
        yield client


@pytest.fixture()
def api_client(
    secured_app, db_session: Session, engineer
) -> Iterator[TestClient]:
    """
    The default client: an authenticated engineer.

    Every test written before EPIC 30.3 uses this fixture and keeps
    passing, which is the point - authentication was added to the
    platform without changing what the platform does.
    """

    with TestClient(secured_app) as client:
        authenticate(client, db_session, engineer)
        yield client


@pytest.fixture()
def administrator_client(
    secured_app, db_session: Session, administrator
) -> Iterator[TestClient]:
    """An authenticated administrator, for the routes that require one."""

    with TestClient(secured_app) as client:
        authenticate(client, db_session, administrator)
        yield client
