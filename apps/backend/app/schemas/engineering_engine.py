from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowCapability,
    WorkflowExecutionEventType,
    WorkflowStepStatus,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.schemas.engineering_response import EngineeringResponseRead

# --- Request -----------------------------------------------------------


class ComparisonOperandCriteriaBody(BaseModel):
    """One side of a comparison, exactly as
    ``/engineering-requests/prepare`` derived it. Named ``comparison_left``
    / ``comparison_right`` on the body rather than supplied as a list:
    "compare A with B" and "compare B with A" are different questions."""

    designation: str
    retrieval_limit: int = 20
    retrieval_include_neighborhood: bool = False
    retrieval_neighborhood_depth: int = 0
    retrieval_entity_type: str | None = None
    retrieval_canonical_entity_id: str | None = None
    retrieval_attribute_name: str | None = None
    retrieval_lexical_terms: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EngineeringEngineExecuteRequestBody(BaseModel):
    """
    An engine execution request. ``project_id`` is deliberately absent -
    the path's own ``{project_id}`` is authoritative.

    **Never accepts a caller-supplied workflow plan**: the server
    selects the workflow and constructs the plan. The caller supplies
    the classified intent (``engineering_intent_id``/``intent_type``,
    exactly as a prior ``/engineering-intents/classify`` call returned)
    plus the retrieval/runtime configuration the existing services
    already accept - the engine adds no configuration surface of its
    own.
    """

    engineering_session_id: str
    conversation_id: str
    turn_id: str
    request_text: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType

    retrieval_limit: int = 20
    retrieval_include_neighborhood: bool = False
    retrieval_neighborhood_depth: int = 0
    retrieval_entity_type: str | None = None
    retrieval_canonical_entity_id: str | None = None
    retrieval_attribute_name: str | None = None
    retrieval_lexical_terms: list[str] = Field(default_factory=list)

    provider_id: str | None = None
    model_identifier: str | None = None
    request_correlation_id: str | None = None

    working_memory_has_open_question: bool = False
    working_memory_active_response_count: int = 0

    comparison_left: ComparisonOperandCriteriaBody | None = None
    comparison_right: ComparisonOperandCriteriaBody | None = None


# --- Response ------------------------------------------------------------


class WorkflowSelectionRead(BaseModel):
    workflow_id: str
    workflow_type: WorkflowType
    workflow_version: str
    intent_type: EngineeringIntentType

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, selection) -> "WorkflowSelectionRead":
        return cls(
            workflow_id=selection.workflow_id.value,
            workflow_type=selection.workflow_type,
            workflow_version=selection.workflow_version,
            intent_type=selection.intent_type,
        )


class WorkflowStepRead(BaseModel):
    step_id: str
    step_type: WorkflowStepType
    ordinal: int
    required_capability: WorkflowCapability
    required_artifacts: list[WorkflowArtifactKey]
    produced_artifacts: list[WorkflowArtifactKey]
    optional: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, step) -> "WorkflowStepRead":
        return cls(
            step_id=step.step_id.value,
            step_type=step.step_type,
            ordinal=step.ordinal,
            required_capability=step.required_capability,
            required_artifacts=list(step.required_artifacts),
            produced_artifacts=list(step.produced_artifacts),
            optional=step.optional,
        )


class WorkflowPlanMetadataRead(BaseModel):
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    workflow_id: str
    workflow_type: WorkflowType
    planned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowPlanStatisticsRead(BaseModel):
    step_count: int
    required_step_count: int
    optional_step_count: int
    required_capability_count: int

    model_config = ConfigDict(from_attributes=True)


class WorkflowPlanVersionRead(BaseModel):
    engine_version: str
    workflow_version: str
    plan_policy_version: str

    model_config = ConfigDict(from_attributes=True)


class WorkflowPlanRead(BaseModel):
    plan_id: str
    workflow_id: str
    workflow_type: WorkflowType
    steps: list[WorkflowStepRead]
    required_capabilities: list[WorkflowCapability]
    metadata: WorkflowPlanMetadataRead
    statistics: WorkflowPlanStatisticsRead
    version: WorkflowPlanVersionRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, plan) -> "WorkflowPlanRead":
        return cls(
            plan_id=plan.plan_id.value,
            workflow_id=plan.workflow_id.value,
            workflow_type=plan.workflow_type,
            steps=[WorkflowStepRead.from_domain(step) for step in plan.steps],
            required_capabilities=list(plan.required_capabilities),
            metadata=WorkflowPlanMetadataRead.model_validate(plan.metadata),
            statistics=WorkflowPlanStatisticsRead.model_validate(
                plan.statistics
            ),
            version=WorkflowPlanVersionRead.model_validate(plan.version),
        )


class WorkflowStepFailureRead(BaseModel):
    code: EngineeringEngineFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class WorkflowStepResultRead(BaseModel):
    step_id: str
    step_type: WorkflowStepType
    ordinal: int
    status: WorkflowStepStatus
    produced_artifacts: list[WorkflowArtifactKey]
    started_at: datetime
    completed_at: datetime
    failure: WorkflowStepFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "WorkflowStepResultRead":
        return cls(
            step_id=result.step_id.value,
            step_type=result.step_type,
            ordinal=result.ordinal,
            status=result.status,
            produced_artifacts=list(result.produced_artifacts),
            started_at=result.started_at,
            completed_at=result.completed_at,
            failure=(
                WorkflowStepFailureRead.model_validate(result.failure)
                if result.failure is not None
                else None
            ),
        )


class WorkflowExecutionEventRead(BaseModel):
    event_type: WorkflowExecutionEventType
    sequence: int
    occurred_at: datetime
    description: str

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionTimelineRead(BaseModel):
    events: list[WorkflowExecutionEventRead]

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionStatisticsRead(BaseModel):
    planned_step_count: int
    completed_step_count: int
    failed_step_count: int
    skipped_step_count: int
    timeline_event_count: int

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionRead(BaseModel):
    execution_id: str
    plan_id: str
    status: EngineeringEngineExecutionStatus
    step_results: list[WorkflowStepResultRead]
    timeline: WorkflowExecutionTimelineRead
    statistics: WorkflowExecutionStatisticsRead
    started_at: datetime
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, execution) -> "WorkflowExecutionRead":
        return cls(
            execution_id=execution.execution_id.value,
            plan_id=execution.plan_id.value,
            status=execution.status,
            step_results=[
                WorkflowStepResultRead.from_domain(result)
                for result in execution.step_results
            ],
            timeline=WorkflowExecutionTimelineRead.model_validate(
                execution.timeline
            ),
            statistics=WorkflowExecutionStatisticsRead.model_validate(
                execution.statistics
            ),
            started_at=execution.started_at,
            completed_at=execution.completed_at,
        )


class ConversationUpdateProposalRead(BaseModel):
    conversation_id: str
    turn_id: str
    disposition: AggregateUpdateDisposition
    description: str

    model_config = ConfigDict(from_attributes=True)


class SessionUpdateProposalRead(BaseModel):
    engineering_session_id: str
    disposition: AggregateUpdateDisposition
    description: str

    model_config = ConfigDict(from_attributes=True)


class PreparedAggregateUpdatesRead(BaseModel):
    """
    Explicitly states that updates were **prepared, not applied** - the
    engine never mutates ``Conversation`` or ``EngineeringSession``
    (ADR-0020). A caller wanting them applied must do so itself through
    the existing conversation/session services.
    """

    conversation_update: ConversationUpdateProposalRead | None
    session_update: SessionUpdateProposalRead | None

    model_config = ConfigDict(from_attributes=True)


class EngineeringEngineFailureRead(BaseModel):
    code: EngineeringEngineFailureCode
    message: str
    detail: str | None
    step_id: str | None
    step_type: WorkflowStepType | None

    model_config = ConfigDict(from_attributes=True)


class EngineeringEngineExecutionMetadataRead(BaseModel):
    engine_version: str
    plan_policy_version: str
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineeringEngineValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class EngineeringEngineExecutionResultRead(BaseModel):
    """
    The engine's own auditable result - never raw runtime or provider
    output. On success it carries the ``EngineeringResponse``; on
    failure or unsupported intent it carries a typed, provider-neutral
    failure instead.
    """

    execution_id: str
    project_id: int
    status: EngineeringEngineExecutionStatus
    selection: WorkflowSelectionRead | None
    plan: WorkflowPlanRead | None
    execution: WorkflowExecutionRead | None
    engineering_response: EngineeringResponseRead | None
    prepared_updates: PreparedAggregateUpdatesRead | None
    failure: EngineeringEngineFailureRead | None
    metadata: EngineeringEngineExecutionMetadataRead
    validation: EngineeringEngineValidationResultRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "EngineeringEngineExecutionResultRead":
        return cls(
            execution_id=result.execution_id.value,
            project_id=result.project_id,
            status=result.status,
            selection=(
                WorkflowSelectionRead.from_domain(result.selection)
                if result.selection is not None
                else None
            ),
            plan=(
                WorkflowPlanRead.from_domain(result.plan)
                if result.plan is not None
                else None
            ),
            execution=(
                WorkflowExecutionRead.from_domain(result.execution)
                if result.execution is not None
                else None
            ),
            engineering_response=(
                EngineeringResponseRead.model_validate(
                    result.engineering_response
                )
                if result.engineering_response is not None
                else None
            ),
            prepared_updates=(
                PreparedAggregateUpdatesRead.model_validate(
                    result.prepared_updates
                )
                if result.prepared_updates is not None
                else None
            ),
            failure=(
                EngineeringEngineFailureRead.model_validate(result.failure)
                if result.failure is not None
                else None
            ),
            metadata=EngineeringEngineExecutionMetadataRead.model_validate(
                result.metadata
            ),
            validation=(
                EngineeringEngineValidationResultRead.model_validate(
                    result.validation
                )
                if result.validation is not None
                else None
            ),
        )


__all__ = [
    "EngineeringEngineExecuteRequestBody",
    "EngineeringEngineExecutionResultRead",
]
