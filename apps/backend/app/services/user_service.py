"""
Application service for managing users.

Creating an account, changing a password, disabling access. Everything
here is an administrative or self-service action on an identity; none of
it authenticates anything.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.identity.identity_exceptions import (
    MalformedPasswordHashError,
    UserNotFoundError,
)
from app.domain.identity.identity_models import (
    DisplayName,
    EmailAddress,
    User,
    UserStatus,
)
from app.domain.identity.identity_repository import (
    SessionRepository,
    UserRepository,
)
from app.domain.identity.identity_roles import Role
from app.domain.identity.password_credential import (
    PasswordHash,
    validate_password,
)
from app.domain.identity.password_hasher_port import PasswordHasher


def create_user(
    users: UserRepository,
    hasher: PasswordHasher,
    *,
    email: str,
    display_name: str,
    password: str,
    role: Role,
    now: datetime,
) -> User:
    """
    Registers a new account.

    Raises ``InvalidEmailAddressError``, ``InvalidDisplayNameError``,
    ``WeakPasswordError`` or ``DuplicateEmailAddressError``. The password
    is validated **before** it is hashed, so a refused password never
    costs a key derivation.
    """

    address = EmailAddress(email)
    name = DisplayName(display_name)
    validate_password(password)

    return users.add(
        User(
            user_id=None,
            email=address,
            display_name=name,
            role=role,
            status=UserStatus.ACTIVE,
            encoded_credential=hasher.hash(password).encode(),
            created_at=now,
            credential_updated_at=now,
        )
    )


def change_password(
    users: UserRepository,
    sessions: SessionRepository,
    hasher: PasswordHasher,
    *,
    user_id: int,
    current_password: str,
    new_password: str,
    now: datetime,
) -> bool:
    """
    Changes a user's own password. Returns ``False`` if the current
    password was wrong.

    Two properties this function exists to guarantee:

    - **The current password is required.** Otherwise anyone who found an
      unlocked, logged-in browser could take the account permanently
      rather than until the session expired.
    - **Every session is ended, including the caller's.** A password is
      most often changed because it may be known to someone else, and
      leaving the sessions it opened alive would defeat the change. The
      caller is logged out too; that is a deliberate cost, and the API
      says so.
    """

    user = users.find_by_id(user_id)

    if user is None:
        raise UserNotFoundError("This user no longer exists.", user_id=user_id)

    try:
        stored = PasswordHash.decode(user.encoded_credential)

        if not hasher.verify(current_password, stored):
            return False
    except MalformedPasswordHashError:
        return False

    validate_password(new_password)

    users.save(
        user.with_credential(hasher.hash(new_password).encode(), now=now)
    )

    sessions.revoke_all_for_user(user_id, now=now)

    return True


def set_status(
    users: UserRepository,
    sessions: SessionRepository,
    *,
    user_id: int,
    status: UserStatus,
    now: datetime,
) -> User:
    """
    Enables or disables an account.

    Disabling revokes every live session immediately. Without that,
    "disabled" would mean "may not log in again", and an account disabled
    because of an incident would keep working for hours.

    The user row is never deleted - see ``UserStatus`` on why an audit
    trail full of unresolvable actor ids is worse than a disabled row.
    """

    user = users.find_by_id(user_id)

    if user is None:
        raise UserNotFoundError("This user no longer exists.", user_id=user_id)

    updated = users.save(
        User(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            status=status,
            encoded_credential=user.encoded_credential,
            created_at=user.created_at,
            credential_updated_at=user.credential_updated_at,
        )
    )

    if status is UserStatus.DISABLED:
        sessions.revoke_all_for_user(user_id, now=now)

    return updated


def has_any_user(users: UserRepository) -> bool:
    """
    Whether the installation has been bootstrapped.

    The first administrator has to come from somewhere, and every
    mechanism for creating one is a mechanism for creating one. This
    predicate is what lets the bootstrap script refuse to run twice.
    """

    return users.count() > 0
