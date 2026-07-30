"""
Password hashing with scrypt.

**Why scrypt, and why from the standard library.**

``hashlib.scrypt`` is OpenSSL's implementation of RFC 7914 - a salted,
memory-hard key-derivation function designed for exactly this job. It is
on OWASP's list of acceptable password hashes, it is not something this
codebase invented, and it needs no dependency.

Argon2id is the better choice and this module says so plainly. It was not
adopted here because it means a compiled dependency (``argon2-cffi``) in
a repository that currently has **no dependency manifest at all** - see
`docs/architecture/security_architecture.md` on that debt. Adding a
binary dependency that nothing records is a worse position than using a
standard-library KDF that is genuinely adequate.

The move is prepared for rather than promised: every credential records
the algorithm and parameters it was produced under, ``needs_rehash``
compares them against current policy, and the authentication service
re-derives a stale credential at the one moment the password is
legitimately available - a successful login. Introducing Argon2id later
is a new adapter and a policy constant, with no migration and no forced
reset.

**Cost parameters.** ``n=2**15, r=8, p=1`` is roughly 32 MiB and tens of
milliseconds per verification on current hardware: enough to make offline
cracking of a stolen table expensive, cheap enough that a login is not a
noticeable pause. They are raised by editing the policy below, and every
credential hashed under the old values keeps verifying.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.domain.identity.identity_exceptions import (
    MalformedPasswordHashError,
)
from app.domain.identity.password_credential import PasswordHash
from app.domain.identity.password_hasher_port import PasswordHasher

ALGORITHM = "scrypt"

#: CPU/memory cost. Must be a power of two.
DEFAULT_COST = 2**15

#: Block size. With `n`, this sets the memory requirement.
DEFAULT_BLOCK_SIZE = 8

#: Parallelisation.
DEFAULT_PARALLELISM = 1

DEFAULT_SALT_BYTES = 16

DEFAULT_DIGEST_BYTES = 32

_MAXMEM = 256 * 1024 * 1024
"""
OpenSSL refuses a derivation that would exceed its memory limit, and the
default is below what these parameters need. Stated here rather than
discovered as a runtime error on the first login.
"""


class ScryptPasswordHasher(PasswordHasher):
    """The default ``PasswordHasher``. Holds no state between calls."""

    def __init__(
        self,
        *,
        cost: int = DEFAULT_COST,
        block_size: int = DEFAULT_BLOCK_SIZE,
        parallelism: int = DEFAULT_PARALLELISM,
        salt_bytes: int = DEFAULT_SALT_BYTES,
        digest_bytes: int = DEFAULT_DIGEST_BYTES,
    ) -> None:
        self._cost = cost
        self._block_size = block_size
        self._parallelism = parallelism
        self._salt_bytes = salt_bytes
        self._digest_bytes = digest_bytes

    def hash(self, password: str) -> PasswordHash:
        salt = secrets.token_bytes(self._salt_bytes)

        return PasswordHash(
            algorithm=ALGORITHM,
            parameters=(
                ("n", str(self._cost)),
                ("r", str(self._block_size)),
                ("p", str(self._parallelism)),
            ),
            salt=salt,
            digest=self._derive(
                password,
                salt=salt,
                cost=self._cost,
                block_size=self._block_size,
                parallelism=self._parallelism,
                length=self._digest_bytes,
            ),
        )

    def verify(self, password: str, stored: PasswordHash) -> bool:
        if stored.algorithm != ALGORITHM:
            raise MalformedPasswordHashError(
                f"Credential was produced by '{stored.algorithm}', which "
                "this hasher cannot verify."
            )

        candidate = self._derive(
            password,
            salt=stored.salt,
            cost=_integer(stored, "n"),
            block_size=_integer(stored, "r"),
            parallelism=_integer(stored, "p"),
            length=len(stored.digest),
        )

        # Constant time with respect to the digest. A byte-by-byte `==`
        # returns as soon as it finds a difference, and the time it takes
        # to do so is a measurement of how much of the digest was
        # guessed correctly.
        return hmac.compare_digest(candidate, stored.digest)

    def needs_rehash(self, stored: PasswordHash) -> bool:
        """
        True when the credential is weaker than current policy.

        Also true for a credential from another algorithm, which is what
        makes an eventual move to Argon2id a re-hash on next login rather
        than a migration.
        """

        if stored.algorithm != ALGORITHM:
            return True

        return (
            _integer(stored, "n") < self._cost
            or _integer(stored, "r") < self._block_size
            or _integer(stored, "p") < self._parallelism
            or len(stored.digest) < self._digest_bytes
        )

    @staticmethod
    def _derive(
        password: str,
        *,
        salt: bytes,
        cost: int,
        block_size: int,
        parallelism: int,
        length: int,
    ) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=cost,
            r=block_size,
            p=parallelism,
            dklen=length,
            maxmem=_MAXMEM,
        )


def _integer(stored: PasswordHash, name: str) -> int:
    """
    Reads one recorded cost parameter.

    A parameter that is missing or not an integer makes the credential
    unreadable, and an unreadable credential is refused rather than
    verified under a guessed default - a default that happened to be
    weaker than the one the digest was produced with would fail every
    correct password, and one that happened to be *stronger* would be a
    silent downgrade nobody could see.
    """

    value = stored.parameter(name)

    if value is None:
        raise MalformedPasswordHashError(
            f"Credential does not record its '{name}' parameter."
        )

    try:
        return int(value)
    except ValueError as error:
        raise MalformedPasswordHashError(
            f"Credential's '{name}' parameter is not an integer."
        ) from error
