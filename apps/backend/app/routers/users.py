"""
The user administration API.

```
GET   /users/me                    the caller's own account
POST  /users/me/password           change one's own password
GET   /users/                      every account          (administrator)
POST  /users/                      register an account    (administrator)
POST  /users/{user_id}/status      enable or disable      (administrator)
```

Every route is authenticated - the middleware sees to that - and the four
administrative ones additionally declare the ``MANAGE_USERS`` capability.
The two self-service routes need no capability beyond being somebody:
reading and changing *your own* password is not an administrative act.

There is deliberately **no self-registration**. A private engineering
platform does not admit whoever finds the address, so accounts are
created by an administrator and the first one comes from the bootstrap
script (`scripts/create_administrator.py`).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_exceptions import (
    DuplicateEmailAddressError,
    InvalidDisplayNameError,
    InvalidEmailAddressError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.identity.identity_models import UserStatus
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.infrastructure.identity.scrypt_password_hasher import (
    ScryptPasswordHasher,
)
from app.infrastructure.identity.sqlalchemy_session_repository import (
    SqlAlchemySessionRepository,
)
from app.infrastructure.identity.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.routers.security import current_identity, require_administrator
from app.schemas.identity import (
    ChangePasswordRequest,
    CreateUserRequest,
    IdentityRead,
    SetUserStatusRequest,
    UserListResponse,
    UserRead,
)
from app.services import audit_service, user_service

router = APIRouter(prefix="/users", tags=["Users"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/me",
    response_model=IdentityRead,
    summary="The caller's own identity",
)
def read_me(
    identity: AuditIdentity = Depends(current_identity),
) -> IdentityRead:
    return IdentityRead(
        user_id=identity.user_id,
        email=identity.email,
        display_name=identity.display_name,
        role=identity.role,
    )


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "The current password is not correct."},
        422: {"description": "The new password fails the policy."},
    },
    summary="Change one's own password",
)
def change_own_password(
    payload: ChangePasswordRequest,
    identity: AuditIdentity = Depends(current_identity),
    db: Session = Depends(get_db),
) -> None:
    """
    Requires the current password, and **ends every session including
    this one**.

    Both are deliberate. Without the current password, an unlocked
    browser would be a permanent account takeover rather than a temporary
    one; without the revocation, a password changed because it may be
    known to someone else would leave that someone else logged in.
    """

    now = datetime.utcnow()

    try:
        changed = user_service.change_password(
            SqlAlchemyUserRepository(db),
            SqlAlchemySessionRepository(db),
            ScryptPasswordHasher(),
            user_id=identity.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            now=now,
        )
    except WeakPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            # The unmet requirements, never the rejected password.
            detail=" ".join(error.violations),
        ) from error
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    audit = SqlAlchemyAuditRepository(db)
    resource = AuditResource("user", str(identity.user_id))

    if not changed:
        audit_service.record_for_identity(
            audit,
            identity=identity,
            action=AuditAction.PASSWORD_CHANGED,
            outcome=AuditOutcome.DENIED,
            resource=resource,
            now=now,
            detail="current password did not match",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The current password is not correct.",
        )

    audit_service.record_for_identity(
        audit,
        identity=identity,
        action=AuditAction.PASSWORD_CHANGED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=resource,
        now=now,
        detail="all sessions revoked",
    )


@router.get(
    "/",
    response_model=UserListResponse,
    dependencies=[Depends(require_administrator)],
    summary="Every account",
)
def list_users(db: Session = Depends(get_db)) -> UserListResponse:
    return UserListResponse(
        items=tuple(
            UserRead.of(user)
            for user in SqlAlchemyUserRepository(db).list_all()
        )
    )


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "The caller is not an administrator."},
        409: {"description": "That address already has an account."},
        422: {"description": "The address, name or password is invalid."},
    },
    summary="Register an account",
)
def create_user(
    payload: CreateUserRequest,
    identity: AuditIdentity = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> UserRead:
    now = datetime.utcnow()

    try:
        user = user_service.create_user(
            SqlAlchemyUserRepository(db),
            ScryptPasswordHasher(),
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
            now=now,
        )
    except DuplicateEmailAddressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except WeakPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=" ".join(error.violations),
        ) from error
    except (InvalidEmailAddressError, InvalidDisplayNameError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    audit_service.record_for_identity(
        SqlAlchemyAuditRepository(db),
        identity=identity,
        action=AuditAction.USER_CREATED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource("user", str(user.user_id)),
        now=now,
        detail=f"role={user.role.value}",
    )

    return UserRead.of(user)


@router.post(
    "/{user_id}/status",
    response_model=UserRead,
    responses={
        403: {"description": "The caller is not an administrator."},
        404: {"description": "No such user."},
        409: {"description": "An administrator may not disable themselves."},
    },
    summary="Enable or disable an account",
)
def set_user_status(
    user_id: int,
    payload: SetUserStatusRequest,
    identity: AuditIdentity = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> UserRead:
    """
    Disabling revokes every live session of that user immediately.

    An administrator may not disable their own account: an installation
    whose last administrator locks themselves out has no supported way
    back in, and `409` is a cheaper answer than that.
    """

    if user_id == identity.user_id and payload.status is UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An administrator may not disable their own account.",
        )

    now = datetime.utcnow()

    try:
        user = user_service.set_status(
            SqlAlchemyUserRepository(db),
            SqlAlchemySessionRepository(db),
            user_id=user_id,
            status=payload.status,
            now=now,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    audit_service.record_for_identity(
        SqlAlchemyAuditRepository(db),
        identity=identity,
        action=AuditAction.USER_DISABLED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource("user", str(user_id)),
        now=now,
        detail=f"status={payload.status.value}",
    )

    return UserRead.of(user)
