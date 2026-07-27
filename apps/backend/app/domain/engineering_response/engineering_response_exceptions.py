from __future__ import annotations


class EngineeringResponseError(Exception):
    """Base class for every exception raised by the Engineering
    Response bounded context."""


class InvalidProjectIdError(EngineeringResponseError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class ProjectIdMismatchError(EngineeringResponseError):
    """The path's ``project_id`` and a supplied upstream package's own
    ``project_id`` disagree - the same "path is authoritative, but a
    body that names a different project is a real inconsistency, not
    silently ignored" discipline every governed router in this
    pipeline follows."""

    def __init__(
        self, path_project_id: int, other_project_id: int, source_name: str
    ) -> None:
        self.path_project_id = path_project_id
        self.other_project_id = other_project_id
        self.source_name = source_name

        super().__init__(
            f"Project id mismatch: path project id {path_project_id} "
            f"does not match the supplied {source_name}'s project id "
            f"{other_project_id}."
        )
