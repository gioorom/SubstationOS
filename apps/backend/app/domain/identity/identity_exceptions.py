"""
Typed failures of the identity context.

Every one derives from ``IdentityError`` and carries the identifier that
makes it actionable - except where carrying it would leak. A failure
raised while authenticating never names the address it was raised for,
because the exception's message is one of the things an attacker gets to
read.
"""

from __future__ import annotations


class IdentityError(Exception):
    """Base class for every failure of the identity context."""


class InvalidEmailAddressError(IdentityError):
    def __init__(self, message: str, *, value: str) -> None:
        super().__init__(message)
        self.value = value


class InvalidDisplayNameError(IdentityError):
    def __init__(self, message: str, *, value: str) -> None:
        super().__init__(message)
        self.value = value


class WeakPasswordError(IdentityError):
    """
    A password the policy refuses.

    Carries the unmet requirements, never the password. A message that
    quoted the rejected value would put it in a log the moment anything
    caught this.
    """

    def __init__(self, message: str, *, violations: tuple[str, ...]) -> None:
        super().__init__(message)
        self.violations = violations


class MalformedPasswordHashError(IdentityError):
    """
    A stored credential that cannot be parsed.

    Never recoverable by guessing: a credential that is not in the
    recorded format is refused, not re-interpreted, because a hash this
    system cannot read is a hash it cannot safely compare against.
    """


class UserNotFoundError(IdentityError):
    def __init__(self, message: str, *, user_id: int | None = None) -> None:
        super().__init__(message)
        self.user_id = user_id


class DuplicateEmailAddressError(IdentityError):
    def __init__(self, message: str, *, email: str) -> None:
        super().__init__(message)
        self.email = email


class SessionNotFoundError(IdentityError):
    """No live session matched the presented token."""
