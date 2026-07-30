"""
The port the audit trail is written through.

**Append and read. There is no update and no delete**, and their absence
is the contract rather than an omission: a trail an application can edit
proves nothing, so the interface an implementer must satisfy offers no
way to try.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.audit.audit_models import AuditAction, AuditEvent


class AuditRepository(ABC):
    """Records and reads audit events."""

    @abstractmethod
    def record(self, event: AuditEvent) -> AuditEvent:
        """
        Appends one event and returns it with its assigned id.

        Implementations must commit the event independently of whatever
        transaction the audited action ran in. An action that succeeded
        and an audit row that was rolled back with an unrelated failure
        is a trail that has quietly lost an entry.
        """

        raise NotImplementedError

    @abstractmethod
    def list_recent(
        self,
        *,
        limit: int,
        action: AuditAction | None = None,
        user_id: int | None = None,
    ) -> tuple[AuditEvent, ...]:
        """
        The most recent events, newest first, bounded by ``limit``.

        The bound is mandatory rather than defaulted at the call site:
        an audit trail is the one table that only grows, and an unbounded
        read of it is a request that gets slower every day the system
        runs.
        """

        raise NotImplementedError
