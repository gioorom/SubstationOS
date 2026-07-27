from __future__ import annotations

import asyncio

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowCapability,
    WorkflowDefinition,
    WorkflowExecutionEventType,
    WorkflowId,
    WorkflowStepDefinition,
    WorkflowStepStatus,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_engine.engineering_engine_validation import (
    validate_execution,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.plan_executor import execute_plan
from app.services.engineering_engine.step_handler_registry import (
    StepHandlerRegistry,
)
from app.services.engineering_engine.step_handlers import StepHandlerError
from tests.services._engineering_engine_support import NOW, execution_request


# --- Execution context ------------------------------------------------------


def test_a_fresh_context_carries_only_the_execution_request() -> None:
    context = WorkflowExecutionContext(execution_request=execution_request())

    assert context.has_artifact(WorkflowArtifactKey.EXECUTION_REQUEST) is True
    assert context.has_artifact(WorkflowArtifactKey.PROMPT_PACKAGE) is False


def test_with_artifact_returns_a_new_context_and_never_mutates() -> None:
    original = WorkflowExecutionContext(execution_request=execution_request())

    updated = original.with_artifact(
        WorkflowArtifactKey.PROMPT_PACKAGE, object()
    )

    assert updated is not original
    assert original.has_artifact(WorkflowArtifactKey.PROMPT_PACKAGE) is False
    assert updated.has_artifact(WorkflowArtifactKey.PROMPT_PACKAGE) is True


def test_missing_artifacts_reports_exactly_what_is_absent() -> None:
    context = WorkflowExecutionContext(execution_request=execution_request())

    missing = context.missing_artifacts(
        (
            WorkflowArtifactKey.EXECUTION_REQUEST,
            WorkflowArtifactKey.CONTEXT_PACKAGE,
            WorkflowArtifactKey.PROMPT_PACKAGE,
        )
    )

    assert missing == (
        WorkflowArtifactKey.CONTEXT_PACKAGE,
        WorkflowArtifactKey.PROMPT_PACKAGE,
    )


# --- Executor with synthetic handlers ------------------------------------------


class _RecordingHandler:
    """A minimal handler that records that it ran and optionally
    produces its declared artifact."""

    def __init__(
        self,
        step_type: WorkflowStepType,
        *,
        produces: WorkflowArtifactKey | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._step_type = step_type
        self._produces = produces
        self._raises = raises
        self.ran = False

    def supports(self, step_type: WorkflowStepType) -> bool:
        return step_type is self._step_type

    async def execute(self, step, context):
        self.ran = True
        if self._raises is not None:
            raise self._raises
        if self._produces is not None:
            return context.with_artifact(self._produces, object())
        return context


def _definition(*steps: WorkflowStepDefinition) -> WorkflowDefinition:
    capabilities = tuple({step.required_capability for step in steps})
    return WorkflowDefinition(
        workflow_id=WorkflowId(value="synthetic"),
        workflow_type=WorkflowType.KNOWLEDGE_QUERY,
        supported_intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        workflow_version="1.0",
        steps=steps,
        required_capabilities=capabilities,
    )


def _run(definition, handlers):
    plan = build_plan(definition=definition, request=execution_request())
    execution, context = asyncio.run(
        execute_plan(
            plan=plan,
            context=WorkflowExecutionContext(
                execution_request=execution_request()
            ),
            handlers=handlers,
            clock=lambda: NOW,
        )
    )
    return plan, execution, context


def test_a_two_step_plan_executes_both_steps_in_order() -> None:
    first = _RecordingHandler(
        WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
        produces=WorkflowArtifactKey.RETRIEVAL_REQUEST,
    )
    second = _RecordingHandler(
        WorkflowStepType.EXECUTE_RETRIEVAL,
        produces=WorkflowArtifactKey.RETRIEVAL_RESULT,
    )
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_RETRIEVAL_REQUEST, first)
    handlers.register(WorkflowStepType.EXECUTE_RETRIEVAL, second)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.RETRIEVAL_REQUEST,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_RETRIEVAL,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.RETRIEVAL_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.RETRIEVAL_RESULT,),
        ),
    )

    plan, execution, _context = _run(definition, handlers)

    assert first.ran and second.ran
    assert execution.status is EngineeringEngineExecutionStatus.COMPLETED
    assert validate_execution(execution, plan).valid is True


def test_a_missing_required_artifact_fails_deterministically() -> None:
    handler = _RecordingHandler(WorkflowStepType.BUILD_PROMPT)
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_PROMPT, handler)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
            produced_artifacts=(),
        ),
    )

    _plan, execution, _context = _run(definition, handlers)

    assert execution.status is EngineeringEngineExecutionStatus.FAILED
    assert execution.step_results[0].failure.code is (
        EngineeringEngineFailureCode.MISSING_REQUIRED_ARTIFACT
    )
    assert handler.ran is False


def test_a_handler_not_producing_its_declared_artifact_fails() -> None:
    handler = _RecordingHandler(WorkflowStepType.BUILD_PROMPT, produces=None)
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_PROMPT, handler)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
        ),
    )

    _plan, execution, _context = _run(definition, handlers)

    assert execution.status is EngineeringEngineExecutionStatus.FAILED
    assert execution.step_results[0].failure.code is (
        EngineeringEngineFailureCode.MISSING_REQUIRED_ARTIFACT
    )


def test_an_unregistered_handler_fails_with_a_typed_failure() -> None:
    handlers = StepHandlerRegistry()

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
    )

    _plan, execution, _context = _run(definition, handlers)

    assert execution.step_results[0].failure.code is (
        EngineeringEngineFailureCode.STEP_HANDLER_NOT_REGISTERED
    )


def test_execution_stops_at_the_first_failure_and_skips_the_rest() -> None:
    failing = _RecordingHandler(
        WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
        raises=StepHandlerError(
            EngineeringEngineFailureCode.RETRIEVAL_FAILURE, "boom"
        ),
    )
    never_runs = _RecordingHandler(WorkflowStepType.EXECUTE_RETRIEVAL)
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_RETRIEVAL_REQUEST, failing)
    handlers.register(WorkflowStepType.EXECUTE_RETRIEVAL, never_runs)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_RETRIEVAL,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
    )

    plan, execution, _context = _run(definition, handlers)

    assert never_runs.ran is False
    assert execution.step_results[0].status is WorkflowStepStatus.FAILED
    assert execution.step_results[1].status is WorkflowStepStatus.SKIPPED
    assert execution.statistics.skipped_step_count == 1
    assert validate_execution(execution, plan).valid is True


def test_an_unexpected_handler_exception_becomes_an_internal_error() -> None:
    handler = _RecordingHandler(
        WorkflowStepType.BUILD_PROMPT, raises=ZeroDivisionError("oops")
    )
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_PROMPT, handler)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
    )

    _plan, execution, _context = _run(definition, handlers)

    failure = execution.step_results[0].failure
    assert failure.code is (
        EngineeringEngineFailureCode.INTERNAL_EXECUTION_ERROR
    )
    assert "ZeroDivisionError" in failure.detail


def test_the_timeline_records_every_step_start_and_outcome() -> None:
    handler = _RecordingHandler(WorkflowStepType.BUILD_PROMPT)
    handlers = StepHandlerRegistry()
    handlers.register(WorkflowStepType.BUILD_PROMPT, handler)

    definition = _definition(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
    )

    _plan, execution, _context = _run(definition, handlers)
    event_types = [e.event_type for e in execution.timeline.events]

    assert event_types == [
        WorkflowExecutionEventType.EXECUTION_CREATED,
        WorkflowExecutionEventType.STEP_STARTED,
        WorkflowExecutionEventType.STEP_COMPLETED,
        WorkflowExecutionEventType.EXECUTION_COMPLETED,
    ]
