from __future__ import annotations

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionStatus,
)


class EngineeringSessionError(Exception):
    """Base class for every exception raised by the Engineering
    Session bounded context."""


class InvalidProjectIdError(EngineeringSessionError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class InvalidSessionIdError(EngineeringSessionError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

        super().__init__(f"Invalid session id: '{session_id!r}'.")


class ProjectIdMismatchError(EngineeringSessionError):
    """An ``EngineeringResponse`` being appended belongs to a different
    project than the session itself - the same "a body that names a
    different project is a real inconsistency, not silently ignored"
    discipline every governed context in this pipeline follows."""

    def __init__(self, session_project_id: int, response_project_id: int) -> None:
        self.session_project_id = session_project_id
        self.response_project_id = response_project_id

        super().__init__(
            f"Project id mismatch: session project id "
            f"{session_project_id} does not match the supplied "
            f"EngineeringResponse's project id {response_project_id}."
        )


class InvalidSessionTransitionError(EngineeringSessionError):
    def __init__(
        self,
        current: EngineeringSessionStatus,
        target: EngineeringSessionStatus,
    ) -> None:
        self.current = current
        self.target = target

        super().__init__(
            f"Invalid session state transition: '{current.value}' -> "
            f"'{target.value}'."
        )


class SessionNotMutableError(EngineeringSessionError):
    """Raised when a caller attempts to append an ``EngineeringResponse``
    or update configuration on a session whose current status is not in
    ``MUTABLE_STATUSES`` (``COMPLETED``/``ARCHIVED`` are read-only)."""

    def __init__(self, status: EngineeringSessionStatus) -> None:
        self.status = status

        super().__init__(
            f"Session in status '{status.value}' does not accept new "
            "engineering responses or configuration changes."
        )
