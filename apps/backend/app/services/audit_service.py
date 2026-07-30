"""
Recording what happened.

One function per shape of event, so a call site names the action rather
than assembling a record. Every one of them **swallows its own storage
failures**, and that is a deliberate, uncomfortable decision worth
stating plainly:

An audit write that fails must not fail the action it was auditing. A
login that worked, refused at the last moment because the trail could not
be appended to, is a worse outcome than a login that worked and is
missing from the trail - and refusing every request when the audit table
is unwritable turns a logging fault into a total outage.

The failure is not silent: it is logged at ``exception`` level with the
event that could not be written, which is the loudest thing available to
a component that has just discovered it cannot write things down.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.domain.audit.audit_models import (
    AuditAction,
    AuditActor,
    AuditEvent,
    AuditOutcome,
    AuditResource,
)
from app.domain.audit.audit_repository import AuditRepository
from app.domain.identity.audit_identity import AuditIdentity

logger = logging.getLogger(__name__)


def record(
    repository: AuditRepository,
    *,
    action: AuditAction,
    outcome: AuditOutcome,
    actor: AuditActor,
    resource: AuditResource,
    now: datetime,
    detail: str | None = None,
) -> AuditEvent | None:
    """
    Appends one event.

    Returns the stored event, or ``None`` when it could not be written -
    a return value no caller is expected to branch on, and which exists
    so a test can prove the swallowing is real rather than accidental.
    """

    event = AuditEvent(
        event_id=None,
        occurred_at=now,
        action=action,
        outcome=outcome,
        actor=actor,
        resource=resource,
        detail=detail,
    )

    try:
        return repository.record(event)
    except Exception:
        # Deliberately broad, and deliberately not re-raised. See the
        # module docstring: the audited action has already happened.
        logger.exception(
            "Audit event could not be recorded: %s %s on %s by %s",
            action.value,
            outcome.value,
            resource.describe(),
            actor.description,
        )

        return None


def record_for_identity(
    repository: AuditRepository,
    *,
    identity: AuditIdentity,
    action: AuditAction,
    outcome: AuditOutcome,
    resource: AuditResource,
    now: datetime,
    detail: str | None = None,
) -> AuditEvent | None:
    """The common case: an authenticated actor did something."""

    return record(
        repository,
        action=action,
        outcome=outcome,
        actor=AuditActor.of(identity),
        resource=resource,
        now=now,
        detail=detail,
    )


def record_pipeline_execution(
    repository: AuditRepository,
    *,
    identity: AuditIdentity,
    stage: str,
    document_id: int,
    succeeded: bool,
    reused: bool,
    now: datetime,
) -> AuditEvent | None:
    """
    Records that somebody ran a pipeline stage.

    The event is the only place a person appears anywhere near the
    deterministic pipeline. **Nothing it records changes what the stage
    produced**: `reused` is reported because re-using an existing
    artefact is what the stage did, not because the identity influenced
    it, and the artefacts themselves carry no actor and no timestamp -
    which is exactly why two runs under two logins compare equal.
    """

    return record_for_identity(
        repository,
        identity=identity,
        action=AuditAction.PIPELINE_EXECUTED,
        outcome=(
            AuditOutcome.SUCCEEDED if succeeded else AuditOutcome.FAILED
        ),
        resource=AuditResource("document", str(document_id)),
        now=now,
        detail=f"stage={stage} reused={str(reused).lower()}",
    )


def record_anonymous(
    repository: AuditRepository,
    *,
    action: AuditAction,
    outcome: AuditOutcome,
    resource: AuditResource,
    now: datetime,
    attempted_identifier: str | None = None,
    detail: str | None = None,
) -> AuditEvent | None:
    """
    An unauthenticated actor did something - a failed login, a rejected
    anonymous request.

    ``attempted_identifier`` is whatever the caller *claimed* to be. It
    is untrusted input, is recorded as an attempt rather than as an
    identity, and is truncated by the repository.
    """

    return record(
        repository,
        action=action,
        outcome=outcome,
        actor=AuditActor.anonymous(
            "anonymous"
            if attempted_identifier is None
            else f"anonymous (attempted: {attempted_identifier})"
        ),
        resource=resource,
        now=now,
        detail=detail,
    )
