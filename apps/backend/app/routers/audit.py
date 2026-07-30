"""
The audit trail API.

```
GET /audit/events   the most recent recorded actions   (administrator)
```

Read-only, and there is no write endpoint by design: the trail is
appended to by the services that perform the audited actions, never by a
caller. An API that let a client post an audit event would be an API for
writing fiction into the record.

``READ_AUDIT_TRAIL`` rather than ``MANAGE_USERS``: reading who did what
is a different permission from creating accounts, even though only one
role carries both today. The capability is what the route declares, so a
future auditor role needs no change here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.audit.audit_models import AuditAction, AuditEvent
from app.domain.identity.identity_roles import Capability
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.routers.security import require_capability
from app.schemas.identity import (
    AuditActorRead,
    AuditEventListResponse,
    AuditEventRead,
)

router = APIRouter(prefix="/audit", tags=["Audit"])

DEFAULT_LIMIT = 100

MAX_LIMIT = 500
"""
Refused rather than clamped, like every other bound in this API: a caller
who asked for a thousand should learn that they cannot have one, not
receive five hundred and believe it was all of them.
"""


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/events",
    response_model=AuditEventListResponse,
    dependencies=[Depends(require_capability(Capability.READ_AUDIT_TRAIL))],
    responses={
        403: {"description": "The caller may not read the audit trail."},
    },
    summary="The most recent audit events, newest first",
)
def list_audit_events(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    action: AuditAction | None = Query(default=None),
    user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AuditEventListResponse:
    events = SqlAlchemyAuditRepository(db).list_recent(
        limit=limit, action=action, user_id=user_id
    )

    return AuditEventListResponse(
        items=tuple(_read(event) for event in events)
    )


def _read(event: AuditEvent) -> AuditEventRead:
    return AuditEventRead(
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        action=event.action,
        outcome=event.outcome,
        actor=AuditActorRead(
            authenticated=event.actor.authenticated,
            user_id=event.actor.user_id,
            session_id=event.actor.session_id,
            description=event.actor.description,
        ),
        resource_type=event.resource.resource_type,
        resource_id=event.resource.resource_id,
        detail=event.detail,
    )
