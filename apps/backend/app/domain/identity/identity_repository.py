"""
The ports the identity context loads and saves through.

The domain declares what it needs to ask - "is there a user with this
address?", "is this token fingerprint a live session?" - and nothing
about where the answer comes from. Both implementations live in
``app/infrastructure/identity``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.identity.identity_models import EmailAddress, User
from app.domain.identity.session_models import AuthenticationSession


class UserRepository(ABC):
    """Loads and stores users."""

    @abstractmethod
    def find_by_email(self, email: EmailAddress) -> User | None:
        """
        The user registered at this address, or ``None``.

        ``None`` is returned for an address nobody has registered. The
        *caller* is responsible for not turning that into an observably
        different response than a wrong password - see
        ``authentication_service`` on user enumeration.
        """

        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def add(self, user: User) -> User:
        """
        Registers a new user and returns it with its assigned id.

        Raises ``DuplicateEmailAddressError`` when the address is
        already registered. The uniqueness constraint is the database's,
        not a read-then-write in application code, because two
        registrations racing must not both succeed.
        """

        raise NotImplementedError

    @abstractmethod
    def save(self, user: User) -> User:
        """Persists a change to an existing user."""

        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> tuple[User, ...]:
        """Every user, ordered by id. Administration only."""

        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        """
        How many users exist.

        Used by the bootstrap check that refuses to create a second
        first-administrator.
        """

        raise NotImplementedError


class SessionRepository(ABC):
    """Loads and stores authentication sessions."""

    @abstractmethod
    def add(
        self, session: AuthenticationSession
    ) -> AuthenticationSession:
        raise NotImplementedError

    @abstractmethod
    def find_by_fingerprint(
        self, token_fingerprint: str
    ) -> AuthenticationSession | None:
        """
        The session whose token has this fingerprint, or ``None``.

        The lookup is by fingerprint and never by user, because the only
        thing a request presents is a token.
        """

        raise NotImplementedError

    @abstractmethod
    def save(
        self, session: AuthenticationSession
    ) -> AuthenticationSession:
        raise NotImplementedError

    @abstractmethod
    def revoke_all_for_user(
        self, user_id: int, *, now: datetime
    ) -> int:
        """
        Ends every live session of one user and returns how many.

        This is what a password change must call. A password that has
        been changed because it may have been compromised is worth
        nothing if the sessions it opened stay alive.
        """

        raise NotImplementedError

    @abstractmethod
    def list_active_for_user(
        self, user_id: int
    ) -> tuple[AuthenticationSession, ...]:
        """
        Every unrevoked session of one user, newest first.

        "Unrevoked" is a stored fact; whether each is *usable* is a
        question for ``SessionPolicy``, which the repository does not
        know and must not duplicate.
        """

        raise NotImplementedError
