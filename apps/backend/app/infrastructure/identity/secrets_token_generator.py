"""
Session tokens from the operating system's CSPRNG.

``secrets.token_urlsafe`` is the standard library's answer to "give me an
unguessable string", and it draws from ``os.urandom``. There is no
seeding, no reuse and nothing derived from the user or the clock - a
token that could be predicted from anything about the request would be a
session an attacker can mint without a password.

The fingerprint is a plain SHA-256. See ``token_generator_port`` for why
that is correct here and why a slow password hash would not be.
"""

from __future__ import annotations

import hashlib
import secrets

from app.domain.identity.token_generator_port import (
    MINIMUM_TOKEN_ENTROPY_BYTES,
    SecureTokenGenerator,
)


class SecretsTokenGenerator(SecureTokenGenerator):
    """The default ``SecureTokenGenerator``."""

    def __init__(
        self, *, entropy_bytes: int = MINIMUM_TOKEN_ENTROPY_BYTES
    ) -> None:
        if entropy_bytes < MINIMUM_TOKEN_ENTROPY_BYTES:
            raise ValueError(
                "A session token must carry at least "
                f"{MINIMUM_TOKEN_ENTROPY_BYTES} bytes of entropy; "
                f"{entropy_bytes} was requested."
            )

        self._entropy_bytes = entropy_bytes

    def issue(self) -> str:
        return secrets.token_urlsafe(self._entropy_bytes)

    def fingerprint(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
