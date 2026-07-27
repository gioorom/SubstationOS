from __future__ import annotations

from app.domain.conversation.conversation_models import (
    ConversationStatus,
    ConversationTurnStatus,
)


class ConversationError(Exception):
    """Base class for every exception raised by the Conversation
    bounded context."""


class InvalidProjectIdError(ConversationError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class InvalidConversationIdError(ConversationError):
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

        super().__init__(f"Invalid conversation id: '{conversation_id!r}'.")


class InvalidSessionIdError(ConversationError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

        super().__init__(f"Invalid session id: '{session_id!r}'.")


class InvalidTurnIdError(ConversationError):
    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id

        super().__init__(f"Invalid turn id: '{turn_id!r}'.")


class ProjectIdMismatchError(ConversationError):
    """An ``EngineeringResponse`` being attached to a turn belongs to a
    different project than the conversation itself - the same "a body
    that names a different project is a real inconsistency, not
    silently ignored" discipline every governed context in this
    pipeline follows."""

    def __init__(
        self, conversation_project_id: int, response_project_id: int
    ) -> None:
        self.conversation_project_id = conversation_project_id
        self.response_project_id = response_project_id

        super().__init__(
            f"Project id mismatch: conversation project id "
            f"{conversation_project_id} does not match the supplied "
            f"EngineeringResponse's project id {response_project_id}."
        )


class InvalidConversationTransitionError(ConversationError):
    def __init__(
        self, current: ConversationStatus, target: ConversationStatus
    ) -> None:
        self.current = current
        self.target = target

        super().__init__(
            f"Invalid conversation status transition: '{current.value}' "
            f"-> '{target.value}'."
        )


class ConversationNotMutableError(ConversationError):
    """Raised when a caller attempts to start a turn or change status on
    a conversation whose current status is not ``ACTIVE``
    (``COMPLETED``/``ARCHIVED`` are read-only)."""

    def __init__(self, status: ConversationStatus) -> None:
        self.status = status

        super().__init__(
            f"Conversation in status '{status.value}' does not accept "
            "new turns or further status changes."
        )


class TurnAlreadyInProgressError(ConversationError):
    """Raised when starting a new turn while the conversation's most
    recent turn is still ``STARTED`` - only one turn may be open at a
    time."""

    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id

        super().__init__(
            f"Cannot start a new turn: turn '{turn_id}' is still in "
            "progress."
        )


class NoActiveTurnError(ConversationError):
    """Raised when appending a message, attaching an
    ``EngineeringResponse``, or completing a turn on a conversation with
    no currently ``STARTED`` turn."""

    def __init__(self) -> None:
        super().__init__(
            "This conversation has no turn currently in progress."
        )


class InvalidTurnTransitionError(ConversationError):
    def __init__(
        self, current: ConversationTurnStatus, target: ConversationTurnStatus
    ) -> None:
        self.current = current
        self.target = target

        super().__init__(
            f"Invalid turn status transition: '{current.value}' -> "
            f"'{target.value}'."
        )
