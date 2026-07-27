from __future__ import annotations


class WorkingMemoryError(Exception):
    """Base class for every exception raised by the Working Memory
    bounded context."""


class InvalidProjectIdError(WorkingMemoryError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class ProjectIdMismatchError(WorkingMemoryError):
    """The supplied ``Conversation`` and ``EngineeringSession`` name
    different projects - a real inconsistency, never silently ignored."""

    def __init__(self, conversation_project_id: int, session_project_id: int) -> None:
        self.conversation_project_id = conversation_project_id
        self.session_project_id = session_project_id

        super().__init__(
            f"Project id mismatch: conversation project id "
            f"{conversation_project_id} does not match the supplied "
            f"EngineeringSession's project id {session_project_id}."
        )


class ConversationSessionMismatchError(WorkingMemoryError):
    """The supplied ``Conversation`` does not belong to the supplied
    ``EngineeringSession``."""

    def __init__(
        self, conversation_session_id: str, engineering_session_id: str
    ) -> None:
        self.conversation_session_id = conversation_session_id
        self.engineering_session_id = engineering_session_id

        super().__init__(
            f"Session mismatch: conversation names session "
            f"'{conversation_session_id}', but the supplied "
            f"EngineeringSession is '{engineering_session_id}'."
        )
