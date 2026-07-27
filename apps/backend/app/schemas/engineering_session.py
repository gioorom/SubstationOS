from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSession,
    EngineeringSessionConfiguration,
    EngineeringSessionEvent,
    EngineeringSessionEventType,
    EngineeringSessionId,
    EngineeringSessionMetadata,
    EngineeringSessionPolicy,
    EngineeringSessionState,
    EngineeringSessionStatistics,
    EngineeringSessionStatus,
    EngineeringSessionTimeline,
    EngineeringSessionVersion,
)
from app.schemas.engineering_response import (
    EngineeringResponseRead,
    engineering_response_from_schema,
)

# --- Request -----------------------------------------------------------


class EngineeringSessionCreateRequestBody(BaseModel):
    """
    A session-creation request. ``project_id`` is deliberately absent -
    the path's own ``{project_id}`` is authoritative. ``session_id`` is
    deliberately absent too - the composition root (the router)
    generates a fresh identifier per real session, since the domain
    layer itself never generates identifiers (CLAUDE.md SS15, "Pure
    domain").
    """

    title: str | None = None
    notes: str | None = None
    created_by: str | None = None


class EngineeringSessionStateRead(BaseModel):
    status: EngineeringSessionStatus
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionEventRead(BaseModel):
    event_type: EngineeringSessionEventType
    sequence: int
    occurred_at: datetime
    description: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionTimelineRead(BaseModel):
    events: list[EngineeringSessionEventRead]

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionPolicyRead(BaseModel):
    version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionConfigurationRead(BaseModel):
    session_policy: EngineeringSessionPolicyRead
    engineering_session_version: str
    title: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionMetadataRead(BaseModel):
    engineering_session_version: str
    session_policy_version: str
    project_id: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionStatisticsRead(BaseModel):
    response_count: int
    timeline_event_count: int
    session_duration_seconds: float
    last_activity_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionVersionRead(BaseModel):
    engineering_session_version: str
    session_policy_version: str
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionRead(BaseModel):
    """
    The root aggregate's own API response shape - and, per Milestone
    19's "no persistence" instruction, also the shape every subsequent
    ``append-response``/``change-state``/``update-configuration`` call
    accepts back as its own input, since nothing is held in memory
    between requests.
    """

    session_id: str
    project_id: int
    state: EngineeringSessionStateRead
    engineering_responses: list[EngineeringResponseRead]
    configuration: EngineeringSessionConfigurationRead
    timeline: EngineeringSessionTimelineRead
    metadata: EngineeringSessionMetadataRead
    statistics: EngineeringSessionStatisticsRead
    version: EngineeringSessionVersionRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, session: EngineeringSession) -> "EngineeringSessionRead":
        return cls(
            session_id=session.session_id.value,
            project_id=session.project_id,
            state=EngineeringSessionStateRead.model_validate(session.state),
            engineering_responses=[
                EngineeringResponseRead.model_validate(response)
                for response in session.engineering_responses
            ],
            configuration=EngineeringSessionConfigurationRead.model_validate(
                session.configuration
            ),
            timeline=EngineeringSessionTimelineRead.model_validate(session.timeline),
            metadata=EngineeringSessionMetadataRead.model_validate(session.metadata),
            statistics=EngineeringSessionStatisticsRead.model_validate(
                session.statistics
            ),
            version=EngineeringSessionVersionRead.model_validate(session.version),
        )


class EngineeringSessionValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class EngineeringSessionBuilderResultRead(BaseModel):
    project_id: int
    session: EngineeringSessionRead
    validation: EngineeringSessionValidationResultRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "EngineeringSessionBuilderResultRead":
        return cls(
            project_id=result.project_id,
            session=EngineeringSessionRead.from_domain(result.session),
            validation=EngineeringSessionValidationResultRead.model_validate(
                result.validation
            ),
        )


class EngineeringSessionAppendResponseRequestBody(BaseModel):
    session: EngineeringSessionRead
    response: EngineeringResponseRead


class EngineeringSessionChangeStateRequestBody(BaseModel):
    session: EngineeringSessionRead
    target_status: EngineeringSessionStatus


class EngineeringSessionUpdateConfigurationRequestBody(BaseModel):
    session: EngineeringSessionRead
    title: str | None = None
    notes: str | None = None


# --- Reconstruction ------------------------------------------------------


def _event_from_read(model: EngineeringSessionEventRead) -> EngineeringSessionEvent:
    return EngineeringSessionEvent(
        event_type=model.event_type,
        sequence=model.sequence,
        occurred_at=model.occurred_at,
        description=model.description,
    )


def engineering_session_from_schema(
    model: EngineeringSessionRead,
) -> EngineeringSession:
    return EngineeringSession(
        session_id=EngineeringSessionId(value=model.session_id),
        project_id=model.project_id,
        state=EngineeringSessionState(
            status=model.state.status, changed_at=model.state.changed_at
        ),
        engineering_responses=tuple(
            engineering_response_from_schema(response)
            for response in model.engineering_responses
        ),
        configuration=EngineeringSessionConfiguration(
            session_policy=EngineeringSessionPolicy(
                version=model.configuration.session_policy.version
            ),
            engineering_session_version=(
                model.configuration.engineering_session_version
            ),
            title=model.configuration.title,
            notes=model.configuration.notes,
        ),
        timeline=EngineeringSessionTimeline(
            events=tuple(
                _event_from_read(event) for event in model.timeline.events
            )
        ),
        metadata=EngineeringSessionMetadata(
            engineering_session_version=(
                model.metadata.engineering_session_version
            ),
            session_policy_version=model.metadata.session_policy_version,
            project_id=model.metadata.project_id,
            created_by=model.metadata.created_by,
            created_at=model.metadata.created_at,
            updated_at=model.metadata.updated_at,
            package_version=model.metadata.package_version,
        ),
        statistics=EngineeringSessionStatistics(
            response_count=model.statistics.response_count,
            timeline_event_count=model.statistics.timeline_event_count,
            session_duration_seconds=model.statistics.session_duration_seconds,
            last_activity_at=model.statistics.last_activity_at,
        ),
        version=EngineeringSessionVersion(
            engineering_session_version=(
                model.version.engineering_session_version
            ),
            session_policy_version=model.version.session_policy_version,
            package_version=model.version.package_version,
        ),
    )


__all__ = [
    "EngineeringSessionCreateRequestBody",
    "EngineeringSessionAppendResponseRequestBody",
    "EngineeringSessionChangeStateRequestBody",
    "EngineeringSessionUpdateConfigurationRequestBody",
    "EngineeringSessionRead",
    "EngineeringSessionBuilderResultRead",
    "engineering_session_from_schema",
]
