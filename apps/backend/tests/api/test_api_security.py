"""
The API's security boundary, asserted rather than asserted-to.

The centrepiece is ``test_every_route_is_protected_or_declared_public``:
it walks **every path in the live OpenAPI document** and requires each
one to be either on the public list or to refuse an anonymous caller.
A router added next year is covered by it without anybody remembering to
add a test, which is the only kind of coverage that survives a codebase
this size.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.routers.security import CSRF_HEADER, PUBLIC_ROUTES, SESSION_COOKIE
from app.schemas import identity as identity_schemas

#: A value for each path parameter, so a URL can be built for any route.
#: The ids are deliberately ones that do not exist: an anonymous request
#: must be refused *before* anything looks for the resource, and a `404`
#: here would mean the lookup happened first.
_PATH_PARAMETER_VALUES = {
    "baseline_report_id": "999999",
    "batch_id": "999999",
    "candidate_id": "999999",
    "candidate_report_id": "999999",
    "claim_id": "999999",
    "corpus_id": "999999",
    "document_id": "999999",
    "entity_id": "999999",
    "entity_key": "nope",
    "entry_id": "999999",
    "execution_id": "999999",
    "fact_id": "999999",
    "fact_key": "nope",
    "graph_entity_id": "999999",
    "job_id": "999999",
    "page_number": "1",
    "project_id": "999999",
    "report_id": "999999",
    "statement_key": "nope",
    "type": "nope",
    "user_id": "999999",
}


def _concrete(path: str) -> str:
    concrete = path

    for name, value in _PATH_PARAMETER_VALUES.items():
        concrete = concrete.replace(f"{{{name}}}", value)

    return concrete


def _routes(client: TestClient) -> list[tuple[str, str]]:
    schema = client.app.openapi()

    return [
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}
    ]


def test_the_test_can_build_a_url_for_every_route(
    anonymous_client: TestClient,
) -> None:
    """
    A guard on the guard.

    If a new route introduced a path parameter this module does not know,
    the sweep below would silently request a literal `{whatever}` - which
    might 404 for the wrong reason and look like a pass.
    """

    unresolved = [
        path
        for _, path in _routes(anonymous_client)
        if "{" in _concrete(path)
    ]

    assert unresolved == []


def test_every_route_is_protected_or_declared_public(
    anonymous_client: TestClient,
) -> None:
    """
    Deny by default, proved one route at a time.

    A route that is neither on the public list nor answers `401` is a
    hole, and this test names it.
    """

    holes: list[str] = []

    for method, path in _routes(anonymous_client):
        if path in PUBLIC_ROUTES:
            continue

        response = anonymous_client.request(method, _concrete(path))

        if response.status_code != 401:
            holes.append(f"{method} {path} -> {response.status_code}")

    assert holes == []


def test_the_public_list_is_short_and_deliberate() -> None:
    """
    Every entry is a decision somebody made. This test is what turns
    adding one into a decision somebody has to defend.
    """

    assert PUBLIC_ROUTES == frozenset(
        {
            "/",
            "/health",
            "/openapi.json",
            "/docs",
            "/docs/oauth2-redirect",
            "/redoc",
            "/auth/login",
            "/auth/logout",
            "/auth/session",
        }
    )


def test_the_root_banner_answers_anonymously() -> None:
    """
    Checked against the real application, because `/` and `/health` are
    declared on it directly rather than on a router the test app
    includes.

    `/health` is deliberately **not** exercised here: it writes a probe
    file into the storage root and queries the configured database, and a
    unit test has no business doing either on a developer's machine. That
    it is public is asserted by the list test above, and that it is
    *meant* to be is recorded in `PUBLIC_ROUTES`.
    """

    import app.main

    with TestClient(app.main.app) as client:
        assert client.get("/").status_code == 200


def test_a_refusal_does_not_say_why(anonymous_client: TestClient) -> None:
    """
    No token, an unknown token, a revoked one and an expired one all
    produce the same body. Telling a caller which would let them use the
    API to test whether a token they found is real.
    """

    without = anonymous_client.get("/projects/")

    anonymous_client.cookies.set(SESSION_COOKIE, "a-token-that-is-not-real")
    with_forged = anonymous_client.get("/projects/")

    assert without.status_code == with_forged.status_code == 401
    assert without.json() == with_forged.json()


def test_a_refusal_names_no_user_and_no_route_internals(
    anonymous_client: TestClient,
) -> None:
    body = anonymous_client.get("/projects/").text.lower()

    for leak in ("sql", "traceback", "sqlalchemy", "session_id", "cookie="):
        assert leak not in body


# --- Authorization -------------------------------------------------------


def test_an_engineer_may_use_the_engineering_platform(
    api_client: TestClient,
) -> None:
    assert api_client.get("/projects/").status_code == 200


def test_an_engineer_may_not_administer_users(
    api_client: TestClient,
) -> None:
    """
    `403`, not `401`: the caller is authenticated and this is not a
    credential problem, so telling them to authenticate again would send
    them round a loop that cannot succeed.
    """

    assert api_client.get("/users/").status_code == 403


def test_an_engineer_may_not_read_the_audit_trail(
    api_client: TestClient,
) -> None:
    assert api_client.get("/audit/events").status_code == 403


def test_an_administrator_may(
    administrator_client: TestClient,
) -> None:
    assert administrator_client.get("/users/").status_code == 200
    assert administrator_client.get("/audit/events").status_code == 200


def test_anyone_authenticated_may_read_their_own_identity(
    api_client: TestClient,
) -> None:
    response = api_client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "engineer@substationos.test"
    assert response.json()["role"] == "engineer"


# --- Nothing secret is representable in the contract ---------------------


def test_no_identity_response_schema_declares_a_secret_field() -> None:
    """
    Structural: a field that does not exist cannot be populated by
    accident three refactors from now.
    """

    forbidden = ("password", "credential", "hash", "salt", "secret", "token")

    response_models = [
        identity_schemas.IdentityRead,
        identity_schemas.SessionRead,
        identity_schemas.UserRead,
        identity_schemas.UserListResponse,
        identity_schemas.AuditEventRead,
        identity_schemas.AuditActorRead,
    ]

    offenders = [
        f"{model.__name__}.{field}"
        for model in response_models
        for field in model.model_fields
        if any(item in field.lower() for item in forbidden)
    ]

    assert offenders == []


def test_a_user_listing_carries_no_credential(
    administrator_client: TestClient,
) -> None:
    body = administrator_client.get("/users/").text.lower()

    for leak in ("scrypt", "credential", "password", "salt", "digest"):
        assert leak not in body


def test_the_stored_credential_is_never_the_password(
    db_session: Session, engineer
) -> None:
    from app.infrastructure.identity.sqlalchemy_user_repository import (
        SqlAlchemyUserRepository,
    )

    stored = SqlAlchemyUserRepository(db_session).find_by_id(
        engineer.user_id
    )

    assert stored is not None
    assert "$" in stored.encoded_credential


# --- CSRF ----------------------------------------------------------------


def test_an_unsafe_request_without_a_csrf_header_is_refused(
    api_client: TestClient,
) -> None:
    del api_client.headers[CSRF_HEADER]

    response = api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    )

    assert response.status_code == 403


def test_a_read_needs_no_csrf_header(api_client: TestClient) -> None:
    del api_client.headers[CSRF_HEADER]

    assert api_client.get("/projects/").status_code == 200
