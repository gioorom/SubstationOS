"""
The contract a password hashing algorithm must honour.

The domain declares *that* passwords are hashed, salted, slow to verify
and upgradable. It does not declare *which* function does it - that is an
adapter, precisely so the platform can move to Argon2id without the
identity context, the services or the API learning anything new.

An implementer must guarantee, and the tests in
``tests/domain/test_password_hashing.py`` assert:

- a fresh, cryptographically random salt per credential;
- the same password hashing to two different credentials;
- verification in constant time with respect to the digest;
- a malformed stored credential refused, never treated as a match.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.identity.password_credential import PasswordHash


class PasswordHasher(ABC):
    """Produces and checks stored credentials."""

    @abstractmethod
    def hash(self, password: str) -> PasswordHash:
        """
        Derives a new credential for ``password``.

        Must generate a fresh random salt on every call, so two users who
        choose the same password do not share a digest - which is what
        makes a stolen credential table answer "who else used this
        password?" with nothing.
        """

        raise NotImplementedError

    @abstractmethod
    def verify(self, password: str, stored: PasswordHash) -> bool:
        """
        Whether ``password`` produces ``stored``.

        Must compare digests in constant time: a comparison that returns
        early on the first differing byte leaks, one byte at a time, what
        the correct digest is.

        Raises ``MalformedPasswordHashError`` if ``stored`` was produced
        by an algorithm this implementation does not recognise. Returning
        ``False`` would be safe but silent, and a credential table that
        has quietly become unverifiable is worth an exception.
        """

        raise NotImplementedError

    @abstractmethod
    def needs_rehash(self, stored: PasswordHash) -> bool:
        """
        Whether ``stored`` was produced under weaker parameters than the
        current policy.

        This is the upgrade path. A successful login is the one moment
        the plaintext password is legitimately in memory, so it is the
        one moment a credential can be re-derived under stronger
        parameters without asking the user for anything.
        """

        raise NotImplementedError
