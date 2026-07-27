"""
The Engineering Engine Service (Milestone 23A) - the application-level
coordinator.

It contains **no workflow-specific business logic**. Knowledge-query
behaviour lives entirely in the registered ``WorkflowDefinition``
(``workflow_definitions.py``) and the concrete step handlers
(``step_handlers.py``). This module only:

    select_workflow -> build_plan -> validate_plan -> execute_plan

Each of those is independently callable and independently testable -
planning is never hidden inside execution.

There is **no intent branching here.** Workflow selection is entirely
registry-driven; adding a workflow in Milestone 23B requires no change
to this file.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionId,
    EngineeringEngineExecutionMetadata,
    EngineeringEngineExecutionRequest,
    EngineeringEngineExecutionResult,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailure,
    EngineeringEngineFailureCode,
    PreparedAggregateUpdates,
    WorkflowDefinition,
    WorkflowExecutionEventType,
    WorkflowPlan,
    WorkflowSelectionResult,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    ENGINE_VERSION,
    PLAN_POLICY_VERSION,
    derive_execution_id,
    derive_workflow_plan_id,
)
from app.domain.engineering_engine.engineering_engine_validation import (
    validate_execution_request,
    validate_execution_result,
    validate_plan,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.plan_executor import (
    _TimelineRecorder,
    execute_plan,
)
from app.services.engineering_engine.step_handler_registry import (
    StepHandlerRegistry,
)
from app.services.engineering_engine.workflow_registry import WorkflowRegistry

Clock = Callable[[], datetime]


class EngineeringEngineService:
    def __init__(
        self,
        *,
        workflow_registry: WorkflowRegistry,
        step_handler_registry: StepHandlerRegistry,
        clock: Clock,
    ) -> None:
        self._workflows = workflow_registry
        self._handlers = step_handler_registry
        self._clock = clock

    # --- Independently testable operations ---------------------------

    def select_workflow(
        self, request: EngineeringEngineExecutionRequest
    ) -> WorkflowSelectionResult:
        return self._workflows.select_workflow(request.intent_type)

    def build_plan(
        self,
        request: EngineeringEngineExecutionRequest,
        definition: WorkflowDefinition,
    ) -> WorkflowPlan:
        return build_plan(definition=definition, request=request)

    def validate_plan(self, plan: WorkflowPlan):
        return validate_plan(plan)

    # --- Full coordination -------------------------------------------

    async def execute(
        self, request: EngineeringEngineExecutionRequest
    ) -> EngineeringEngineExecutionResult:
        metadata = self._metadata(request)

        request_validation = validate_execution_request(request)
        if not request_validation.valid:
            return self._failed_before_planning(
                request,
                metadata,
                EngineeringEngineFailure(
                    code=(
                        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
                    ),
                    message="The execution request is structurally invalid.",
                    detail="; ".join(request_validation.errors),
                ),
                status=EngineeringEngineExecutionStatus.FAILED,
            )

        selection_result = self.select_workflow(request)
        if not selection_result.selected:
            # Unsupported intent: no plan is built, no downstream
            # component runs, no LLM is invoked.
            return self._failed_before_planning(
                request,
                metadata,
                selection_result.failure,
                status=EngineeringEngineExecutionStatus.UNSUPPORTED,
            )

        definition = self._workflows.resolve(request.intent_type)
        plan = self.build_plan(request, definition)

        recorder = _TimelineRecorder(self._clock)
        recorder.record(
            WorkflowExecutionEventType.EXECUTION_CREATED,
            f"Execution created for plan '{plan.plan_id.value}'.",
        )
        recorder.record(
            WorkflowExecutionEventType.WORKFLOW_SELECTED,
            f"Workflow '{definition.workflow_id.value}' selected for intent "
            f"'{request.intent_type.value}'.",
        )
        recorder.record(
            WorkflowExecutionEventType.PLAN_BUILT,
            f"Plan built with {len(plan.steps)} steps.",
        )

        plan_validation = self.validate_plan(plan)
        if not plan_validation.valid:
            return self._failed_with_plan(
                request,
                metadata,
                plan,
                selection_result,
                EngineeringEngineFailure(
                    code=EngineeringEngineFailureCode.INVALID_WORKFLOW_PLAN,
                    message="The built workflow plan is structurally "
                    "invalid.",
                    detail="; ".join(plan_validation.errors),
                ),
            )

        missing_handlers = self._handlers.missing_handlers(plan)
        if missing_handlers:
            return self._failed_with_plan(
                request,
                metadata,
                plan,
                selection_result,
                EngineeringEngineFailure(
                    code=(
                        EngineeringEngineFailureCode.STEP_HANDLER_NOT_REGISTERED
                    ),
                    message="One or more plan steps have no registered "
                    "handler.",
                    detail=", ".join(
                        step_type.value for step_type in missing_handlers
                    ),
                ),
            )

        recorder.record(
            WorkflowExecutionEventType.PLAN_VALIDATED,
            "Plan validated and every required handler is available.",
        )

        execution, context = await execute_plan(
            plan=plan,
            context=WorkflowExecutionContext(execution_request=request),
            handlers=self._handlers,
            clock=self._clock,
            timeline_recorder=recorder,
        )

        if execution.status is EngineeringEngineExecutionStatus.FAILED:
            failing = next(
                (
                    result
                    for result in execution.step_results
                    if result.failure is not None
                ),
                None,
            )
            failure = (
                EngineeringEngineFailure(
                    code=failing.failure.code,
                    message=failing.failure.message,
                    detail=failing.failure.detail,
                    step_id=failing.step_id.value,
                    step_type=failing.step_type,
                )
                if failing is not None
                else EngineeringEngineFailure(
                    code=(
                        EngineeringEngineFailureCode.INTERNAL_EXECUTION_ERROR
                    ),
                    message="Execution failed without recording a step "
                    "failure.",
                )
            )

            result = EngineeringEngineExecutionResult(
                execution_id=execution.execution_id,
                project_id=request.project_id,
                status=EngineeringEngineExecutionStatus.FAILED,
                selection=selection_result.selection,
                plan=plan,
                execution=execution,
                engineering_response=None,
                prepared_updates=None,
                failure=failure,
                metadata=metadata,
            )
            return self._validated(result)

        result = EngineeringEngineExecutionResult(
            execution_id=execution.execution_id,
            project_id=request.project_id,
            status=EngineeringEngineExecutionStatus.COMPLETED,
            selection=selection_result.selection,
            plan=plan,
            execution=execution,
            engineering_response=context.engineering_response,
            prepared_updates=PreparedAggregateUpdates(
                conversation_update=context.conversation_update_proposal,
                session_update=context.session_update_proposal,
            ),
            failure=None,
            metadata=metadata,
        )
        return self._validated(result)

    # --- Helpers -----------------------------------------------------

    def _metadata(
        self, request: EngineeringEngineExecutionRequest
    ) -> EngineeringEngineExecutionMetadata:
        return EngineeringEngineExecutionMetadata(
            engine_version=ENGINE_VERSION,
            plan_policy_version=PLAN_POLICY_VERSION,
            project_id=request.project_id,
            engineering_session_id=request.engineering_session_id,
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            engineering_intent_id=request.engineering_intent_id,
            intent_type=request.intent_type,
            executed_at=request.executed_at,
        )

    def _provisional_execution_id(
        self, request: EngineeringEngineExecutionRequest
    ) -> EngineeringEngineExecutionId:
        """An execution id derived the same deterministic way even when
        no plan was built - so a rejected or unsupported execution is
        still identifiable and still recognizably the same execution on
        a repeat attempt."""

        plan_id = derive_workflow_plan_id(
            project_id=request.project_id,
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            engineering_intent_id=request.engineering_intent_id,
            workflow_id="none",
            workflow_version="none",
        )

        return EngineeringEngineExecutionId(
            value=derive_execution_id(plan_id=plan_id)
        )

    def _failed_before_planning(
        self,
        request: EngineeringEngineExecutionRequest,
        metadata: EngineeringEngineExecutionMetadata,
        failure: EngineeringEngineFailure,
        *,
        status: EngineeringEngineExecutionStatus,
    ) -> EngineeringEngineExecutionResult:
        result = EngineeringEngineExecutionResult(
            execution_id=self._provisional_execution_id(request),
            project_id=request.project_id,
            status=status,
            selection=None,
            plan=None,
            execution=None,
            engineering_response=None,
            prepared_updates=None,
            failure=failure,
            metadata=metadata,
        )
        return self._validated(result)

    def _failed_with_plan(
        self,
        request: EngineeringEngineExecutionRequest,
        metadata: EngineeringEngineExecutionMetadata,
        plan: WorkflowPlan,
        selection_result: WorkflowSelectionResult,
        failure: EngineeringEngineFailure,
    ) -> EngineeringEngineExecutionResult:
        result = EngineeringEngineExecutionResult(
            execution_id=EngineeringEngineExecutionId(
                value=derive_execution_id(plan_id=plan.plan_id.value)
            ),
            project_id=request.project_id,
            status=EngineeringEngineExecutionStatus.FAILED,
            selection=selection_result.selection,
            plan=plan,
            execution=None,
            engineering_response=None,
            prepared_updates=None,
            failure=failure,
            metadata=metadata,
        )
        return self._validated(result)

    @staticmethod
    def _validated(
        result: EngineeringEngineExecutionResult,
    ) -> EngineeringEngineExecutionResult:
        from dataclasses import replace

        return replace(result, validation=validate_execution_result(result))
