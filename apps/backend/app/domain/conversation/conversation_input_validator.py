from __future__ import annotations

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)
from app.domain.conversation.conversation_exceptions import (
    InvalidConversationIdError,
    InvalidProjectIdError,
    InvalidSessionIdError,
    InvalidTurnIdError,
    ProjectIdMismatchError,
)


class ConversationInputValidator:
    """Stateless validation rules for Conversation, shared by the
    builder. Validates only structurally invalid input (a non-positive
    project id, a blank identifier, an ``EngineeringResponse`` belonging
    to a different project) - every other input (an empty conversation,
    no turns yet, no messages yet) is valid, not an error."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_conversation_id(conversation_id: str) -> None:
        if not conversation_id or not conversation_id.strip():
            raise InvalidConversationIdError(conversation_id)

    @staticmethod
    def validate_session_id(session_id: str) -> None:
        if not session_id or not session_id.strip():
            raise InvalidSessionIdError(session_id)

    @staticmethod
    def validate_turn_id(turn_id: str) -> None:
        if not turn_id or not turn_id.strip():
            raise InvalidTurnIdError(turn_id)

    @staticmethod
    def validate_response_belongs_to_project(
        project_id: int, response: EngineeringResponse
    ) -> None:
        if response.project_id != project_id:
            raise ProjectIdMismatchError(project_id, response.project_id)
