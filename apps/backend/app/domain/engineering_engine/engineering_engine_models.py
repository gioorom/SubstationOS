"""
Value objects for the Engineering Engine (EPIC 5, Milestone 23A).

The Engineering Engine is an **application coordination capability**,
not a new knowledge bounded context and not an autonomous agent, LLM
brain, reasoning engine, chatbot, or multi-agent orchestrator. It
coordinates deterministic workflow structure: selecting a registered
workflow for a classified request, building an explicit immutable
``WorkflowPlan``, executing that plan through registered step handlers,
and returning an auditable ``EngineeringEngineExecutionResult``.

This module holds only the **immutable planning and execution-result
domain models**. Orchestration, the workflow registry, step execution,
and adapters to existing services live in
``app/services/engineering_engine/**`` - this module imports no router,
schema, provider SDK, persistence adapter, or application service.

Milestone 23A implements exactly one workflow:
``EngineeringIntentType.KNOWLEDGE_QUERY``. Every other intent type
yields an explicit ``UNSUPPORTED`` result - never a silent reroute
through the knowledge-query workflow, and never an LLM fallback (see
``docs/architecture/adr/0020-engineering-engine-foundation.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
)


class WorkflowType(str, Enum):
    """The kind of engineering work a registered workflow performs.
    Deliberately one value in Milestone 23A - Milestone 23B adds more
    by registering new workflows, never by editing the engine core."""

    KNOWLEDGE_QUERY = "knowledge_query"


class WorkflowStepType(str, Enum):
    """
    The step taxonomy, derived from the *real* pipeline this engine
    coordinates - never speculative reserved values.

    Note there is no separate ``EXECUTE_GRAPH_QUERY``: Graph Query is
    already an internal dependency of Structured Retrieval (which reads
    through ``GraphQueryRepository``), so modelling it as its own engine
    step would duplicate it artificially.
    """

    VALIDATE_EXECUTION_REQUEST = "validate_execution_request"
    BUILD_RETRIEVAL_REQUEST = "build_retrieval_request"
    EXECUTE_RETRIEVAL = "execute_retrieval"
    BUILD_CONTEXT = "build_context"
    BUILD_PROMPT = "build_prompt"
    INVOKE_LLM_RUNTIME = "invoke_llm_runtime"
    BUILD_ENGINEERING_RESPONSE = "build_engineering_response"
    VALIDATE_ENGINEERING_RESPONSE = "validate_engineering_response"
    PREPARE_CONVERSATION_UPDATE = "prepare_conversation_update"
    PREPARE_SESSION_UPDATE = "prepare_session_update"


class WorkflowArtifactKey(str, Enum):
    """
    Every typed intermediate artifact a step may require or produce.
    The engine domain knows only these *keys*; the concrete artifact
    types live in the application layer's execution context, keeping
    this module free of any dependency on Structured Retrieval, Context
    Builder, Prompt Builder, or the LLM Runtime.
    """

    EXECUTION_REQUEST = "execution_request"
    RETRIEVAL_REQUEST = "retrieval_request"
    RETRIEVAL_RESULT = "retrieval_result"
    CONTEXT_PACKAGE = "context_package"
    PROMPT_PACKAGE = "prompt_package"
    LLM_RESPONSE_ENVELOPE = "llm_response_envelope"
    ENGINEERING_RESPONSE = "engineering_response"
    ENGINEERING_RESPONSE_VALIDATION = "engineering_response_validation"
    CONVERSATION_UPDATE_PROPOSAL = "conversation_update_proposal"
    SESSION_UPDATE_PROPOSAL = "session_update_proposal"


class WorkflowCapability(str, Enum):
    """A capability a step requires from the composed engine. The
    registry checks every plan's required capabilities against the
    registered step handlers *before* execution begins, so a missing
    dependency fails at validation rather than mid-execution."""

    REQUEST_VALIDATION = "request_validation"
    STRUCTURED_RETRIEVAL = "structured_retrieval"
    CONTEXT_BUILDING = "context_building"
    PROMPT_BUILDING = "prompt_building"
    LLM_RUNTIME_INVOCATION = "llm_runtime_invocation"
    ENGINEERING_RESPONSE_BUILDING = "engineering_response_building"
    AGGREGATE_UPDATE_PREPARATION = "aggregate_update_preparation"


class EngineeringEngineExecutionStatus(str, Enum):
    """Only statuses genuinely supported in Milestone 23A. Cancellation
    is deliberately absent - it is not implemented, so representing it
    would be a false promise."""

    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EngineeringEngineFailureCode(str, Enum):
    """A closed, provider-neutral failure taxonomy. A raw provider
    exception is never exposed through the engine domain - the
    application boundary maps it to one of these codes and preserves a
    safe, already-extracted detail string."""

    INVALID_EXECUTION_REQUEST = "invalid_execution_request"
    UNSUPPORTED_INTENT = "unsupported_intent"
    WORKFLOW_NOT_REGISTERED = "workflow_not_registered"
    INVALID_WORKFLOW_PLAN = "invalid_workflow_plan"
    STEP_HANDLER_NOT_REGISTERED = "step_handler_not_registered"
    MISSING_REQUIRED_ARTIFACT = "missing_required_artifact"
    RETRIEVAL_FAILURE = "retrieval_failure"
    CONTEXT_BUILD_FAILURE = "context_build_failure"
    PROMPT_BUILD_FAILURE = "prompt_build_failure"
    RUNTIME_FAILURE = "runtime_failure"
    RESPONSE_BUILD_FAILURE = "response_build_failure"
    RESPONSE_VALIDATION_FAILURE = "response_validation_failure"
    AGGREGATE_UPDATE_FAILURE = "aggregate_update_failure"
    INTERNAL_EXECUTION_ERROR = "internal_execution_error"


class WorkflowExecutionEventType(str, Enum):
    EXECUTION_CREATED = "execution_created"
    WORKFLOW_SELECTED = "workflow_selected"
    PLAN_BUILT = "plan_built"
    PLAN_VALIDATED = "plan_validated"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"


class AggregateUpdateDisposition(str, Enum):
    """
    How an aggregate update was handled. Milestone 23A always uses
    ``PREPARED``: the engine returns an explicit, immutable update
    *proposal* a higher application service may apply - it never
    mutates ``Conversation`` or ``EngineeringSession`` itself. The
    ``APPLIED`` value exists so a future milestone that genuinely
    applies updates can say so honestly, and so the execution result can
    never imply an update occurred when only a proposal was returned.
    """

    PREPARED = "prepared"
    APPLIED = "applied"
    NOT_APPLICABLE = "not_applicable"


# --- Identity -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkflowId:
    value: str


@dataclass(frozen=True, slots=True)
class WorkflowPlanId:
    """Deterministically derived from
    ``project_id:conversation_id:turn_id:engineering_intent_id:workflow_id:workflow_version``
    - never random. Identical inputs under the same registry and
    definition versions always produce the same plan identity."""

    value: str


@dataclass(frozen=True, slots=True)
class WorkflowStepId:
    """Deterministically derived from
    ``{plan_id}:{ordinal}:{step_type}`` - never random."""

    value: str


@dataclass(frozen=True, slots=True)
class EngineeringEngineExecutionId:
    """Deterministically derived from the plan identity, so re-running
    the same request under the same versions is recognizably the same
    execution - see ADR-0020 on planning determinism versus runtime
    nondeterminism."""

    value: str


# --- Failure ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EngineeringEngineFailure:
    """
    A typed, stage-specific, provider-neutral failure. ``detail`` is a
    safe, already-extracted message - never a raw provider exception,
    never a stack trace. ``step_id``/``step_type`` are populated only
    when the failure occurred inside a step.
    """

    code: EngineeringEngineFailureCode
    message: str
    detail: str | None = None
    step_id: str | None = None
    step_type: WorkflowStepType | None = None


@dataclass(frozen=True, slots=True)
class WorkflowStepFailure:
    code: EngineeringEngineFailureCode
    message: str
    detail: str | None = None


# --- Workflow definition and plan ------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkflowStepDefinition:
    """
    One declarative step in a ``WorkflowDefinition``. Purely
    descriptive: it never invokes a service. The planner turns
    definitions plus an execution request into concrete
    ``WorkflowStep``s.
    """

    step_type: WorkflowStepType
    required_capability: WorkflowCapability
    required_artifacts: tuple[WorkflowArtifactKey, ...] = ()
    produced_artifacts: tuple[WorkflowArtifactKey, ...] = ()
    optional: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """A declarative description of one registered workflow. Contains
    no executable logic - the registry stores it, the planner reads it,
    and step handlers (application layer) do the actual work."""

    workflow_id: WorkflowId
    workflow_type: WorkflowType
    supported_intent_type: EngineeringIntentType
    workflow_version: str
    steps: tuple[WorkflowStepDefinition, ...]
    required_capabilities: tuple[WorkflowCapability, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One concrete, planned step. Immutable and deterministically
    identified; carries everything execution needs to know without
    consulting the definition again."""

    step_id: WorkflowStepId
    step_type: WorkflowStepType
    ordinal: int
    required_capability: WorkflowCapability
    required_artifacts: tuple[WorkflowArtifactKey, ...]
    produced_artifacts: tuple[WorkflowArtifactKey, ...]
    optional: bool


@dataclass(frozen=True, slots=True)
class WorkflowPlanVersion:
    engine_version: str
    workflow_version: str
    plan_policy_version: str


@dataclass(frozen=True, slots=True)
class WorkflowPlanMetadata:
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    workflow_id: str
    workflow_type: WorkflowType
    planned_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowPlanStatistics:
    step_count: int
    required_step_count: int
    optional_step_count: int
    required_capability_count: int


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    plan_id: WorkflowPlanId
    workflow_id: WorkflowId
    workflow_type: WorkflowType
    steps: tuple[WorkflowStep, ...]
    required_capabilities: tuple[WorkflowCapability, ...]
    metadata: WorkflowPlanMetadata
    statistics: WorkflowPlanStatistics
    version: WorkflowPlanVersion


# --- Selection ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkflowSelection:
    workflow_id: WorkflowId
    workflow_type: WorkflowType
    workflow_version: str
    intent_type: EngineeringIntentType


@dataclass(frozen=True, slots=True)
class WorkflowSelectionResult:
    """Either a ``selection`` (supported intent, workflow registered) or
    a ``failure`` (unsupported intent, or no workflow registered for a
    nominally supported one) - never both, never neither."""

    selected: bool
    selection: WorkflowSelection | None = None
    failure: EngineeringEngineFailure | None = None


# --- Execution ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkflowStepResult:
    step_id: WorkflowStepId
    step_type: WorkflowStepType
    ordinal: int
    status: WorkflowStepStatus
    produced_artifacts: tuple[WorkflowArtifactKey, ...]
    started_at: datetime
    completed_at: datetime
    failure: WorkflowStepFailure | None = None


@dataclass(frozen=True, slots=True)
class WorkflowExecutionEvent:
    event_type: WorkflowExecutionEventType
    sequence: int
    occurred_at: datetime
    description: str


@dataclass(frozen=True, slots=True)
class WorkflowExecutionTimeline:
    """Append-only execution evidence - domain-level, not production
    tracing. No external telemetry infrastructure is introduced."""

    events: tuple[WorkflowExecutionEvent, ...]


@dataclass(frozen=True, slots=True)
class WorkflowExecutionStatistics:
    planned_step_count: int
    completed_step_count: int
    failed_step_count: int
    skipped_step_count: int
    timeline_event_count: int


@dataclass(frozen=True, slots=True)
class WorkflowExecution:
    execution_id: EngineeringEngineExecutionId
    plan_id: WorkflowPlanId
    status: EngineeringEngineExecutionStatus
    step_results: tuple[WorkflowStepResult, ...]
    timeline: WorkflowExecutionTimeline
    statistics: WorkflowExecutionStatistics
    started_at: datetime
    completed_at: datetime


# --- Aggregate update proposals ------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConversationUpdateProposal:
    """
    An explicit, immutable *proposal* to attach the produced
    ``EngineeringResponse`` to a conversation turn. Milestone 23A
    never applies it - a higher application service may, using
    ``conversation_service.attach_response``. ``disposition`` states
    plainly which happened.
    """

    conversation_id: str
    turn_id: str
    disposition: AggregateUpdateDisposition
    description: str


@dataclass(frozen=True, slots=True)
class SessionUpdateProposal:
    """The same, for appending the response to its
    ``EngineeringSession`` via
    ``engineering_session_service.append_response``."""

    engineering_session_id: str
    disposition: AggregateUpdateDisposition
    description: str


@dataclass(frozen=True, slots=True)
class PreparedAggregateUpdates:
    conversation_update: ConversationUpdateProposal | None
    session_update: SessionUpdateProposal | None


# --- Execution request and result -------------------------------------------------


@dataclass(frozen=True, slots=True)
class EngineeringEngineExecutionRequest:
    """
    Everything one engine execution needs, and nothing more.

    Deliberately carries **identifiers plus validated current-state
    objects**, not whole aggregates: the ``Conversation`` and
    ``EngineeringSession`` aggregates are never required, because
    Milestone 23A only *prepares* updates for them and therefore never
    needs to read or transform their current state (see ADR-0020's
    Aggregate Update Policy).

    ``engineering_intent`` is the full, already-validated classification
    result from Milestone 22 - the engine never re-classifies.
    ``working_memory_*`` fields are the same purely structural signals
    Working Memory itself exposes, carried here for workflow use without
    depending on the Working Memory bounded context.

    Retrieval and runtime configuration mirror the parameters the
    existing services already accept, so the engine adds no new
    configuration surface of its own.
    """

    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    request_text: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    executed_at: datetime
    # Retrieval configuration (mirrors StructuredRetrievalRequestFactory).
    retrieval_limit: int = 20
    retrieval_include_neighborhood: bool = False
    retrieval_neighborhood_depth: int = 0
    retrieval_entity_type: str | None = None
    retrieval_canonical_entity_id: str | None = None
    retrieval_attribute_name: str | None = None
    retrieval_lexical_terms: tuple[str, ...] = ()
    # Runtime configuration (mirrors the provider-neutral runtime).
    provider_id: str | None = None
    model_identifier: str | None = None
    request_correlation_id: str | None = None
    # Structural Working Memory signals (never memory contents).
    working_memory_has_open_question: bool = False
    working_memory_active_response_count: int = 0


@dataclass(frozen=True, slots=True)
class EngineeringEngineExecutionMetadata:
    engine_version: str
    plan_policy_version: str
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    executed_at: datetime


@dataclass(frozen=True, slots=True)
class EngineeringEngineValidationResult:
    """Structural validation of the execution result. Never validates
    engineering correctness."""

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringEngineExecutionResult:
    """
    The full, auditable outcome. On ``COMPLETED`` an
    ``engineering_response`` is present and ``failure`` is ``None``; on
    ``FAILED``/``UNSUPPORTED`` the reverse holds - never both, never
    neither. ``prepared_updates`` states explicitly whether aggregate
    updates were prepared or applied.
    """

    execution_id: EngineeringEngineExecutionId
    project_id: int
    status: EngineeringEngineExecutionStatus
    selection: WorkflowSelection | None
    plan: WorkflowPlan | None
    execution: WorkflowExecution | None
    engineering_response: EngineeringResponse | None
    prepared_updates: PreparedAggregateUpdates | None
    failure: EngineeringEngineFailure | None
    metadata: EngineeringEngineExecutionMetadata
    validation: EngineeringEngineValidationResult | None = None
