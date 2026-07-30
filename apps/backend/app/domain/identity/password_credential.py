"""
How a password is stored, and what a password must be.

Two rules govern this module, and both are absolute:

1. **A password is never stored, and never stored reversibly.** What is
   stored is the output of a deliberately slow, salted key-derivation
   function. There is no code path in this system that turns a stored
   credential back into a password, because none can exist.
2. **The stored form describes itself.** A credential records the
   algorithm and the parameters it was produced under, so raising the
   cost - or moving to Argon2id - is a policy change plus a re-hash on
   next login, not a schema migration and not a forced password reset
   for every user.

The composition rules are deliberately *absent*. NIST SP 800-63B
recommends length over character-class requirements, because
``P@ssw0rd!`` satisfies every classic rule and is worthless, while a long
passphrase fails several and is not. Length is checked; shape is not.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from app.domain.identity.identity_exceptions import (
    MalformedPasswordHashError,
    WeakPasswordError,
)

MIN_PASSWORD_LENGTH = 12

MAX_PASSWORD_LENGTH = 1024
"""
Not a strength rule - a cost bound.

The hash function is slow by design. Without a ceiling, a megabyte of
"password" is an unauthenticated request that makes the server do
unbounded work, which is a denial-of-service vector wearing a login
form's clothes.
"""

FIELD_SEPARATOR = "$"

PARAMETER_SEPARATOR = ","


def validate_password(password: str) -> None:
    """
    Raises ``WeakPasswordError`` if the password may not be used.

    The violations are returned together rather than one at a time: a
    user changing a password should learn everything wrong with their
    choice in one attempt.
    """

    violations: list[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        violations.append(
            f"A password must be at least {MIN_PASSWORD_LENGTH} "
            "characters long."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        violations.append(
            f"A password may not exceed {MAX_PASSWORD_LENGTH} characters."
        )

    if password.strip() == "":
        violations.append("A password may not be entirely whitespace.")

    if violations:
        raise WeakPasswordError(
            "The password does not satisfy the password policy.",
            violations=tuple(violations),
        )


@dataclass(frozen=True, slots=True)
class PasswordHash:
    """
    A stored credential, self-describing.

    Encoded as ``algorithm$parameters$salt$digest``, with salt and digest
    in URL-safe base64. The shape follows the long-established modular
    crypt convention for one reason: a credential that carries its own
    parameters can be verified years after the parameters changed.

    This value object performs no hashing. It is the *format*; producing
    and checking a digest is the ``PasswordHasher`` port's job, and the
    algorithm lives in an adapter so it can be replaced without the
    domain learning a new one.
    """

    algorithm: str
    parameters: tuple[tuple[str, str], ...]
    salt: bytes
    digest: bytes

    def encode(self) -> str:
        """The single string a repository stores."""

        return FIELD_SEPARATOR.join(
            (
                self.algorithm,
                PARAMETER_SEPARATOR.join(
                    f"{name}={value}" for name, value in self.parameters
                ),
                _b64(self.salt),
                _b64(self.digest),
            )
        )

    def parameter(self, name: str) -> str | None:
        for declared, value in self.parameters:
            if declared == name:
                return value

        return None

    @classmethod
    def decode(cls, encoded: str) -> "PasswordHash":
        """
        Parses a stored credential.

        Raises ``MalformedPasswordHashError`` rather than guessing.
        A credential this system cannot read is a credential it must not
        compare against - silently treating an unreadable hash as a
        mismatch would be tolerable, and treating it as a match would be
        catastrophic, so it refuses to do either.
        """

        fields = encoded.split(FIELD_SEPARATOR)

        if len(fields) != 4:
            raise MalformedPasswordHashError(
                "A stored credential must have four fields."
            )

        algorithm, parameters, salt, digest = fields

        if not algorithm:
            raise MalformedPasswordHashError(
                "A stored credential must name its algorithm."
            )

        try:
            decoded_parameters = tuple(
                _split_parameter(entry)
                for entry in parameters.split(PARAMETER_SEPARATOR)
                if entry
            )
        except ValueError as error:
            raise MalformedPasswordHashError(
                "A stored credential's parameters must be name=value."
            ) from error

        return cls(
            algorithm=algorithm,
            parameters=decoded_parameters,
            salt=_unb64(salt),
            digest=_unb64(digest),
        )


def _split_parameter(entry: str) -> tuple[str, str]:
    name, separator, value = entry.partition("=")

    if not separator or not name:
        raise ValueError(entry)

    return (name, value)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)

    try:
        return base64.urlsafe_b64decode(encoded + padding)
    except (ValueError, TypeError) as error:
        raise MalformedPasswordHashError(
            "A stored credential's salt and digest must be base64."
        ) from error
