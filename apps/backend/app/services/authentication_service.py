"""
Application service for authentication.

Three operations, and the boundaries between them are the three
questions this EPIC keeps apart:

- ``authenticate`` - *who is making this request?* Proves a password and
  opens a session.
- ``validate_session`` - the same question on every subsequent request,
  answered from a token rather than a password.
- ``end_session`` - revokes one.

Authorization is **not** here. Whether an identity may do a thing is a
pure function of its role and the capability required
(``identity_roles.role_permits``), evaluated at the API boundary. Merging
the two would mean every future permission question had to be asked
inside authentication, which is how "can this user read that project?"
ends up in a login function.

The engineering domain is not imported by this module and does not import
it. Running the pipeline under two different logins produces byte-identical
artefacts, because no artefact has anywhere to record who ran it.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.authentication_outcomes import (
    AuthenticationFailureCode,
    AuthenticationResult,
    SessionRejectionCode,
    SessionValidation,
)
from app.domain.identity.identity_exceptions import (
    MalformedPasswordHashError,
)
from app.domain.identity.identity_models import EmailAddress, User
from app.domain.identity.identity_repository import (
    SessionRepository,
    UserRepository,
)
from app.domain.identity.password_credential import PasswordHash
from app.domain.identity.password_hasher_port import PasswordHasher
from app.domain.identity.session_models import (
    AuthenticationSession,
    SessionStatus,
)
from app.domain.identity.session_policy import (
    DEFAULT_SESSION_POLICY,
    SessionPolicy,
)
from app.domain.identity.token_generator_port import SecureTokenGenerator

#: How stale `last_seen_at` may get before a validating request writes it.
#:
#: Without this, every authenticated request would `UPDATE` the session
#: row, turning a read-only page load into a write. The idle timeout is
#: measured in hours, so a minute of imprecision costs nothing and
#: removes almost all of the writes.
LAST_SEEN_WRITE_INTERVAL_SECONDS = 60


def authenticate(
    users: UserRepository,
    sessions: SessionRepository,
    hasher: PasswordHasher,
    tokens: SecureTokenGenerator,
    *,
    email: str,
    password: str,
    now: datetime,
    policy: SessionPolicy = DEFAULT_SESSION_POLICY,
) -> AuthenticationResult:
    """
    Proves a password and opens a session.

    **User enumeration.** Every refusal returns the same shape, and the
    router turns every one of them into the same status and the same
    sentence. The internal ``AuthenticationFailureCode`` is for the audit
    trail and never for the caller: an API that answered "no such
    account" differently from "wrong password" would be a service for
    discovering who has an account here.

    **Timing.** An address nobody has registered still costs one full key
    derivation - see ``_absorb_timing``. Skipping the work for unknown
    users would make a non-existent account answer measurably faster
    than a real one, which is the same disclosure by a slower channel.

    **Session fixation is unrepresentable.** A session is only ever
    created here, its token is only ever produced by the generator, and
    no input to this function can influence it. There is no code path in
    which a caller-supplied token becomes an authenticated session, so
    there is nothing to fixate.
    """

    try:
        address = EmailAddress(email)
    except Exception:
        # A malformed address cannot match a user. Answered like every
        # other refusal, after paying the same cost.
        _absorb_timing(hasher, password)

        return AuthenticationResult.refused(
            AuthenticationFailureCode.UNKNOWN_IDENTITY
        )

    user = users.find_by_email(address)

    if user is None:
        _absorb_timing(hasher, password)

        return AuthenticationResult.refused(
            AuthenticationFailureCode.UNKNOWN_IDENTITY
        )

    try:
        stored = PasswordHash.decode(user.encoded_credential)
        matches = hasher.verify(password, stored)
    except MalformedPasswordHashError:
        # An operator problem, not a user one: the credential on this row
        # cannot be read. Refused rather than treated as a mismatch that
        # a user could try to "fix" by guessing.
        return AuthenticationResult.refused(
            AuthenticationFailureCode.UNREADABLE_CREDENTIAL
        )

    if not matches:
        return AuthenticationResult.refused(
            AuthenticationFailureCode.INVALID_CREDENTIAL
        )

    if not user.is_active:
        # Checked *after* the password, so a disabled account is not
        # distinguishable from an active one by trying a wrong password
        # against it.
        return AuthenticationResult.refused(
            AuthenticationFailureCode.DISABLED_ACCOUNT
        )

    user = _rehash_if_stale(
        users, hasher, user=user, stored=stored, password=password, now=now
    )

    token = tokens.issue()

    session = sessions.add(
        AuthenticationSession(
            session_id=None,
            user_id=user.user_id,
            token_fingerprint=tokens.fingerprint(token),
            issued_at=now,
            last_seen_at=now,
            expires_at=policy.expires_at(now),
            revoked_at=None,
        )
    )

    return AuthenticationResult.granted(
        identity=_identity_of(user, session),
        token=token,
        expires_at=session.expires_at,
    )


def validate_session(
    users: UserRepository,
    sessions: SessionRepository,
    tokens: SecureTokenGenerator,
    *,
    token: str | None,
    now: datetime,
    policy: SessionPolicy = DEFAULT_SESSION_POLICY,
) -> SessionValidation:
    """
    Turns a presented token into a verified identity, or a reason.

    The user is re-read on every request rather than trusted from the
    session, so disabling an account ends its live sessions at the next
    request instead of whenever they happen to expire. That is one extra
    read per request and it is what makes "disable this account" mean
    something immediately.
    """

    if not token:
        return SessionValidation.rejected(SessionRejectionCode.MISSING_TOKEN)

    session = sessions.find_by_fingerprint(tokens.fingerprint(token))

    if session is None:
        return SessionValidation.rejected(
            SessionRejectionCode.UNKNOWN_SESSION
        )

    status = policy.status_at(session, now)

    if status is not SessionStatus.ACTIVE:
        return SessionValidation.rejected(_REJECTION_FOR_STATUS[status])

    user = users.find_by_id(session.user_id)

    if user is None:
        return SessionValidation.rejected(
            SessionRejectionCode.UNKNOWN_IDENTITY
        )

    if not user.is_active:
        return SessionValidation.rejected(
            SessionRejectionCode.DISABLED_ACCOUNT
        )

    if _should_write_last_seen(session, now):
        session = sessions.save(session.touched_at(now))

    return SessionValidation.authenticated(
        _identity_of(user, session), session.expires_at
    )


def end_session(
    sessions: SessionRepository,
    tokens: SecureTokenGenerator,
    *,
    token: str | None,
    now: datetime,
) -> bool:
    """
    Revokes the session a token names. Returns whether one was ended.

    Idempotent, and deliberately incurious: logging out with no token, an
    unknown token or an already-revoked one is a success from the
    caller's point of view, because in every case they finish without a
    session. Answering differently would make logout a way to test
    whether a stolen token is still live.
    """

    if not token:
        return False

    session = sessions.find_by_fingerprint(tokens.fingerprint(token))

    if session is None or session.is_revoked:
        return False

    sessions.save(session.revoked(now))

    return True


def end_all_sessions(
    sessions: SessionRepository, *, user_id: int, now: datetime
) -> int:
    """
    Revokes every live session of one user.

    Called on a password change. A password changed because it might be
    known to somebody else is worth nothing while the sessions it opened
    are still authenticating requests.
    """

    return sessions.revoke_all_for_user(user_id, now=now)


_REJECTION_FOR_STATUS: dict[SessionStatus, SessionRejectionCode] = {
    SessionStatus.REVOKED: SessionRejectionCode.REVOKED_SESSION,
    SessionStatus.EXPIRED: SessionRejectionCode.EXPIRED_SESSION,
    SessionStatus.IDLE_EXPIRED: SessionRejectionCode.IDLE_SESSION,
}


def _identity_of(
    user: User, session: AuthenticationSession
) -> AuditIdentity:
    return AuditIdentity(
        user_id=user.user_id,
        email=user.email.value,
        display_name=user.display_name.value,
        role=user.role,
        session_id=session.session_id,
    )


def _absorb_timing(hasher: PasswordHasher, password: str) -> None:
    """
    Spends the cost of a verification without having anything to verify.

    Hashing the presented password and discarding it performs the same
    key derivation, with the same parameters, that a real account would
    have cost. No stored dummy credential is needed, and no module-level
    state is introduced to hold one.
    """

    hasher.hash(password)


def _rehash_if_stale(
    users: UserRepository,
    hasher: PasswordHasher,
    *,
    user: User,
    stored: PasswordHash,
    password: str,
    now: datetime,
) -> User:
    """
    Re-derives a credential under current parameters, on login.

    A successful login is the only moment the plaintext password is
    legitimately in memory, so it is the only moment a credential can be
    strengthened without asking the user for anything. A failure to
    persist the stronger hash must not fail the login: the user proved
    their password, and the weaker credential still works.
    """

    if not hasher.needs_rehash(stored):
        return user

    try:
        return users.save(
            user.with_credential(hasher.hash(password).encode(), now=now)
        )
    except Exception:
        return user


def _should_write_last_seen(
    session: AuthenticationSession, now: datetime
) -> bool:
    return (
        now - session.last_seen_at
    ).total_seconds() >= LAST_SEEN_WRITE_INTERVAL_SECONDS
