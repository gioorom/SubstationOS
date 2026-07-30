"""
SQLAlchemy adapter for the ``SessionRepository`` port.

Every lookup is by token fingerprint, because a fingerprint is the only
thing a request can produce. There is deliberately **no** method that
finds a session by user and returns something usable to authenticate
with: a session is proved by presenting its token, and an interface that
could hand one out on the strength of a user id would be a way to
impersonate anybody.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.identity.identity_repository import SessionRepository
from app.domain.identity.session_models import AuthenticationSession
from app.models.identity import AuthenticationSessionRecord


class SqlAlchemySessionRepository(SessionRepository):
    """The default ``SessionRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, session: AuthenticationSession
    ) -> AuthenticationSession:
        record = AuthenticationSessionRecord(
            user_id=session.user_id,
            token_fingerprint=session.token_fingerprint,
            issued_at=session.issued_at,
            last_seen_at=session.last_seen_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
        )

        self._session.add(record)
        self._session.commit()

        return _to_domain(record)

    def find_by_fingerprint(
        self, token_fingerprint: str
    ) -> AuthenticationSession | None:
        record = self._session.scalar(
            select(AuthenticationSessionRecord).where(
                AuthenticationSessionRecord.token_fingerprint
                == token_fingerprint
            )
        )

        return None if record is None else _to_domain(record)

    def save(
        self, session: AuthenticationSession
    ) -> AuthenticationSession:
        record = self._session.get(
            AuthenticationSessionRecord, session.session_id
        )

        if record is None:
            # A session that has vanished under us is not re-created:
            # writing it back would resurrect something an administrator
            # may have deliberately removed.
            return session

        record.last_seen_at = session.last_seen_at
        record.expires_at = session.expires_at
        record.revoked_at = session.revoked_at

        self._session.commit()

        return _to_domain(record)

    def revoke_all_for_user(self, user_id: int, *, now: datetime) -> int:
        """
        One statement, so a user cannot open a new session in the gap
        between reading the live ones and revoking them.
        """

        result = self._session.execute(
            update(AuthenticationSessionRecord)
            .where(
                AuthenticationSessionRecord.user_id == user_id,
                AuthenticationSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        self._session.commit()

        return int(result.rowcount or 0)

    def list_active_for_user(
        self, user_id: int
    ) -> tuple[AuthenticationSession, ...]:
        records = self._session.scalars(
            select(AuthenticationSessionRecord)
            .where(
                AuthenticationSessionRecord.user_id == user_id,
                AuthenticationSessionRecord.revoked_at.is_(None),
            )
            .order_by(AuthenticationSessionRecord.issued_at.desc())
        ).all()

        return tuple(_to_domain(record) for record in records)


def _to_domain(
    record: AuthenticationSessionRecord,
) -> AuthenticationSession:
    return AuthenticationSession(
        session_id=record.id,
        user_id=record.user_id,
        token_fingerprint=record.token_fingerprint,
        issued_at=record.issued_at,
        last_seen_at=record.last_seen_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
    )
