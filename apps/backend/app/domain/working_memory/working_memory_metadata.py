"""
Builds ``WorkingMemoryMetadata`` and ``WorkingMemoryVersion``. ``now``
is always supplied by the caller rather than read from the wall clock
here, keeping building deterministic and reproducible (CLAUDE.md SS16)
given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.working_memory.working_memory_models import (
    WorkingMemoryMetadata,
    WorkingMemoryVersion,
)
from app.domain.working_memory.working_memory_policy import (
    WORKING_MEMORY_PACKAGE_VERSION,
    WORKING_MEMORY_POLICY_VERSION,
    WORKING_MEMORY_VERSION,
)


def build_metadata(
    *,
    project_id: int,
    conversation_id: str,
    session_id: str,
    built_at: datetime,
) -> WorkingMemoryMetadata:
    return WorkingMemoryMetadata(
        working_memory_version=WORKING_MEMORY_VERSION,
        working_memory_policy_version=WORKING_MEMORY_POLICY_VERSION,
        project_id=project_id,
        conversation_id=conversation_id,
        session_id=session_id,
        built_at=built_at,
        package_version=WORKING_MEMORY_PACKAGE_VERSION,
    )


def build_version() -> WorkingMemoryVersion:
    return WorkingMemoryVersion(
        working_memory_version=WORKING_MEMORY_VERSION,
        working_memory_policy_version=WORKING_MEMORY_POLICY_VERSION,
        package_version=WORKING_MEMORY_PACKAGE_VERSION,
    )
