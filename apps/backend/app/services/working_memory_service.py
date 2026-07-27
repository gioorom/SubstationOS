"""
Application service for Working Memory (EPIC 5, Milestone 21). Thin
orchestration over the pure domain builder
(``working_memory_builder.py``) - like Conversation and Engineering
Session's own services, this needs no application-layer translation
seam, because Working Memory's inputs (``Conversation``,
``EngineeringSession``) are already domain types. Performs no
persistence and no I/O of any kind.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_models import Conversation
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
)
from app.domain.working_memory.working_memory_builder import (
    build_working_memory,
    rebuild_working_memory,
)
from app.domain.working_memory.working_memory_models import (
    WorkingMemoryBuilderResult,
)


def build(
    *,
    conversation: Conversation,
    engineering_session: EngineeringSession,
    now: datetime,
) -> WorkingMemoryBuilderResult:
    return build_working_memory(
        conversation=conversation, engineering_session=engineering_session, now=now
    )


def rebuild(
    *,
    conversation: Conversation,
    engineering_session: EngineeringSession,
    now: datetime,
) -> WorkingMemoryBuilderResult:
    return rebuild_working_memory(
        conversation=conversation, engineering_session=engineering_session, now=now
    )
