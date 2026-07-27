from __future__ import annotations

from app.domain.conversation.conversation_models import Conversation
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
)
from app.domain.working_memory.working_memory_exceptions import (
    ConversationSessionMismatchError,
    InvalidProjectIdError,
    ProjectIdMismatchError,
)


class WorkingMemoryInputValidator:
    """Stateless validation rules for Working Memory, shared by the
    builder. Validates only structurally invalid input (a non-positive
    project id, a conversation naming a different project or a
    different session than the supplied EngineeringSession) - every
    other input (a conversation with no turns yet, a session with no
    responses yet) is valid, not an error."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_conversation_matches_session(
        conversation: Conversation, engineering_session: EngineeringSession
    ) -> None:
        if conversation.project_id != engineering_session.project_id:
            raise ProjectIdMismatchError(
                conversation.project_id, engineering_session.project_id
            )

        if conversation.session_id.value != engineering_session.session_id.value:
            raise ConversationSessionMismatchError(
                conversation.session_id.value,
                engineering_session.session_id.value,
            )
