from __future__ import annotations


class PromptBuilderError(Exception):
    """Base class for every exception raised by the Prompt Builder
    bounded context."""


class InvalidProjectIdError(PromptBuilderError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class ProjectIdMismatchError(PromptBuilderError):
    """The path's ``project_id`` and the supplied ``ContextPackage``'s
    own ``project_id`` disagree - the same "path is authoritative, but
    a body that names a different project is a real inconsistency, not
    silently ignored" discipline every governed router in this
    pipeline follows."""

    def __init__(self, path_project_id: int, context_package_project_id: int) -> None:
        self.path_project_id = path_project_id
        self.context_package_project_id = context_package_project_id

        super().__init__(
            f"Project id mismatch: path project id {path_project_id} "
            "does not match the supplied ContextPackage's project id "
            f"{context_package_project_id}."
        )
