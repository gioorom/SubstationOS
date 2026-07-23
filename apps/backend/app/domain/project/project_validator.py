from __future__ import annotations

from app.domain.project.project_exceptions import (
    InvalidProjectCodeError,
    InvalidProjectNameError,
)


class ProjectValidator:
    """
    Stateless validation rules for Project metadata, shared by the
    factory (at creation) and the service layer (at metadata update).
    """

    @staticmethod
    def validate_name(name: str) -> None:
        if not name or not name.strip():
            raise InvalidProjectNameError(name)

    @staticmethod
    def validate_code(code: str) -> None:
        if not code or not code.strip():
            raise InvalidProjectCodeError(code)
