from __future__ import annotations

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.engineering_session.engineering_session_exceptions import (
    InvalidProjectIdError,
    InvalidSessionIdError,
    ProjectIdMismatchError,
)


class EngineeringSessionInputValidator:
    """Stateless validation rules for Engineering Session, shared by
    ``engineering_session_builder.py``. Validates only structurally
    invalid input (a non-positive project id, a blank session id, an
    ``EngineeringResponse`` belonging to a different project) - every
    other input (an empty session, no responses yet, no timeline beyond
    creation) is valid, not an error."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_session_id(session_id: str) -> None:
        if not session_id or not session_id.strip():
            raise InvalidSessionIdError(session_id)

    @staticmethod
    def validate_response_belongs_to_project(
        project_id: int, response: EngineeringResponse
    ) -> None:
        if response.project_id != project_id:
            raise ProjectIdMismatchError(project_id, response.project_id)
