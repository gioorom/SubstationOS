"""
Creates the first administrator.

The first account has to come from somewhere, and every mechanism for
creating one is a mechanism for creating one - so this is the only one,
it runs on the server, and it refuses once an account exists.

    python scripts/create_administrator.py --email ada@example.com \\
        --name "Ada Lovelace"

The password is read from the terminal without echo, or from
``SUBSTATIONOS_ADMIN_PASSWORD`` for an automated provision. It is
**never** taken from a command-line argument: arguments appear in shell
history and in the process list, where every other user on the machine
can read them.

Refuses to run when any user already exists. A script that could mint an
administrator into a running installation would be a privilege-escalation
tool sitting in the repository; recovering a lost administrator is a
deliberate database operation, not a command.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPOSITORY_ROOT / "apps" / "backend"

PASSWORD_ENVIRONMENT_VARIABLE = "SUBSTATIONOS_ADMIN_PASSWORD"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the first SubstationOS administrator."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--allow-additional",
        action="store_true",
        help=(
            "Create an administrator even though accounts already exist. "
            "Intended for recovering an installation that has lost its "
            "last administrator; every use is a deliberate one."
        ),
    )

    arguments = parser.parse_args()

    sys.path.insert(0, str(BACKEND_ROOT))

    from app.database.database import SessionLocal  # noqa: PLC0415
    from app.domain.identity.identity_exceptions import (  # noqa: PLC0415
        DuplicateEmailAddressError,
        IdentityError,
    )
    from app.domain.identity.identity_roles import Role  # noqa: PLC0415
    from app.infrastructure.identity.scrypt_password_hasher import (  # noqa: PLC0415, E501
        ScryptPasswordHasher,
    )
    from app.infrastructure.identity.sqlalchemy_user_repository import (  # noqa: PLC0415, E501
        SqlAlchemyUserRepository,
    )
    from app.services import user_service  # noqa: PLC0415

    password = _read_password()

    if password is None:
        print("No password supplied; nothing was created.", file=sys.stderr)
        return 2

    with SessionLocal() as database:
        users = SqlAlchemyUserRepository(database)

        if user_service.has_any_user(users) and not arguments.allow_additional:
            print(
                "This installation already has accounts. Refusing to "
                "create another administrator; pass --allow-additional "
                "if that is genuinely what you intend.",
                file=sys.stderr,
            )
            return 1

        try:
            user = user_service.create_user(
                users,
                ScryptPasswordHasher(),
                email=arguments.email,
                display_name=arguments.name,
                password=password,
                role=Role.ADMINISTRATOR,
                now=datetime.utcnow(),
            )
        except DuplicateEmailAddressError:
            print(
                f"An account already exists for {arguments.email}.",
                file=sys.stderr,
            )
            return 1
        except IdentityError as error:
            print(str(error), file=sys.stderr)
            return 1

    print(f"Created administrator {user.email} (id {user.user_id}).")

    return 0


def _read_password() -> str | None:
    """
    From the environment, or from the terminal without echo.

    Never from an argument. Confirmed when typed, because a mistyped
    password on the only account in the installation is a locked door.
    """

    from_environment = os.environ.get(PASSWORD_ENVIRONMENT_VARIABLE)

    if from_environment:
        return from_environment

    if not sys.stdin.isatty():
        return None

    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")

    if first != second:
        print("The passwords do not match.", file=sys.stderr)
        return None

    return first


if __name__ == "__main__":
    raise SystemExit(main())
