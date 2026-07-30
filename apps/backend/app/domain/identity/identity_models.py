"""
Who a user is.

This is the whole of what the identity context knows about a person: a
stable id, an address to authenticate with, a name to show, one role and
a status. It deliberately knows nothing about projects, documents or
engineering artefacts - the dependency runs the other way, and it runs
only through the application layer.

**No engineering artefact references a user.** An entity, a fact or a
semantic statement is a function of the document's bytes and the rules
that read them; making one depend on who ran the pipeline would destroy
the determinism the whole platform rests on. Identity attaches to
*actions*, never to artefacts - see ``audit_identity.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.identity.identity_exceptions import (
    InvalidDisplayNameError,
    InvalidEmailAddressError,
)
from app.domain.identity.identity_roles import Role

MAX_EMAIL_LENGTH = 254
"""RFC 5321's limit on a forward path. Longer is not an address."""

MIN_DISPLAY_NAME_LENGTH = 2
MAX_DISPLAY_NAME_LENGTH = 120


class UserStatus(str, Enum):
    """
    Whether this user may authenticate at all.

    ``DISABLED`` is deliberately not deletion: an engineering platform
    must be able to say who performed an action years after that person
    left, and a deleted user makes every audit event they produced
    unreadable. Disabling ends access and preserves the record.
    """

    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """
    The address a user authenticates with.

    Validation is deliberately shallow: exactly one ``@``, something on
    each side, no whitespace, within RFC 5321's length. A regex claiming
    to implement RFC 5322 would reject real addresses, and the only
    proof that an address works is sending mail to it - which this
    milestone does not do.

    Normalised to lower case because an address that differs only in
    case is the same login attempt, and two accounts differing only in
    case would be an account-takeover mechanism, not a feature.
    """

    value: str

    def __post_init__(self) -> None:
        candidate = self.value.strip().lower()

        if not candidate:
            raise InvalidEmailAddressError(
                "An email address is required.", value=self.value
            )

        if len(candidate) > MAX_EMAIL_LENGTH:
            raise InvalidEmailAddressError(
                f"An email address may not exceed {MAX_EMAIL_LENGTH} "
                "characters.",
                value=self.value,
            )

        if any(character.isspace() for character in candidate):
            raise InvalidEmailAddressError(
                "An email address may not contain whitespace.",
                value=self.value,
            )

        local, separator, domain = candidate.partition("@")

        if not separator or not local or not domain or "@" in domain:
            raise InvalidEmailAddressError(
                "An email address must contain exactly one '@', with a "
                "local part and a domain.",
                value=self.value,
            )

        object.__setattr__(self, "value", candidate)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DisplayName:
    """The name shown next to an action. Never used to authenticate."""

    value: str

    def __post_init__(self) -> None:
        candidate = " ".join(self.value.split())

        if len(candidate) < MIN_DISPLAY_NAME_LENGTH:
            raise InvalidDisplayNameError(
                f"A display name must be at least "
                f"{MIN_DISPLAY_NAME_LENGTH} characters.",
                value=self.value,
            )

        if len(candidate) > MAX_DISPLAY_NAME_LENGTH:
            raise InvalidDisplayNameError(
                f"A display name may not exceed "
                f"{MAX_DISPLAY_NAME_LENGTH} characters.",
                value=self.value,
            )

        object.__setattr__(self, "value", candidate)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class User:
    """
    One person who may authenticate.

    ``credential`` is the *encoded* password hash, never a password and
    never anything a password could be recovered from. It is typed as a
    plain string here because the identity context stores what the
    hasher produced; only ``PasswordHash`` interprets it.

    ``user_id`` is ``None`` before the repository has assigned one, the
    same convention the rest of this codebase uses for unsaved entities.
    """

    user_id: int | None
    email: EmailAddress
    display_name: DisplayName
    role: Role
    status: UserStatus
    encoded_credential: str
    created_at: datetime
    credential_updated_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    @property
    def is_administrator(self) -> bool:
        return self.role is Role.ADMINISTRATOR

    def with_credential(
        self, encoded_credential: str, *, now: datetime
    ) -> "User":
        """A password change. The value object is replaced, not mutated."""

        return User(
            user_id=self.user_id,
            email=self.email,
            display_name=self.display_name,
            role=self.role,
            status=self.status,
            encoded_credential=encoded_credential,
            created_at=self.created_at,
            credential_updated_at=now,
        )
