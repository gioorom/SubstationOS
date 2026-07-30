"""
SQLAlchemy adapter for the ``AuditRepository`` port.

Append and read. There is no update and no delete here because the port
declares none, and the absence is the guarantee.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit.audit_models import (
    AuditAction,
    AuditActor,
    AuditEvent,
    AuditOutcome,
    AuditResource,
)
from app.domain.audit.audit_repository import AuditRepository
from app.models.identity import AuditEventRecord


class SqlAlchemyAuditRepository(AuditRepository):
    """The default ``AuditRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: AuditEvent) -> AuditEvent:
        record = AuditEventRecord(
            occurred_at=event.occurred_at,
            action=event.action.value,
            outcome=event.outcome.value,
            actor_authenticated=event.actor.authenticated,
            actor_user_id=event.actor.user_id,
            actor_session_id=event.actor.session_id,
            actor_description=event.actor.description[:300],
            resource_type=event.resource.resource_type,
            resource_id=event.resource.resource_id,
            detail=None if event.detail is None else event.detail[:500],
        )

        self._session.add(record)
        self._session.commit()

        return _to_domain(record)

    def list_recent(
        self,
        *,
        limit: int,
        action: AuditAction | None = None,
        user_id: int | None = None,
    ) -> tuple[AuditEvent, ...]:
        statement = select(AuditEventRecord)

        if action is not None:
            statement = statement.where(
                AuditEventRecord.action == action.value
            )

        if user_id is not None:
            statement = statement.where(
                AuditEventRecord.actor_user_id == user_id
            )

        # `id` breaks the tie. Two events recorded in the same clock tick
        # would otherwise come back in an order the database chose, and a
        # trail whose order changes between reads is hard to trust.
        records = self._session.scalars(
            statement.order_by(
                AuditEventRecord.occurred_at.desc(),
                AuditEventRecord.id.desc(),
            ).limit(limit)
        ).all()

        return tuple(_to_domain(record) for record in records)


def _to_domain(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        event_id=record.id,
        occurred_at=record.occurred_at,
        action=AuditAction(record.action),
        outcome=AuditOutcome(record.outcome),
        actor=AuditActor(
            authenticated=record.actor_authenticated,
            user_id=record.actor_user_id,
            session_id=record.actor_session_id,
            description=record.actor_description,
        ),
        resource=AuditResource(
            resource_type=record.resource_type,
            resource_id=record.resource_id,
        ),
        detail=record.detail,
    )
