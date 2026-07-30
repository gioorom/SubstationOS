"""
The scrypt password hasher.

These are the properties the ``PasswordHasher`` port promises, asserted
against the adapter that implements it. Every one of them is a property
an attacker exploits when it is absent.

The cost parameters are lowered throughout: this suite is testing the
*properties*, not the wall-clock cost, and running production parameters
here would add minutes to the suite to prove something no assertion
checks.
"""

from __future__ import annotations

import pytest

from app.domain.identity.identity_exceptions import (
    MalformedPasswordHashError,
)
from app.domain.identity.password_credential import PasswordHash
from app.infrastructure.identity.scrypt_password_hasher import (
    ScryptPasswordHasher,
)

PASSWORD = "cavallo batteria graffetta"


@pytest.fixture()
def hasher() -> ScryptPasswordHasher:
    return ScryptPasswordHasher(cost=2**8, block_size=4, parallelism=1)


def test_a_password_verifies_against_its_own_credential(
    hasher: ScryptPasswordHasher,
) -> None:
    assert hasher.verify(PASSWORD, hasher.hash(PASSWORD))


def test_a_different_password_does_not(
    hasher: ScryptPasswordHasher,
) -> None:
    assert not hasher.verify("something else entirely", hasher.hash(PASSWORD))


def test_the_password_is_not_recoverable_from_the_credential(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    The whole point. There is no code path that reverses this, and the
    stored form must not contain the input in any readable form.
    """

    encoded = hasher.hash(PASSWORD).encode()

    assert PASSWORD not in encoded
    assert "cavallo" not in encoded


def test_the_same_password_hashes_to_two_different_credentials(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    A fresh salt per credential. Without it, a stolen table would answer
    "who else used this password?" - and one cracked password would
    unlock every account that shared it.
    """

    first = hasher.hash(PASSWORD)
    second = hasher.hash(PASSWORD)

    assert first.salt != second.salt
    assert first.digest != second.digest
    assert hasher.verify(PASSWORD, first)
    assert hasher.verify(PASSWORD, second)


def test_a_credential_records_the_parameters_it_was_made_under(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    This is what makes raising the cost - or moving to Argon2id - a
    policy change rather than a forced password reset for every user.
    """

    stored = hasher.hash(PASSWORD)

    assert stored.algorithm == "scrypt"
    assert stored.parameter("n") == str(2**8)
    assert stored.parameter("r") == "4"
    assert stored.parameter("p") == "1"


def test_a_credential_still_verifies_after_the_policy_is_raised() -> None:
    """
    An old credential must not become unverifiable when the cost goes up,
    or every user is locked out by a configuration change.
    """

    weak = ScryptPasswordHasher(cost=2**8, block_size=4)
    strong = ScryptPasswordHasher(cost=2**10, block_size=8)

    stored = weak.hash(PASSWORD)

    assert strong.verify(PASSWORD, stored)


def test_a_credential_below_current_policy_is_flagged_for_rehash() -> None:
    weak = ScryptPasswordHasher(cost=2**8, block_size=4)
    strong = ScryptPasswordHasher(cost=2**10, block_size=8)

    assert strong.needs_rehash(weak.hash(PASSWORD))
    assert not strong.needs_rehash(strong.hash(PASSWORD))


def test_a_credential_from_another_algorithm_is_flagged_for_rehash(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    What makes an eventual move to Argon2id a re-hash on next login
    rather than a migration.
    """

    foreign = PasswordHash(
        algorithm="argon2id",
        parameters=(("m", "65536"),),
        salt=b"salt",
        digest=b"digest",
    )

    assert hasher.needs_rehash(foreign)


def test_a_credential_from_another_algorithm_is_refused_not_mismatched(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    Returning ``False`` would be safe but silent, and a credential table
    that has quietly become unverifiable is worth an exception.
    """

    foreign = PasswordHash(
        algorithm="argon2id",
        parameters=(("m", "65536"),),
        salt=b"salt",
        digest=b"digest",
    )

    with pytest.raises(MalformedPasswordHashError):
        hasher.verify(PASSWORD, foreign)


@pytest.mark.parametrize("missing", ["n", "r", "p"])
def test_a_credential_missing_a_cost_parameter_is_refused(
    hasher: ScryptPasswordHasher, missing: str
) -> None:
    """
    Verifying under a guessed default would fail every correct password
    if the guess were weaker, and be a silent downgrade if it were
    stronger.
    """

    stored = hasher.hash(PASSWORD)

    damaged = PasswordHash(
        algorithm=stored.algorithm,
        parameters=tuple(
            item for item in stored.parameters if item[0] != missing
        ),
        salt=stored.salt,
        digest=stored.digest,
    )

    with pytest.raises(MalformedPasswordHashError):
        hasher.verify(PASSWORD, damaged)


def test_verification_uses_a_constant_time_comparison() -> None:
    """
    Structural, because a timing property cannot be asserted reliably on
    a shared CI machine. A byte-by-byte ``==`` returns as soon as it
    finds a difference, and how long that takes measures how much of the
    digest was guessed correctly.
    """

    from pathlib import Path

    source = Path(
        "app/infrastructure/identity/scrypt_password_hasher.py"
    ).read_text(encoding="utf-8")

    assert "hmac.compare_digest" in source
    assert "== stored.digest" not in source


def test_an_empty_password_still_produces_a_credential(
    hasher: ScryptPasswordHasher,
) -> None:
    """
    The hasher does not enforce policy - ``validate_password`` does. Two
    components with the same rule would eventually disagree about it.
    """

    assert hasher.verify("", hasher.hash(""))
