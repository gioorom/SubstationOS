"""
The public identity contract.

**Nothing here can carry a secret.** No schema declares a password, a
credential, a hash, a salt or a session token, and a test in
``tests/api/test_api_security.py`` walks every model in this module
asserting that no field name contains ``password``, ``credential``,
``hash``, ``secret`` or ``token``. The session token leaves the server
exactly once, in a ``Set-Cookie`` header, and never in a body.

``LoginRequest`` is the single exception in the other direction: a
password comes *in*. It is never echoed back, never logged, and never
stored.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.audit.audit_models import AuditAction, AuditOutcome
from app.domain.identity.identity_models import User, UserStatus
from app.domain.identity.identity_roles import Role

# --- Requests ------------------------------------------------------------


class LoginRequest(BaseModel):
    """
    Credentials presented at the login form.

    ``password`` is bounded so an unauthenticated request cannot make the
    server perform an unbounded key derivation - see
    ``password_credential.MAX_PASSWORD_LENGTH``.
    """

    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class CreateUserRequest(BaseModel):
    email: str = Field(max_length=254)
    display_name: str = Field(max_length=120)
    password: str = Field(max_length=1024)
    role: Role = Role.ENGINEER


class SetUserStatusRequest(BaseModel):
    status: UserStatus


# --- Responses -----------------------------------------------------------


class IdentityRead(BaseModel):
    """
    Who the caller is.

    Deliberately small: an id, an address, a name, a role. Everything a
    UI needs to greet somebody and decide which controls to render, and
    nothing that would be worth stealing.
    """

    user_id: int
    email: str
    display_name: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


class SessionRead(BaseModel):
    """
    The current session.

    ``expires_at`` is the **absolute** ceiling and is exposed so a client
    can warn before it arrives. The idle timeout is deliberately not
    exposed: it moves with every request, so a client that displayed it
    would be showing a number that was already wrong.
    """

    identity: IdentityRead
    expires_at: datetime


class UserRead(IdentityRead):
    """One account, as an administrator sees it."""

    status: UserStatus
    created_at: datetime

    @classmethod
    def of(cls, user: User) -> "UserRead":
        return cls(
            user_id=user.user_id,
            email=user.email.value,
            display_name=user.display_name.value,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
        )


class UserListResponse(BaseModel):
    items: tuple[UserRead, ...]


# --- Audit ---------------------------------------------------------------


class AuditActorRead(BaseModel):
    """
    Who acted.

    ``authenticated`` is the field that matters: it says whether
    ``description`` names a verified identity or merely records what an
    anonymous caller claimed.
    """

    authenticated: bool
    user_id: int | None
    session_id: int | None
    description: str


class AuditEventRead(BaseModel):
    event_id: int
    occurred_at: datetime
    action: AuditAction
    outcome: AuditOutcome
    actor: AuditActorRead
    resource_type: str
    resource_id: str | None
    detail: str | None


class AuditEventListResponse(BaseModel):
    items: tuple[AuditEventRead, ...]
