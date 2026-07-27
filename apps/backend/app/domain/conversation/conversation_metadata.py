"""
Builds ``ConversationMetadata`` and ``ConversationVersion``. ``now``/
``created_at`` are always supplied by the caller rather than read from
the wall clock here, keeping every builder operation deterministic and
reproducible (CLAUDE.md SS16) given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.conversation.conversation_models import (
    ConversationMetadata,
    ConversationPolicy,
    ConversationVersion,
)
from app.domain.conversation.conversation_policy import (
    CONVERSATION_PACKAGE_VERSION,
)


def build_metadata(
    *,
    conversation_version: str,
    policy: ConversationPolicy,
    project_id: int,
    session_id: str,
    created_by: str | None,
    created_at: datetime,
    updated_at: datetime,
) -> ConversationMetadata:
    return ConversationMetadata(
        conversation_version=conversation_version,
        conversation_policy_version=policy.version,
        project_id=project_id,
        session_id=session_id,
        created_by=created_by,
        created_at=created_at,
        updated_at=updated_at,
        package_version=CONVERSATION_PACKAGE_VERSION,
    )


def build_version(
    *, conversation_version: str, policy: ConversationPolicy
) -> ConversationVersion:
    return ConversationVersion(
        conversation_version=conversation_version,
        conversation_policy_version=policy.version,
        package_version=CONVERSATION_PACKAGE_VERSION,
    )
