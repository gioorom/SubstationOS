"""
An authenticated session: the fact that a user proved who they were, and
for how long that proof remains good.

**The token is not here.** A session records a *fingerprint* of the token
- a digest that can confirm a presented token and cannot produce one. A
database that stores session tokens is a database whose theft is
equivalent to stealing every live login; a database that stores
fingerprints is not.

The token itself exists exactly twice: in the response that created the
session, and in the request that presents it. It is never logged, never
returned by a read endpoint, and has no column.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """
    Why a session is or is not usable.

    The three ways a session ends are kept apart because they mean
    different things to the person holding it: an idle session is one
    they walked away from, an expired one is one they have had for long
    enough regardless of use, and a revoked one is a logout - theirs or
    an administrator's.

    All three are answered to the client as the same `401`. The
    distinction is for the audit trail and for the engineer reading it,
    not for the caller, who learns only that they must authenticate.
    """

    ACTIVE = "active"
    IDLE_EXPIRED = "idle_expired"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class AuthenticationSession:
    """
    One login.

    ``last_seen_at`` moves as the session is used, which is what makes
    the idle timeout an idle timeout. ``issued_at`` never moves, which is
    what makes the absolute lifetime absolute - a session cannot be kept
    alive indefinitely by using it, and that ceiling is the reason a
    stolen session token has a bounded value.
    """

    session_id: int | None
    user_id: int
    token_fingerprint: str
    issued_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def touched_at(self, now: datetime) -> "AuthenticationSession":
        """The same session, seen now. Value objects are replaced."""

        return AuthenticationSession(
            session_id=self.session_id,
            user_id=self.user_id,
            token_fingerprint=self.token_fingerprint,
            issued_at=self.issued_at,
            last_seen_at=now,
            expires_at=self.expires_at,
            revoked_at=self.revoked_at,
        )

    def revoked(self, now: datetime) -> "AuthenticationSession":
        """
        Ends the session.

        Idempotent: revoking an already revoked session keeps the first
        revocation time, because when it *ended* is the auditable fact
        and a second logout does not change it.
        """

        return AuthenticationSession(
            session_id=self.session_id,
            user_id=self.user_id,
            token_fingerprint=self.token_fingerprint,
            issued_at=self.issued_at,
            last_seen_at=self.last_seen_at,
            expires_at=self.expires_at,
            revoked_at=self.revoked_at if self.is_revoked else now,
        )
