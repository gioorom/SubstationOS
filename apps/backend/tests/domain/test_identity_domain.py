"""
The identity domain, tested as pure values.

No database, no request, no clock of its own. Every rule below - what an
address is, what a role may do, when a session dies - is a function of
its arguments, which is what lets an expiry rule be tested without
waiting for one.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_exceptions import (
    InvalidDisplayNameError,
    InvalidEmailAddressError,
    MalformedPasswordHashError,
    WeakPasswordError,
)
from app.domain.identity.identity_models import (
    DisplayName,
    EmailAddress,
    User,
    UserStatus,
)
from app.domain.identity.identity_roles import (
    Capability,
    Role,
    capabilities_of,
    role_permits,
)
from app.domain.identity.password_credential import (
    MIN_PASSWORD_LENGTH,
    PasswordHash,
    validate_password,
)
from app.domain.identity.project_access import may_administer_project
from app.domain.identity.session_models import (
    AuthenticationSession,
    SessionStatus,
)
from app.domain.identity.session_policy import SessionPolicy

NOW = datetime(2026, 7, 30, 9, 0, 0)


# --- Addresses and names -------------------------------------------------


def test_an_address_is_normalised_to_lower_case() -> None:
    """
    Two accounts differing only in case would be an account-takeover
    mechanism, not a feature.
    """

    assert EmailAddress("Ada@Example.COM").value == "ada@example.com"


def test_an_address_is_stripped_of_surrounding_whitespace() -> None:
    assert EmailAddress("  ada@example.com  ").value == "ada@example.com"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "ada",
        "@example.com",
        "ada@",
        "ada@@example.com",
        "ada lovelace@example.com",
        "a" * 250 + "@example.com",
    ],
)
def test_an_address_that_cannot_be_one_is_refused(value: str) -> None:
    with pytest.raises(InvalidEmailAddressError):
        EmailAddress(value)


def test_a_display_name_collapses_internal_whitespace() -> None:
    assert DisplayName("  Ada   Lovelace ").value == "Ada Lovelace"


@pytest.mark.parametrize("value", ["", " ", "A", "x" * 121])
def test_a_display_name_outside_its_bounds_is_refused(value: str) -> None:
    with pytest.raises(InvalidDisplayNameError):
        DisplayName(value)


# --- Roles and capabilities ----------------------------------------------


def test_there_are_exactly_two_roles() -> None:
    """
    The EPIC that introduced this warned against inventing dozens of
    roles ahead of a requirement. This test is what makes adding one a
    deliberate act rather than a quiet one.
    """

    assert {role.value for role in Role} == {"engineer", "administrator"}


def test_an_engineer_may_use_the_platform_but_not_administer_it() -> None:
    assert role_permits(Role.ENGINEER, Capability.USE_ENGINEERING_PLATFORM)
    assert role_permits(Role.ENGINEER, Capability.MANAGE_PROJECTS)
    assert not role_permits(Role.ENGINEER, Capability.MANAGE_USERS)
    assert not role_permits(Role.ENGINEER, Capability.READ_AUDIT_TRAIL)


def test_an_administrator_carries_every_capability() -> None:
    assert capabilities_of(Role.ADMINISTRATOR) == frozenset(Capability)


def test_anonymous_is_not_a_role() -> None:
    """
    Anonymous is the *absence* of an identity. A member here would be a
    value that could be written to a user row.
    """

    assert "anonymous" not in {role.value for role in Role}


# --- Passwords -----------------------------------------------------------


def test_a_password_shorter_than_the_minimum_is_refused() -> None:
    with pytest.raises(WeakPasswordError) as caught:
        validate_password("x" * (MIN_PASSWORD_LENGTH - 1))

    assert caught.value.violations


def test_a_refusal_never_carries_the_rejected_password() -> None:
    """
    The message and the violations are read by whatever catches this, and
    both would end up in a log.
    """

    with pytest.raises(WeakPasswordError) as caught:
        validate_password("segreto")

    assert "segreto" not in str(caught.value)
    assert not any("segreto" in item for item in caught.value.violations)


def test_a_very_long_password_is_refused_as_a_cost_bound() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password("x" * 2000)


def test_shape_is_not_a_password_rule() -> None:
    """
    NIST SP 800-63B recommends length over character classes: a long
    passphrase of only lower-case letters is a good password and must not
    be refused for lacking a symbol.
    """

    validate_password("cavallo batteria graffetta")


def test_a_credential_round_trips_through_its_encoding() -> None:
    original = PasswordHash(
        algorithm="scrypt",
        parameters=(("n", "32768"), ("r", "8"), ("p", "1")),
        salt=b"sixteen-byte-slt",
        digest=b"a thirty-two byte digest value!!",
    )

    assert PasswordHash.decode(original.encode()) == original


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "scrypt",
        "scrypt$n=1$salt",
        "scrypt$n=1$salt$digest$extra",
        "$n=1$c2FsdA$ZGlnZXN0",
        "scrypt$broken$c2FsdA$ZGlnZXN0",
    ],
)
def test_an_unreadable_credential_is_refused_not_guessed(
    encoded: str,
) -> None:
    """
    A credential this system cannot read is one it must not compare
    against. Treating it as a mismatch would be tolerable; treating it as
    a match would be catastrophic, so it does neither.
    """

    with pytest.raises(MalformedPasswordHashError):
        PasswordHash.decode(encoded)


# --- Sessions ------------------------------------------------------------


def _session(
    *,
    issued_at: datetime = NOW,
    last_seen_at: datetime = NOW,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> AuthenticationSession:
    return AuthenticationSession(
        session_id=1,
        user_id=7,
        token_fingerprint="f" * 64,
        issued_at=issued_at,
        last_seen_at=last_seen_at,
        expires_at=expires_at or (issued_at + timedelta(hours=12)),
        revoked_at=revoked_at,
    )


POLICY = SessionPolicy(
    idle_timeout=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=12),
)


def test_a_fresh_session_is_active() -> None:
    assert POLICY.status_at(_session(), NOW) is SessionStatus.ACTIVE


def test_a_session_unused_past_the_idle_timeout_is_idle_expired() -> None:
    session = _session()

    assert (
        POLICY.status_at(session, NOW + timedelta(hours=2, seconds=1))
        is SessionStatus.IDLE_EXPIRED
    )


def test_using_a_session_defers_only_the_idle_clock() -> None:
    """
    The absolute lifetime is what a user cannot extend by working, and it
    is what bounds the value of a stolen token.
    """

    used = _session().touched_at(NOW + timedelta(hours=11))

    assert POLICY.status_at(used, NOW + timedelta(hours=11)) is (
        SessionStatus.ACTIVE
    )
    assert POLICY.status_at(used, NOW + timedelta(hours=12)) is (
        SessionStatus.EXPIRED
    )


def test_revocation_beats_every_clock() -> None:
    revoked = _session().revoked(NOW)

    assert POLICY.status_at(revoked, NOW) is SessionStatus.REVOKED
    assert (
        POLICY.status_at(revoked, NOW + timedelta(days=30))
        is SessionStatus.REVOKED
    )


def test_revoking_twice_keeps_the_first_revocation_time() -> None:
    """When it ended is the auditable fact; a second logout does not
    change it."""

    once = _session().revoked(NOW)
    twice = once.revoked(NOW + timedelta(hours=1))

    assert twice.revoked_at == NOW


def test_the_absolute_ceiling_is_fixed_when_the_session_is_created() -> None:
    assert POLICY.expires_at(NOW) == NOW + timedelta(hours=12)


# --- Audit identity ------------------------------------------------------


def _identity(role: Role = Role.ENGINEER, user_id: int = 7) -> AuditIdentity:
    return AuditIdentity(
        user_id=user_id,
        email="ada@example.com",
        display_name="Ada Lovelace",
        role=role,
        session_id=42,
    )


def test_an_audit_identity_names_the_session_it_acted_under() -> None:
    """
    "User 7 did this" and "user 7, in the session opened at 09:14, did
    this" are different statements, and only the second correlates with
    the login before it.
    """

    assert _identity().session_id == 42


def test_an_audit_identity_carries_nothing_secret() -> None:
    """
    It is logged in full as the actor of an audit event, so it must have
    nowhere to put a credential.
    """

    fields = set(AuditIdentity.__dataclass_fields__)

    assert fields == {
        "user_id",
        "email",
        "display_name",
        "role",
        "session_id",
    }


def test_an_audit_identity_answers_its_own_permissions() -> None:
    assert _identity(Role.ADMINISTRATOR).permits(Capability.MANAGE_USERS)
    assert not _identity(Role.ENGINEER).permits(Capability.MANAGE_USERS)


def test_describing_an_identity_is_safe_to_log() -> None:
    described = _identity().describe()

    assert "Ada Lovelace" in described
    assert "engineer" in described


# --- Project access ------------------------------------------------------


def test_an_owner_may_administer_their_own_project() -> None:
    assert may_administer_project(_identity(user_id=7), owner_user_id=7)


def test_an_engineer_may_not_administer_someone_elses_project() -> None:
    assert not may_administer_project(_identity(user_id=7), owner_user_id=9)


def test_an_administrator_may_administer_any_project() -> None:
    assert may_administer_project(
        _identity(Role.ADMINISTRATOR, user_id=1), owner_user_id=9
    )


def test_a_project_with_no_owner_stays_administrable() -> None:
    """
    Every project created before ownership existed. Retro-assigning an
    owner would be inventing a fact; refusing access would break a
    working installation.
    """

    assert may_administer_project(_identity(user_id=7), owner_user_id=None)


# --- The rule the whole EPIC rests on ------------------------------------


def test_a_user_has_nowhere_to_record_an_engineering_artefact() -> None:
    """
    The dependency runs one way. If a user could hold an entity, a fact
    or a statement, an engineering artefact would have a person in its
    identity and the pipeline would stop being deterministic.
    """

    fields = set(User.__dataclass_fields__)

    assert fields == {
        "user_id",
        "email",
        "display_name",
        "role",
        "status",
        "encoded_credential",
        "created_at",
        "credential_updated_at",
    }


def test_a_disabled_user_is_not_a_deleted_one() -> None:
    """
    An engineering platform must be able to say who performed an action
    years after that person left.
    """

    assert {status.value for status in UserStatus} == {"active", "disabled"}
