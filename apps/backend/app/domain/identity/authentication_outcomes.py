"""
The typed outcomes of authenticating.

The codes below exist for the **audit trail and the operator**, never for
the caller. A failed login is answered with one message and one status
code no matter which of these caused it, because the difference between
"no such address" and "wrong password" is precisely the difference an
attacker uses to turn a login form into a list of who has an account.

So: a rich internal vocabulary, a deliberately poor external one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.identity.audit_identity import AuditIdentity


class AuthenticationFailureCode(str, Enum):
    """Why an authentication attempt did not produce a session."""

    #: No user is registered at the address presented.
    UNKNOWN_IDENTITY = "unknown_identity"

    #: The address is registered; the password did not match.
    INVALID_CREDENTIAL = "invalid_credential"

    #: The user exists and may not authenticate.
    DISABLED_ACCOUNT = "disabled_account"

    #: The stored credential could not be parsed - an operator problem.
    UNREADABLE_CREDENTIAL = "unreadable_credential"


class SessionRejectionCode(str, Enum):
    """Why a presented session token did not authenticate a request."""

    #: No token was presented at all.
    MISSING_TOKEN = "missing_token"

    #: A token was presented and matches no session.
    UNKNOWN_SESSION = "unknown_session"

    #: The session was ended, by logout or by an administrator.
    REVOKED_SESSION = "revoked_session"

    #: The session passed its absolute lifetime.
    EXPIRED_SESSION = "expired_session"

    #: The session was unused for longer than the idle timeout.
    IDLE_SESSION = "idle_session"

    #: The session is live and its user has since been disabled.
    DISABLED_ACCOUNT = "disabled_account"

    #: The session is live and its user no longer exists.
    UNKNOWN_IDENTITY = "unknown_identity"


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """
    What a login attempt produced.

    ``token`` is the only place in the system a session token is ever
    returned. It is set on success and is ``None`` otherwise, and no read
    endpoint can produce it again - a token that has been issued and lost
    is gone, which is the correct behaviour for a bearer secret.
    """

    succeeded: bool
    identity: AuditIdentity | None
    token: str | None
    expires_at: datetime | None
    failure: AuthenticationFailureCode | None

    @classmethod
    def granted(
        cls,
        identity: AuditIdentity,
        token: str,
        expires_at: datetime,
    ) -> "AuthenticationResult":
        return cls(
            succeeded=True,
            identity=identity,
            token=token,
            expires_at=expires_at,
            failure=None,
        )

    @classmethod
    def refused(
        cls, failure: AuthenticationFailureCode
    ) -> "AuthenticationResult":
        return cls(
            succeeded=False,
            identity=None,
            token=None,
            expires_at=None,
            failure=failure,
        )


@dataclass(frozen=True, slots=True)
class SessionValidation:
    """
    What presenting a session token produced.

    Either an identity or a reason, never both, and never a partially
    authenticated state: there is no "authenticated but expired" value
    here that a careless caller could treat as good enough.
    """

    identity: AuditIdentity | None
    rejection: SessionRejectionCode | None
    expires_at: datetime | None = None
    """
    The validated session's absolute ceiling.

    Carried here so a client can be told when it will be signed out
    without the API spending a second query to re-read a session the
    middleware has already loaded.
    """

    @property
    def is_authenticated(self) -> bool:
        return self.identity is not None

    @classmethod
    def authenticated(
        cls, identity: AuditIdentity, expires_at: datetime
    ) -> "SessionValidation":
        return cls(
            identity=identity, rejection=None, expires_at=expires_at
        )

    @classmethod
    def rejected(cls, code: SessionRejectionCode) -> "SessionValidation":
        return cls(identity=None, rejection=code, expires_at=None)
