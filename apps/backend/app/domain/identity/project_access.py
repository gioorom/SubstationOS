"""
Who may administer a project.

**Deliberately one rule, and deliberately not a membership model.**

The long-term shape is:

```
user  ->  project membership  ->  permissions
```

None of that exists yet, and building it now would mean a table, an
invitation flow, a role editor and a permission catalogue - every one of
which is a commitment made before a requirement. What this milestone
establishes is the *concept*: a project has an owner, that owner is a
verified user, and the destructive operation on a project consults it.

The rule below is the whole of the current model:

- an administrator may administer any project;
- the owner may administer their own;
- a project with no owner - every project created before this
  milestone - may be administered by any authenticated engineer.

That last clause is the honest one. Retro-assigning an owner to existing
projects would be inventing a fact; refusing all access to them would
break a working installation. So they are readable and administrable as
before, and the API records an owner from now on.

This module is imported by the projects router through the application
layer. It knows nothing about HTTP, sessions or the database, and takes
the two things the decision actually depends on.
"""

from __future__ import annotations

from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability


def may_administer_project(
    identity: AuditIdentity, owner_user_id: int | None
) -> bool:
    """
    Whether ``identity`` may perform a destructive operation on a project
    owned by ``owner_user_id``.

    "Administer" means archive, restore or delete. Reading a project and
    working with its documents are **not** governed here: this milestone
    introduces no per-project read permissions, and pretending otherwise
    by adding a function nobody calls would be worse than saying so.
    """

    if not identity.permits(Capability.MANAGE_PROJECTS):
        return False

    if identity.is_administrator:
        return True

    if owner_user_id is None:
        # Pre-ownership projects. See the module docstring: this is a
        # migration accommodation with a stated end, not a permission.
        return True

    return identity.user_id == owner_user_id
