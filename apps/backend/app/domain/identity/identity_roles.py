"""
What an authenticated identity is allowed to do.

**Three levels, and deliberately only three.** The EPIC that introduced
this context asked for anonymous, authenticated and administrator, and
warned against inventing dozens of roles ahead of a requirement. Every
role added here is a role that has to be migrated, documented and
reasoned about for the life of the product, so this catalogue grows when
a real permission needs it and not before.

Project-scoped roles (owner, reviewer, contributor) are **not** here.
They belong to a project-membership model this milestone deliberately
does not build; see ``project_access.py`` for the one conservative
ownership rule that does exist.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """
    The role carried by an authenticated user.

    ``ENGINEER`` is the ordinary authenticated user of this platform:
    they may read and run everything the engineering pipeline exposes.
    ``ADMINISTRATOR`` additionally manages identities and reads the
    audit trail.

    There is no ``ANONYMOUS`` member on purpose. Anonymous is the
    *absence* of an identity, not a role an identity can hold, and a
    member here would be a value that could be stored on a user row.
    """

    ENGINEER = "engineer"
    ADMINISTRATOR = "administrator"


class Capability(str, Enum):
    """
    A named thing an identity may be permitted to do.

    Capabilities exist so an endpoint declares *what it needs* rather
    than *which role may have it*. When project membership arrives, a
    capability can be granted by a role or by a membership without every
    call site learning about the new source.
    """

    #: Read and run the deterministic engineering pipeline.
    USE_ENGINEERING_PLATFORM = "use_engineering_platform"

    #: Create, update and archive projects.
    MANAGE_PROJECTS = "manage_projects"

    #: Create, disable and re-role user accounts.
    MANAGE_USERS = "manage_users"

    #: Read the audit trail.
    READ_AUDIT_TRAIL = "read_audit_trail"

    #: Record an engineering judgement over a pipeline artefact
    #: (EPIC 30.4). Distinct from ``USE_ENGINEERING_PLATFORM``, which
    #: covers *reading* reviews: an auditor role that may read every
    #: judgement without passing one is a role this separation already
    #: admits, without any route changing.
    RECORD_ENGINEERING_REVIEW = "record_engineering_review"


_CAPABILITIES_BY_ROLE: dict[Role, frozenset[Capability]] = {
    Role.ENGINEER: frozenset(
        {
            Capability.USE_ENGINEERING_PLATFORM,
            Capability.MANAGE_PROJECTS,
            # Reviewing the pipeline is what an engineer on this platform
            # is for. A separate "reviewer" role would be a second role
            # every engineer would have to be granted on day one.
            Capability.RECORD_ENGINEERING_REVIEW,
        }
    ),
    Role.ADMINISTRATOR: frozenset(Capability),
}


def capabilities_of(role: Role) -> frozenset[Capability]:
    """Every capability the role carries. Total over ``Role``."""

    return _CAPABILITIES_BY_ROLE[role]


def role_permits(role: Role, capability: Capability) -> bool:
    """
    Whether the role carries the capability.

    A pure function over two enums: no request, no session, no database.
    That is what makes the authorization rule testable in isolation and
    what keeps it from drifting into the transport layer.
    """

    return capability in _CAPABILITIES_BY_ROLE[role]
