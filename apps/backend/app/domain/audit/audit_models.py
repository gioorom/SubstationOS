"""
What happened, who did it, and how it ended.

An audit event is a **record of an action**, not of a state. It is
append-only by design: there is no update and no delete on this
aggregate, and the repository port declares none. An audit trail that can
be edited is not an audit trail.

Five fields, and the EPIC that introduced this context named all of them:
actor, timestamp, action, resource, outcome. Everything else is
``detail`` - a short, human-readable clause explaining an outcome that
needs one.

**Nothing sensitive is representable here.** There is no field for a
password, a token, a session fingerprint or a request body, and that is
structural rather than a convention: a value with nowhere to go cannot
be written by accident. The actor is an ``AuditIdentity``, which carries
no credential of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.identity.audit_identity import AuditIdentity


class AuditAction(str, Enum):
    """
    The catalogue of auditable actions.

    A closed vocabulary, so "what can appear in the trail?" has an answer
    that can be read rather than discovered. It grows when a milestone
    adds an action worth recording, and each addition is a deliberate
    decision rather than a free-text string somebody typed at a call
    site.
    """

    #: Identity lifecycle.
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    USER_CREATED = "user_created"
    USER_DISABLED = "user_disabled"

    #: Engineering platform actions.
    PROJECT_CREATED = "project_created"
    DOCUMENT_UPLOADED = "document_uploaded"
    PIPELINE_EXECUTED = "pipeline_executed"
    WORKSPACE_ACCESSED = "workspace_accessed"

    #: Human Review (EPIC 30.4). A governed engineering judgement is an
    #: action, and "what did this person decide on Tuesday?" is asked of
    #: the audit trail like any other.
    ENGINEERING_REVIEW_RECORDED = "engineering_review_recorded"
    ENGINEERING_REVIEW_SUPERSEDED = "engineering_review_superseded"

    #: Governed Knowledge Graph (EPIC 31).
    KNOWLEDGE_PROMOTED = "knowledge_promoted"
    KNOWLEDGE_GRAPH_REBUILT = "knowledge_graph_rebuilt"

    #: Refusals worth seeing in aggregate.
    ACCESS_DENIED = "access_denied"


class AuditOutcome(str, Enum):
    """
    How the action ended.

    ``DENIED`` is kept apart from ``FAILED`` because they are different
    events to whoever reads the trail: one is the system refusing a
    request it understood, the other is a request that was permitted and
    did not work.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class AuditActor:
    """
    Who acted.

    Deliberately **not** an ``AuditIdentity`` field-for-field: a failed
    login has an actor and no verified identity, and modelling that as an
    optional identity would let unauthenticated input into a field whose
    whole value is that it cannot contain any.

    So an actor is either verified - copied from an ``AuditIdentity`` -
    or anonymous, in which case ``user_id`` and ``session_id`` are
    ``None`` and ``description`` holds only what the request claimed. A
    reader can always tell which, because ``authenticated`` says so.
    """

    authenticated: bool
    user_id: int | None
    session_id: int | None
    description: str

    @classmethod
    def of(cls, identity: AuditIdentity) -> "AuditActor":
        return cls(
            authenticated=True,
            user_id=identity.user_id,
            session_id=identity.session_id,
            description=identity.describe(),
        )

    @classmethod
    def anonymous(cls, description: str = "anonymous") -> "AuditActor":
        """
        An unauthenticated actor.

        ``description`` may carry an address someone *claimed* at a login
        form. It is untrusted input and is recorded as such - it says
        what was attempted, never who attempted it.
        """

        return cls(
            authenticated=False,
            user_id=None,
            session_id=None,
            description=description,
        )


@dataclass(frozen=True, slots=True)
class AuditResource:
    """
    What was acted upon.

    A type and an optional identifier, both plain strings, because the
    audit context must be able to name a project, a document or a user
    without importing any of their bounded contexts - and without
    acquiring a foreign key that would stop the row being writable once
    the thing it names is gone.
    """

    resource_type: str
    resource_id: str | None = None

    def describe(self) -> str:
        if self.resource_id is None:
            return self.resource_type

        return f"{self.resource_type}:{self.resource_id}"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One recorded action."""

    event_id: int | None
    occurred_at: datetime
    action: AuditAction
    outcome: AuditOutcome
    actor: AuditActor
    resource: AuditResource
    detail: str | None = None
