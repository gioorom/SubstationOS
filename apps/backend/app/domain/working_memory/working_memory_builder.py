"""
Orchestrates the full Working Memory Builder pipeline (Milestone 21):

    Conversation + EngineeringSession
            |
       Composition          (working_memory_composition.py)
            |
       Statistics           (working_memory_statistics.py)
            |
       Metadata/Versioning  (working_memory_metadata.py)
            |
       Validation           (working_memory_validation.py)
       WorkingMemoryBuilderResult

Pure and deterministic: given the same ``Conversation``/
``EngineeringSession`` and the same ``now``, always produces the same
``WorkingMemoryBuilderResult``. No AI usage, no summarization, no
semantic interpretation, no persistence.

"Rebuild" is not a different computation from "build" - Working Memory
is never persisted, so there is nothing to update in place; rebuilding
means discarding whatever ``WorkingMemory`` existed before and running
this exact same deterministic function again. ``rebuild_working_memory``
is therefore a thin alias, kept as a separate name only because the
milestone names it as a separate capability (see ADR-0018).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_models import Conversation
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
)
from app.domain.working_memory.working_memory_composition import (
    compose_working_memory_entries,
)
from app.domain.working_memory.working_memory_input_validator import (
    WorkingMemoryInputValidator,
)
from app.domain.working_memory.working_memory_metadata import (
    build_metadata,
    build_version,
)
from app.domain.working_memory.working_memory_models import (
    WorkingMemory,
    WorkingMemoryBuilderResult,
    WorkingMemoryId,
)
from app.domain.working_memory.working_memory_statistics import build_statistics
from app.domain.working_memory.working_memory_validation import (
    validate_working_memory,
)


def build_working_memory(
    *,
    conversation: Conversation,
    engineering_session: EngineeringSession,
    now: datetime,
) -> WorkingMemoryBuilderResult:
    WorkingMemoryInputValidator.validate_project_id(conversation.project_id)
    WorkingMemoryInputValidator.validate_conversation_matches_session(
        conversation, engineering_session
    )

    entries = compose_working_memory_entries(
        conversation, engineering_session, now=now
    )
    statistics = build_statistics(entries)
    metadata = build_metadata(
        project_id=conversation.project_id,
        conversation_id=conversation.conversation_id.value,
        session_id=conversation.session_id.value,
        built_at=now,
    )
    version = build_version()

    working_memory = WorkingMemory(
        working_memory_id=WorkingMemoryId(
            value=f"{conversation.conversation_id.value}:working-memory"
        ),
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        entries=entries,
        metadata=metadata,
        statistics=statistics,
        version=version,
    )

    validation = validate_working_memory(working_memory)

    return WorkingMemoryBuilderResult(
        project_id=conversation.project_id,
        working_memory=working_memory,
        validation=validation,
    )


def rebuild_working_memory(
    *,
    conversation: Conversation,
    engineering_session: EngineeringSession,
    now: datetime,
) -> WorkingMemoryBuilderResult:
    return build_working_memory(
        conversation=conversation, engineering_session=engineering_session, now=now
    )


class WorkingMemoryBuilder:
    """A thin, named façade over the module-level builder functions -
    kept for the same reason every sibling bounded context's own
    builder class is."""

    @staticmethod
    def build(
        *,
        conversation: Conversation,
        engineering_session: EngineeringSession,
        now: datetime,
    ) -> WorkingMemoryBuilderResult:
        return build_working_memory(
            conversation=conversation,
            engineering_session=engineering_session,
            now=now,
        )

    @staticmethod
    def rebuild(
        *,
        conversation: Conversation,
        engineering_session: EngineeringSession,
        now: datetime,
    ) -> WorkingMemoryBuilderResult:
        return rebuild_working_memory(
            conversation=conversation,
            engineering_session=engineering_session,
            now=now,
        )
