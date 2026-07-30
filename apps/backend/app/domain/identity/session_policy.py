"""
How long a session lives.

Two independent clocks, and a session must satisfy both:

- **Idle timeout** - time since the session was last used. Bounds the
  window in which an unattended, logged-in workstation is useful to
  somebody who sits down at it.
- **Absolute lifetime** - time since the session was issued, regardless
  of use. Bounds the value of a stolen token, and guarantees that
  authentication is re-proved on a schedule even for a user who never
  stops working.

The defaults below are chosen for a private engineering platform whose
users work in long sittings on documents that take a while to read: long
enough that a session does not expire mid-review, short enough that an
unlocked machine in a shared office is not an open account overnight.

Both are **policy, not law**: a deployment may narrow them, and the
values are stated here in one place rather than spread across the code
that enforces them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.identity.session_models import (
    AuthenticationSession,
    SessionStatus,
)

DEFAULT_IDLE_TIMEOUT = timedelta(hours=2)

DEFAULT_ABSOLUTE_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    """The two timeouts, and the rule that reads them."""

    idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT
    absolute_lifetime: timedelta = DEFAULT_ABSOLUTE_LIFETIME

    def expires_at(self, issued_at: datetime) -> datetime:
        """The absolute ceiling, fixed when the session is created."""

        return issued_at + self.absolute_lifetime

    def status_at(
        self, session: AuthenticationSession, now: datetime
    ) -> SessionStatus:
        """
        What this session is, at this instant.

        Order matters and is deliberate: revocation wins over every
        clock, because an explicitly ended session must never be
        reportable as merely idle. Between the two clocks the absolute
        ceiling is checked first, since it is the one a user cannot
        extend.

        A pure function of a session and a timestamp - no request, no
        database, no wall clock of its own. That is what lets every
        expiry rule be tested without waiting for one.
        """

        if session.is_revoked:
            return SessionStatus.REVOKED

        if now >= session.expires_at:
            return SessionStatus.EXPIRED

        if now - session.last_seen_at >= self.idle_timeout:
            return SessionStatus.IDLE_EXPIRED

        return SessionStatus.ACTIVE

    def is_usable(
        self, session: AuthenticationSession, now: datetime
    ) -> bool:
        return self.status_at(session, now) is SessionStatus.ACTIVE


DEFAULT_SESSION_POLICY = SessionPolicy()
