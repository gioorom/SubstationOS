"""
The authentication API, end to end.

These are the only tests that pay for real key derivations, because they
are the only ones exercising the login path. Everywhere else the fixtures
open a session directly - see ``conftest``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.identity.identity_roles import Role
from app.infrastructure.identity.scrypt_password_hasher import (
    ScryptPasswordHasher,
)
from app.infrastructure.identity.sqlalchemy_session_repository import (
    SqlAlchemySessionRepository,
)
from app.infrastructure.identity.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.routers.security import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    csrf_token_for,
)
from app.services import user_service

PASSWORD = "cavallo batteria graffetta"

OTHER_PASSWORD = "una password completamente diversa"


@pytest.fixture()
def registered(db_session: Session):
    """
    A real account, with a real hash.

    Uses reduced scrypt parameters: this suite asserts the *behaviour* of
    logging in, and production cost parameters would add minutes without
    changing a single assertion.
    """

    return user_service.create_user(
        SqlAlchemyUserRepository(db_session),
        ScryptPasswordHasher(cost=2**8, block_size=4),
        email="ada@substationos.test",
        display_name="Ada Lovelace",
        password=PASSWORD,
        role=Role.ENGINEER,
        now=datetime.utcnow(),
    )


def _login(
    client: TestClient, email: str, password: str
):
    return client.post(
        "/auth/login", json={"email": email, "password": password}
    )


# --- Logging in ----------------------------------------------------------


def test_correct_credentials_open_a_session(
    anonymous_client: TestClient, registered
) -> None:
    response = _login(anonymous_client, "ada@substationos.test", PASSWORD)

    assert response.status_code == 200
    assert response.json()["identity"]["email"] == "ada@substationos.test"
    assert response.json()["identity"]["role"] == "engineer"


def test_the_session_token_is_never_in_the_response_body(
    anonymous_client: TestClient, registered
) -> None:
    """
    The token leaves the server exactly once, as a cookie. A body
    carrying it would be readable by script, which is the whole thing
    ``HttpOnly`` prevents.
    """

    response = _login(anonymous_client, "ada@substationos.test", PASSWORD)
    token = anonymous_client.cookies.get(SESSION_COOKIE)

    assert token
    assert token not in response.text


def test_the_session_cookie_is_http_only_and_same_site(
    anonymous_client: TestClient, registered
) -> None:
    response = _login(anonymous_client, "ada@substationos.test", PASSWORD)

    session_cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(SESSION_COOKIE)
    )

    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie.replace("samesite", "SameSite")


def test_the_csrf_cookie_is_readable_by_script_on_purpose(
    anonymous_client: TestClient, registered
) -> None:
    """
    The client has to echo it in a header, which is the half of the check
    an attacker on another origin cannot perform.
    """

    response = _login(anonymous_client, "ada@substationos.test", PASSWORD)

    csrf_cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(CSRF_COOKIE)
    )

    assert "HttpOnly" not in csrf_cookie


def test_the_login_email_is_case_insensitive(
    anonymous_client: TestClient, registered
) -> None:
    assert (
        _login(anonymous_client, "ADA@SubstationOS.test", PASSWORD).status_code
        == 200
    )


def test_a_password_is_never_echoed_back(
    anonymous_client: TestClient, registered
) -> None:
    response = _login(anonymous_client, "ada@substationos.test", PASSWORD)

    assert PASSWORD not in response.text


# --- Refusals ------------------------------------------------------------


def test_a_wrong_password_is_refused(
    anonymous_client: TestClient, registered
) -> None:
    assert (
        _login(
            anonymous_client, "ada@substationos.test", OTHER_PASSWORD
        ).status_code
        == 401
    )


def test_an_unknown_address_and_a_wrong_password_are_indistinguishable(
    anonymous_client: TestClient, registered
) -> None:
    """
    The refusal that keeps this login form from being a service for
    discovering who has an account here.
    """

    unknown = _login(anonymous_client, "nobody@substationos.test", PASSWORD)
    wrong = _login(anonymous_client, "ada@substationos.test", OTHER_PASSWORD)

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_a_disabled_account_is_refused_indistinguishably(
    anonymous_client: TestClient, db_session: Session, registered
) -> None:
    from app.domain.identity.identity_models import UserStatus

    user_service.set_status(
        SqlAlchemyUserRepository(db_session),
        SqlAlchemySessionRepository(db_session),
        user_id=registered.user_id,
        status=UserStatus.DISABLED,
        now=datetime.utcnow(),
    )

    disabled = _login(anonymous_client, "ada@substationos.test", PASSWORD)
    unknown = _login(anonymous_client, "nobody@substationos.test", PASSWORD)

    assert disabled.status_code == 401
    assert disabled.json() == unknown.json()


def test_a_malformed_address_is_refused_like_any_other(
    anonymous_client: TestClient, registered
) -> None:
    assert _login(anonymous_client, "not-an-address", PASSWORD).status_code == 401


# --- The session ---------------------------------------------------------


def test_a_session_authenticates_subsequent_requests(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)

    assert anonymous_client.get("/auth/session").status_code == 200
    assert anonymous_client.get("/projects/").status_code == 200


def test_the_session_endpoint_refuses_an_anonymous_caller(
    anonymous_client: TestClient,
) -> None:
    assert anonymous_client.get("/auth/session").status_code == 401


def test_two_logins_produce_two_independent_sessions(
    anonymous_client: TestClient, secured_app, registered
) -> None:
    """
    Multiple sessions are supported: an engineer at a workstation and on
    a laptop is one person with two logins, and one must not end the
    other.
    """

    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    first = anonymous_client.cookies.get(SESSION_COOKIE)

    with TestClient(secured_app) as second_client:
        _login(second_client, "ada@substationos.test", PASSWORD)
        second = second_client.cookies.get(SESSION_COOKIE)

        assert first != second
        assert second_client.get("/auth/session").status_code == 200

    assert anonymous_client.get("/auth/session").status_code == 200


def test_a_forged_token_authenticates_nothing(
    anonymous_client: TestClient, registered
) -> None:
    anonymous_client.cookies.set(SESSION_COOKIE, "not-a-real-token")

    assert anonymous_client.get("/auth/session").status_code == 401


def test_a_session_expires_when_its_absolute_lifetime_runs_out(
    anonymous_client: TestClient, db_session: Session, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)

    sessions = SqlAlchemySessionRepository(db_session)
    live = sessions.list_active_for_user(registered.user_id)[0]

    # Reach into the stored session rather than waiting twelve hours.
    sessions.save(
        live.__class__(
            session_id=live.session_id,
            user_id=live.user_id,
            token_fingerprint=live.token_fingerprint,
            issued_at=live.issued_at,
            last_seen_at=live.last_seen_at,
            expires_at=datetime.utcnow() - timedelta(seconds=1),
            revoked_at=None,
        )
    )

    assert anonymous_client.get("/auth/session").status_code == 401


def test_disabling_a_user_ends_their_live_sessions_at_once(
    anonymous_client: TestClient, db_session: Session, registered
) -> None:
    """
    Otherwise "disabled" would mean "may not log in again", and an
    account disabled because of an incident would keep working for hours.
    """

    from app.domain.identity.identity_models import UserStatus

    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    assert anonymous_client.get("/auth/session").status_code == 200

    user_service.set_status(
        SqlAlchemyUserRepository(db_session),
        SqlAlchemySessionRepository(db_session),
        user_id=registered.user_id,
        status=UserStatus.DISABLED,
        now=datetime.utcnow(),
    )

    assert anonymous_client.get("/auth/session").status_code == 401


# --- Logging out ---------------------------------------------------------


def test_logout_ends_the_session(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    token = anonymous_client.cookies.get(SESSION_COOKIE)

    response = anonymous_client.post(
        "/auth/logout", headers={CSRF_HEADER: csrf_token_for(token)}
    )

    assert response.status_code == 204

    anonymous_client.cookies.set(SESSION_COOKIE, token)
    assert anonymous_client.get("/auth/session").status_code == 401


def test_logout_without_a_session_still_succeeds(
    anonymous_client: TestClient,
) -> None:
    """
    Answering differently would make logout a way to test whether a
    stolen token is still live.
    """

    assert anonymous_client.post("/auth/logout").status_code == 204


def test_logout_is_idempotent(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    token = anonymous_client.cookies.get(SESSION_COOKIE)
    headers = {CSRF_HEADER: csrf_token_for(token)}

    assert anonymous_client.post("/auth/logout", headers=headers).status_code == 204

    anonymous_client.cookies.set(SESSION_COOKIE, token)
    assert anonymous_client.post("/auth/logout", headers=headers).status_code == 204


def test_logout_clears_both_cookies(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    token = anonymous_client.cookies.get(SESSION_COOKIE)

    response = anonymous_client.post(
        "/auth/logout", headers={CSRF_HEADER: csrf_token_for(token)}
    )

    cleared = " ".join(response.headers.get_list("set-cookie"))

    assert SESSION_COOKIE in cleared
    assert CSRF_COOKIE in cleared


# --- CSRF ----------------------------------------------------------------


def test_an_unsafe_request_without_the_csrf_header_is_refused(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)

    response = anonymous_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    )

    assert response.status_code == 403


def test_an_unsafe_request_with_a_wrong_csrf_token_is_refused(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)

    response = anonymous_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
        headers={CSRF_HEADER: csrf_token_for("a different session token")},
    )

    assert response.status_code == 403


def test_a_safe_request_needs_no_csrf_token(
    anonymous_client: TestClient, registered
) -> None:
    _login(anonymous_client, "ada@substationos.test", PASSWORD)

    assert anonymous_client.get("/projects/").status_code == 200


def test_the_csrf_token_is_bound_to_its_session(
    anonymous_client: TestClient, registered
) -> None:
    """
    Plain double-submit would accept any value that appeared in both
    places. Deriving the token from the session token means one captured
    from another session is useless.
    """

    _login(anonymous_client, "ada@substationos.test", PASSWORD)
    token = anonymous_client.cookies.get(SESSION_COOKIE)

    assert csrf_token_for(token) != csrf_token_for(token + "x")
    assert token not in csrf_token_for(token)
