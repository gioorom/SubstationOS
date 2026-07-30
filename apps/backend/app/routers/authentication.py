"""
The authentication API.

```
POST /auth/login     exchange a password for a session
POST /auth/logout    end the current session
GET  /auth/session   who am I, and until when
```

All three are public, and each for a different reason: you cannot present
a session before you have one, ending a session must never require a live
one, and "am I signed in?" has to be answerable by a client that does not
yet know.

**The session token leaves the server only as a cookie.** No response
body in this module contains it. That is what makes an XSS flaw in the
frontend a limited incident rather than a credential theft.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.domain.identity.session_policy import DEFAULT_SESSION_POLICY
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.infrastructure.identity.scrypt_password_hasher import (
    ScryptPasswordHasher,
)
from app.infrastructure.identity.secrets_token_generator import (
    SecretsTokenGenerator,
)
from app.infrastructure.identity.sqlalchemy_session_repository import (
    SqlAlchemySessionRepository,
)
from app.infrastructure.identity.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.routers.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    csrf_token_for,
    optional_identity,
    session_expires_at,
)
from app.schemas.identity import IdentityRead, LoginRequest, SessionRead
from app.services import audit_service, authentication_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


#: Cookies are host-only and path-wide. `Secure` is **not** set here so
#: the platform runs over plain HTTP in development; a deployment behind
#: TLS must set it, and `security_architecture.md` says so in the one
#: place an operator will look.
_COOKIE_PATH = "/"

_SAME_SITE = "lax"


@router.post(
    "/login",
    response_model=SessionRead,
    responses={
        401: {
            "description": (
                "The credentials were refused. The response does not say "
                "which part was wrong, deliberately."
            )
        }
    },
    summary="Exchange a password for a session",
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionRead:
    now = datetime.utcnow()
    audit = SqlAlchemyAuditRepository(db)

    result = authentication_service.authenticate(
        SqlAlchemyUserRepository(db),
        SqlAlchemySessionRepository(db),
        ScryptPasswordHasher(),
        SecretsTokenGenerator(),
        email=payload.email,
        password=payload.password,
        now=now,
        policy=DEFAULT_SESSION_POLICY,
    )

    if not result.succeeded:
        audit_service.record_anonymous(
            audit,
            action=AuditAction.LOGIN_FAILED,
            outcome=AuditOutcome.DENIED,
            resource=AuditResource("authentication"),
            now=now,
            attempted_identifier=payload.email[:120],
            # The typed cause is recorded for whoever reads the trail,
            # and is never in the response the caller sees.
            detail=result.failure.value if result.failure else None,
        )

        # One status, one sentence, for every way of failing. See
        # `authentication_service.authenticate` on user enumeration.
        raise _refused()

    _issue_session_cookies(response, result.token)

    audit_service.record_for_identity(
        audit,
        identity=result.identity,
        action=AuditAction.LOGIN_SUCCEEDED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource("authentication"),
        now=now,
    )

    return SessionRead(
        identity=IdentityRead(
            user_id=result.identity.user_id,
            email=result.identity.email,
            display_name=result.identity.display_name,
            role=result.identity.role,
        ),
        expires_at=result.expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End the current session",
)
def logout(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """
    Always succeeds.

    Logging out without a session, with an unknown token or with one that
    has already been revoked all produce `204`. Answering differently
    would make this endpoint a way to test whether a token is still live.

    The cookies are cleared either way, so a client that arrives holding
    something unusable leaves holding nothing.
    """

    now = datetime.utcnow()
    identity = optional_identity(request)

    ended = authentication_service.end_session(
        SqlAlchemySessionRepository(db),
        SecretsTokenGenerator(),
        token=request.cookies.get(SESSION_COOKIE),
        now=now,
    )

    if ended and identity is not None:
        audit_service.record_for_identity(
            SqlAlchemyAuditRepository(db),
            identity=identity,
            action=AuditAction.LOGOUT,
            outcome=AuditOutcome.SUCCEEDED,
            resource=AuditResource("authentication"),
            now=now,
        )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response)

    return response


@router.get(
    "/session",
    response_model=SessionRead,
    responses={
        401: {"description": "There is no live session."},
    },
    summary="The current session, if there is one",
)
def read_session(request: Request) -> SessionRead:
    """
    What the client needs on a page load: who am I, and until when.

    Public, because a client has to be able to ask before it knows. It
    discloses nothing to an anonymous caller - `401` and a sentence.

    Costs no database read of its own: the middleware has already
    validated the session in order to decide whether this request was
    allowed at all.
    """

    identity = optional_identity(request)

    if identity is None:
        raise _refused()

    # The middleware already validated this session in order to let the
    # request through, and carried its expiry forward. Re-reading it here
    # would be a second query per page load for a value already in hand.
    expires_at = session_expires_at(request)

    return SessionRead(
        identity=IdentityRead(
            user_id=identity.user_id,
            email=identity.email,
            display_name=identity.display_name,
            role=identity.role,
        ),
        expires_at=expires_at or DEFAULT_SESSION_POLICY.expires_at(
            datetime.utcnow()
        ),
    )


def _issue_session_cookies(response: Response, token: str) -> None:
    """
    Sets the two cookies a session needs.

    ``httponly`` on the session token is the load-bearing flag: script
    cannot read it, so an injected script cannot exfiltrate a credential
    that outlives the page. The CSRF cookie is readable on purpose,
    because echoing it in a header is what an off-origin attacker cannot
    do.
    """

    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite=_SAME_SITE,
        path=_COOKIE_PATH,
    )

    response.set_cookie(
        CSRF_COOKIE,
        csrf_token_for(token),
        httponly=False,
        samesite=_SAME_SITE,
        path=_COOKIE_PATH,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path=_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path=_COOKIE_PATH)


def _refused() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email address or password is not correct.",
        headers={"WWW-Authenticate": "Cookie"},
    )
