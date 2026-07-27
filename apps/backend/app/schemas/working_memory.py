from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.working_memory.working_memory_models import (
    WorkingMemoryEntryType,
    WorkingMemoryLifetime,
    WorkingMemoryPriority,
    WorkingMemorySource,
)
from app.schemas.engineering_response import EngineeringResponseRead
from app.schemas.engineering_session import (
    EngineeringSessionRead,
    engineering_session_from_schema,
)
from app.schemas.conversation import ConversationRead, conversation_from_schema

# --- Request -----------------------------------------------------------


class WorkingMemoryBuildRequestBody(BaseModel):
    """
    A Working Memory build/rebuild request. ``project_id`` is
    deliberately absent - the path's own ``{project_id}`` is
    authoritative. ``conversation``/``engineering_session`` are exactly
    the objects a prior ``/conversation``/``/engineering-session`` call
    returned - this endpoint never calls Conversation or Engineering
    Session itself, and performs no AI invocation of its own.
    """

    conversation: ConversationRead
    engineering_session: EngineeringSessionRead


# --- Response ------------------------------------------------------------


class WorkingMemoryEntryRead(BaseModel):
    entry_id: str
    entry_type: WorkingMemoryEntryType
    content: str
    source: WorkingMemorySource
    priority: WorkingMemoryPriority
    lifetime: WorkingMemoryLifetime
    sequence: int
    created_at: datetime
    engineering_response: EngineeringResponseRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, entry) -> "WorkingMemoryEntryRead":
        return cls(
            entry_id=entry.entry_id,
            entry_type=entry.entry_type,
            content=entry.content,
            source=entry.source,
            priority=entry.priority,
            lifetime=entry.lifetime,
            sequence=entry.sequence,
            created_at=entry.created_at,
            engineering_response=(
                EngineeringResponseRead.model_validate(entry.engineering_response)
                if entry.engineering_response is not None
                else None
            ),
        )


class WorkingMemoryMetadataRead(BaseModel):
    working_memory_version: str
    working_memory_policy_version: str
    project_id: int
    conversation_id: str
    session_id: str
    built_at: datetime
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class WorkingMemoryStatisticsRead(BaseModel):
    entry_count: int
    open_question_count: int
    assumption_count: int
    constraint_count: int
    active_reference_count: int
    recent_engineering_response_count: int

    model_config = ConfigDict(from_attributes=True)


class WorkingMemoryVersionRead(BaseModel):
    working_memory_version: str
    working_memory_policy_version: str
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class WorkingMemoryRead(BaseModel):
    """
    Deliberately exposes only strongly typed entries and supporting
    objects - no provider SDK response, no raw message text
    interpretation, no persisted state of any kind. Always fully
    derivable from a ``Conversation``/``EngineeringSession`` pair.
    """

    working_memory_id: str
    conversation_id: str
    session_id: str
    project_id: int
    entries: list[WorkingMemoryEntryRead]
    metadata: WorkingMemoryMetadataRead
    statistics: WorkingMemoryStatisticsRead
    version: WorkingMemoryVersionRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, working_memory) -> "WorkingMemoryRead":
        return cls(
            working_memory_id=working_memory.working_memory_id.value,
            conversation_id=working_memory.conversation_id.value,
            session_id=working_memory.session_id.value,
            project_id=working_memory.project_id,
            entries=[
                WorkingMemoryEntryRead.from_domain(entry)
                for entry in working_memory.entries
            ],
            metadata=WorkingMemoryMetadataRead.model_validate(
                working_memory.metadata
            ),
            statistics=WorkingMemoryStatisticsRead.model_validate(
                working_memory.statistics
            ),
            version=WorkingMemoryVersionRead.model_validate(working_memory.version),
        )


class WorkingMemoryValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class WorkingMemoryBuilderResultRead(BaseModel):
    project_id: int
    working_memory: WorkingMemoryRead
    validation: WorkingMemoryValidationResultRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "WorkingMemoryBuilderResultRead":
        return cls(
            project_id=result.project_id,
            working_memory=WorkingMemoryRead.from_domain(result.working_memory),
            validation=WorkingMemoryValidationResultRead.model_validate(
                result.validation
            ),
        )


__all__ = [
    "WorkingMemoryBuildRequestBody",
    "WorkingMemoryBuilderResultRead",
    "conversation_from_schema",
    "engineering_session_from_schema",
]
