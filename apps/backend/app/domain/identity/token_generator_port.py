"""
Where a session token comes from, and how it becomes a fingerprint.

Randomness is ambient state: it is exactly the thing the rest of this
codebase pushes to an adapter so the domain stays deterministic and
testable. A session token is also the one secret in this context that a
mistake in makes everything else pointless, so its generation is a
declared contract rather than a call to whatever `random` module is in
scope.

**The fingerprint is a plain SHA-256 of the token, and that is correct.**
It is deliberately *not* a slow password hash, and the difference matters:
a password is low-entropy and chosen by a human, so it must be expensive
to guess; a session token is 256 bits from a CSPRNG, so there is nothing
to guess and the only requirement is that the stored form cannot produce
the token. Making session lookup deliberately slow would add cost to
every authenticated request and buy nothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

MINIMUM_TOKEN_ENTROPY_BYTES = 32
"""256 bits. Not a number to lower without a reason nobody has yet."""


class SecureTokenGenerator(ABC):
    """Issues session tokens and reduces them to fingerprints."""

    @abstractmethod
    def issue(self) -> str:
        """
        A fresh, unguessable, URL-safe token.

        Must come from a cryptographically secure source with at least
        ``MINIMUM_TOKEN_ENTROPY_BYTES`` of entropy. Must never be derived
        from the user, the time, or a counter - anything predictable here
        is a session an attacker can mint.
        """

        raise NotImplementedError

    @abstractmethod
    def fingerprint(self, token: str) -> str:
        """
        The stored form of a token.

        Must be deterministic (the same token always fingerprints to the
        same value, or no session could ever be found again) and
        one-way (the fingerprint must not yield the token, or a stolen
        database would be a stolen set of live logins).
        """

        raise NotImplementedError
