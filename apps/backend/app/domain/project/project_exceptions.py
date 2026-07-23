from __future__ import annotations

from app.domain.project.project_lifecycle import ProjectLifecycleState


class ProjectError(Exception):
    """
    Base class for every exception raised by the Project bounded context.
    """


class InvalidProjectNameError(ProjectError):
    """
    Project name is missing, blank, or otherwise fails validation.
    """

    def __init__(self, name: str) -> None:
        self.name = name

        super().__init__(
            f"Invalid project name: '{name}'. "
            "A project name is required."
        )


class InvalidProjectCodeError(ProjectError):
    """
    Project code is missing, blank, or otherwise fails validation.
    """

    def __init__(self, code: str) -> None:
        self.code = code

        super().__init__(
            f"Invalid project code: '{code}'. "
            "A project code is required."
        )


class DuplicateProjectCodeError(ProjectError):
    """
    A project with this code already exists.
    """

    def __init__(self, code: str) -> None:
        self.code = code

        super().__init__(
            f"Project code '{code}' already exists."
        )


class ProjectNotFoundError(ProjectError):
    """
    A project was requested by id or code but does not exist.
    """

    def __init__(self, identifier: object) -> None:
        self.identifier = identifier

        super().__init__(
            f"Project '{identifier}' not found."
        )


class InvalidProjectTransitionError(ProjectError):
    """
    An attempted lifecycle transition is not allowed from the project's
    current state.
    """

    def __init__(
        self,
        current_state: ProjectLifecycleState,
        target_state: ProjectLifecycleState,
    ) -> None:
        self.current_state = current_state
        self.target_state = target_state

        super().__init__(
            f"Cannot transition project from "
            f"'{current_state.value}' to '{target_state.value}'."
        )


class ProjectNotMutableError(ProjectError):
    """
    An attempted write (metadata update, document upload) targets a
    project whose lifecycle state is read-only (Archived or Deleted).
    """

    def __init__(
        self,
        code: str,
        lifecycle_state: ProjectLifecycleState,
    ) -> None:
        self.code = code
        self.lifecycle_state = lifecycle_state

        super().__init__(
            f"Project '{code}' is '{lifecycle_state.value}' and is "
            "read-only."
        )
