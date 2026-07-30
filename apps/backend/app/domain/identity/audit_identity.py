"""
Who performed an action, and under which authenticated session.

``AuditIdentity`` is the single value the application layer receives once
a request has been authenticated. It answers the third of the three
questions this context keeps apart:

- authentication: *who is making this request?*
- authorization: *may they do this?*
- **audit identity: who did it, and under which proof of identity?**

The session is part of the answer on purpose. "User 7 deleted this" and
"user 7, in the session opened from this login at 09:14, deleted this"
are different statements, and only the second can be correlated with the
login that preceded it and the logout that followed.

---

**Audit identity attaches to actions, never to artefacts.**

This is the load-bearing rule of the whole EPIC. An `EngineeringEntity`,
an `EngineeringFact` and a `SemanticStatement` are functions of the
document's bytes and the versioned rules that read them. If any of them
carried a user, then running the pipeline twice under two different
logins would produce two different artefacts, idempotency would break,
re-use detection would stop working, and "why does the system believe
this?" would acquire an answer involving a person - which is exactly what
a deterministic engineering platform must never say.

So identity is recorded on the *event*: `pipeline_execution` by whom, at
what time, against which document, with what outcome. The artefacts that
execution produced remain identical either way, and an architecture test
asserts that no engineering domain module imports this one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.identity.identity_roles import Capability, Role, role_permits


@dataclass(frozen=True, slots=True)
class AuditIdentity:
    """
    A verified identity, as the application layer sees it.

    Constructed only after a session has been validated. There is no way
    to build one from a request header, a query parameter or a claim the
    caller made about themselves - the only producer is the
    authentication service, and that is the point.

    Carries no credential, no token and no fingerprint. It is safe to log
    in full, which is what makes it usable as the actor of an audit
    event.
    """

    user_id: int
    email: str
    display_name: str
    role: Role
    session_id: int

    def permits(self, capability: Capability) -> bool:
        """Whether this identity carries the capability."""

        return role_permits(self.role, capability)

    @property
    def is_administrator(self) -> bool:
        return self.role is Role.ADMINISTRATOR

    def describe(self) -> str:
        """
        A short, log-safe rendering: ``"Ada Lovelace <ada@…> (engineer)"``.

        Every component is already public to the holder of the audit
        trail, and none of them is a secret.
        """

        return f"{self.display_name} <{self.email}> ({self.role.value})"
