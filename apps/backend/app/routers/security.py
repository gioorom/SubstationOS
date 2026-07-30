"""
The API's authentication and authorization boundary.

**Deny by default.** Every route is authenticated unless it appears in
``PUBLIC_ROUTES`` below. That direction is the whole design: a router
added next year is protected because nobody did anything, and opening a
route is a visible edit to a short list in one file. The alternative -
a dependency on each of a hundred endpoints - fails the day somebody
forgets one, and nothing tells them.

``tests/api/test_api_security.py`` walks every path in the live OpenAPI
document and asserts that each is either declared public here or answers
an anonymous caller with `401`. That test is what turns "everything is
protected" from a claim into a fact.

Three concerns, kept apart exactly as the EPIC requires:

- **Authentication** - the middleware resolves a session cookie into an
  ``AuditIdentity``, or into nothing.
- **Authorization** - ``require_capability`` is a dependency a route
  declares; it reads the identity and a capability, and knows no
  transport.
- **Audit identity** - ``current_identity`` hands application services a
  verified actor. It is the only way one enters the application layer.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Iterator
from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.database import SessionLocal
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.infrastructure.identity.secrets_token_generator import (
    SecretsTokenGenerator,
)
from app.infrastructure.identity.sqlalchemy_session_repository import (
    SqlAlchemySessionRepository,
)
from app.infrastructure.identity.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services import authentication_service

SESSION_COOKIE = "substationos_session"
"""
The session token.

``HttpOnly``, so script cannot read it. This is the reason a cross-site
scripting flaw in this application is not automatically an account
takeover: the attacker can act as the user for as long as their script
runs, and cannot walk away with a credential that outlives the page.
"""

CSRF_COOKIE = "substationos_csrf"
"""
The CSRF token. Readable by script **on purpose** - the client has to
echo it in a header, which is the half of the check an attacker on
another origin cannot perform.
"""

CSRF_HEADER = "X-CSRF-Token"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Routes that answer without an identity, each one a deliberate choice.
#:
#: | Route | Why it is public |
#: |---|---|
#: | `/` | A liveness banner naming the service and nothing else. |
#: | `/health` | Read by orchestrators that hold no credential. |
#: | `/auth/login` | Where a credential is exchanged for a session. |
#: | `/auth/logout` | Ending a session must never require a live one. |
#: | `/auth/session` | Answers "am I signed in?" - `200` or `401`, no data. |
#: | `/openapi.json`, `/docs`, `/redoc` | The contract, not the content. |
#:
#: The API documentation is public deliberately and revisitably: it
#: describes the shape of the API, discloses no engineering data, and is
#: already committed to this repository as `openapi.json`. A deployment
#: that treats its API surface as confidential should remove these three.
PUBLIC_ROUTES: frozenset[str] = frozenset(
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


def csrf_token_for(session_token: str) -> str:
    """
    The CSRF token that belongs to one session token.

    A one-way function of a 256-bit secret the client already holds, so
    it needs no storage and is **bound to the session**: a token captured
    from one session cannot be replayed against another, which plain
    double-submit does not prevent.

    Knowing the CSRF token yields nothing - it cannot be inverted to the
    session token, and it authenticates no request on its own.
    """

    return hashlib.sha256(
        f"{session_token}|substationos-csrf".encode("utf-8")
    ).hexdigest()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Resolves the session cookie, then enforces the default.

    Runs on every request, including those that will 404. The identity it
    resolves is placed on ``request.state`` and read by the dependencies
    below; routes never touch cookies.

    It **must** be installed inside the CORS middleware (that is, added
    to the application *before* it), so a `401` it produces still carries
    the CORS headers a browser needs in order to read it. A 401 the
    browser reports as a network error is a 401 nobody can act on.
    """

    def __init__(
        self,
        app,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        clock: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory
        self._clock = clock

    async def dispatch(self, request: Request, call_next):
        # A preflight carries no cookies by design and must be answered
        # by the CORS layer, not refused here.
        if request.method == "OPTIONS":
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        identity, expires_at = self._resolve(token)

        request.state.identity = identity
        request.state.session_expires_at = expires_at

        if identity is None and not _is_public(request.url.path):
            return _unauthenticated_response()

        if identity is not None and _requires_csrf_check(request):
            if not _csrf_is_valid(request, token):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": (
                            "This request is missing a valid CSRF token."
                        )
                    },
                )

        return await call_next(request)

    def _resolve(
        self, token: str | None
    ) -> tuple[AuditIdentity | None, datetime | None]:
        """
        One session validation per request, and only one.

        The expiry is carried out alongside the identity so
        `GET /auth/session` can report it without re-reading a session
        this method has already loaded.
        """

        if not token:
            return (None, None)

        database = self._session_factory()

        try:
            validation = authentication_service.validate_session(
                SqlAlchemyUserRepository(database),
                SqlAlchemySessionRepository(database),
                SecretsTokenGenerator(),
                token=token,
                now=self._clock(),
            )
        finally:
            database.close()

        return (validation.identity, validation.expires_at)


def _is_public(path: str) -> bool:
    if path in PUBLIC_ROUTES:
        return True

    # Swagger UI's static assets hang off `/docs`; without this the
    # documentation page loads and renders nothing.
    return path.startswith("/docs/")


def _requires_csrf_check(request: Request) -> bool:
    return request.method not in SAFE_METHODS


def _csrf_is_valid(request: Request, session_token: str | None) -> bool:
    if session_token is None:
        return False

    presented = request.headers.get(CSRF_HEADER)

    if not presented:
        return False

    return hmac.compare_digest(presented, csrf_token_for(session_token))


def _unauthenticated_response() -> JSONResponse:
    """
    One answer for every way of not being authenticated.

    No token, an unknown token, a revoked one, an expired one and an idle
    one all produce this. The distinction is recorded internally and is
    never disclosed: telling a caller *which* would let them use the API
    to test whether a token they found is real.
    """

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Authentication is required."},
        headers={"WWW-Authenticate": "Cookie"},
    )


# --- Dependencies --------------------------------------------------------


def current_identity(request: Request) -> AuditIdentity:
    """
    The verified identity of this request.

    Raises `401` rather than returning ``None``, so a route that declares
    it can never accidentally proceed anonymously. On a protected route
    the middleware has already refused anonymous callers; this is the
    second lock, and it is what makes the dependency safe to use on a
    route somebody later adds to ``PUBLIC_ROUTES``.
    """

    identity = getattr(request.state, "identity", None)

    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    return identity


def optional_identity(request: Request) -> AuditIdentity | None:
    """The identity, or ``None``. For public routes that adapt to it."""

    return getattr(request.state, "identity", None)


def session_expires_at(request: Request) -> datetime | None:
    """The current session's absolute ceiling, if there is a session."""

    return getattr(request.state, "session_expires_at", None)


def require_capability(
    capability: Capability,
) -> Callable[[Request], AuditIdentity]:
    """
    A dependency that admits only identities carrying ``capability``.

    Declares *what the route needs*, never *which role has it*. When
    project membership arrives, a capability can be granted from a second
    source without any route changing.

    `403`, not `401`: the caller is authenticated and this is not a
    credential problem, so telling them to authenticate again would send
    them round a loop that cannot succeed.
    """

    def dependency(request: Request) -> AuditIdentity:
        identity = current_identity(request)

        if not identity.permits(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This action requires a permission your role does "
                    "not carry."
                ),
            )

        return identity

    return dependency


require_administrator = require_capability(Capability.MANAGE_USERS)
"""Shorthand for the administrator-only routes."""


def audit_session(request: Request) -> Iterator[Session]:
    """
    A database session for writing audit events.

    Separate from a router's own ``get_db`` on purpose: an audit write
    must not join the transaction of the action it records, or a rollback
    would take the evidence with it.
    """

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


def install_security(
    app,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """
    Installs the authentication middleware on an application.

    Used by ``app.main`` and by the test fixtures, so the application the
    tests exercise is protected exactly as the real one is. A test suite
    running against an unprotected copy of the app would assert nothing
    about security.
    """

    app.add_middleware(
        AuthenticationMiddleware, session_factory=session_factory
    )
