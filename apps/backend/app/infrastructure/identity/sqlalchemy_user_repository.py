"""
SQLAlchemy adapter for the ``UserRepository`` port.

Writes ``users`` and nothing else. It knows how a user is stored; it does
not know what a password is, how one is hashed, or when a session may be
opened.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.identity.identity_exceptions import (
    DuplicateEmailAddressError,
    UserNotFoundError,
)
from app.domain.identity.identity_models import (
    DisplayName,
    EmailAddress,
    User,
    UserStatus,
)
from app.domain.identity.identity_repository import UserRepository
from app.domain.identity.identity_roles import Role
from app.models.identity import UserRecord


class SqlAlchemyUserRepository(UserRepository):
    """The default ``UserRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_email(self, email: EmailAddress) -> User | None:
        record = self._session.scalar(
            select(UserRecord).where(UserRecord.email == email.value)
        )

        return None if record is None else _to_domain(record)

    def find_by_id(self, user_id: int) -> User | None:
        record = self._session.get(UserRecord, user_id)

        return None if record is None else _to_domain(record)

    def add(self, user: User) -> User:
        record = UserRecord(
            email=user.email.value,
            display_name=user.display_name.value,
            role=user.role.value,
            status=user.status.value,
            encoded_credential=user.encoded_credential,
            created_at=user.created_at,
            credential_updated_at=user.credential_updated_at,
        )

        self._session.add(record)

        try:
            self._session.flush()
        except IntegrityError as error:
            # The unique index refused it. Reported as the domain's own
            # failure so the router never has to recognise a driver's.
            self._session.rollback()

            raise DuplicateEmailAddressError(
                "An account already exists for this email address.",
                email=user.email.value,
            ) from error

        self._session.commit()

        return _to_domain(record)

    def save(self, user: User) -> User:
        if user.user_id is None:
            raise UserNotFoundError(
                "An unsaved user cannot be updated; add it first."
            )

        record = self._session.get(UserRecord, user.user_id)

        if record is None:
            raise UserNotFoundError(
                "This user no longer exists.", user_id=user.user_id
            )

        record.display_name = user.display_name.value
        record.role = user.role.value
        record.status = user.status.value
        record.encoded_credential = user.encoded_credential
        record.credential_updated_at = user.credential_updated_at

        self._session.commit()

        return _to_domain(record)

    def list_all(self) -> tuple[User, ...]:
        records = self._session.scalars(
            select(UserRecord).order_by(UserRecord.id)
        ).all()

        return tuple(_to_domain(record) for record in records)

    def count(self) -> int:
        return int(
            self._session.scalar(select(func.count()).select_from(UserRecord))
            or 0
        )


def _to_domain(record: UserRecord) -> User:
    return User(
        user_id=record.id,
        email=EmailAddress(record.email),
        display_name=DisplayName(record.display_name),
        role=Role(record.role),
        status=UserStatus(record.status),
        encoded_credential=record.encoded_credential,
        created_at=record.created_at,
        credential_updated_at=record.credential_updated_at,
    )
