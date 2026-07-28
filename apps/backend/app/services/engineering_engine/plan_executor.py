"""
The Workflow Plan Executor (Milestone 23A). Runs an already-built,
already-validated ``WorkflowPlan`` step by step through registered
handlers, recording an append-only timeline and a typed result for
every step.

Execution semantics:

- Steps run strictly in ordinal order. No parallelism, no retries -
  both are explicit non-goals of this milestone.
- Before a step runs, its declared required artifacts are checked
  against the typed execution context; a missing artifact fails
  deterministically with ``MISSING_REQUIRED_ARTIFACT``.
- After a step runs, its declared produced artifacts are checked; a
  handler that did not produce what it promised also fails with
  ``MISSING_REQUIRED_ARTIFACT`` rather than silently continuing.
- **Execution stops at the first failure.** Every remaining step is
  recorded as ``SKIPPED``, never executed.
- No raw exception escapes: a handler's ``StepHandlerError`` becomes a
  typed ``WorkflowStepFailure``, and any unexpected exception becomes
  ``INTERNAL_EXECUTION_ERROR``.

Timestamps come from an injected clock, so tests are fully
deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionId,
    EngineeringEngineExecutionStatus,
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowExecutionEventType,
    WorkflowExecutionStatistics,
    WorkflowExecutionTimeline,
    WorkflowPlan,
    WorkflowStep,
    WorkflowStepFailure,
    WorkflowStepResult,
    WorkflowStepStatus,
    EngineeringEngineFailureCode,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    derive_execution_id,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.step_handler_registry import (
    StepHandlerRegistry,
)
from app.services.engineering_engine.step_handler import StepHandlerError

Clock = Callable[[], datetime]


class _TimelineRecorder:
    """Builds the append-only timeline with contiguous sequence numbers."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._events: list[WorkflowExecutionEvent] = []

    def record(
        self, event_type: WorkflowExecutionEventType, description: str
    ) -> None:
        self._events.append(
            WorkflowExecutionEvent(
                event_type=event_type,
                sequence=len(self._events),
                occurred_at=self._clock(),
                description=description,
            )
        )

    def timeline(self) -> WorkflowExecutionTimeline:
        return WorkflowExecutionTimeline(events=tuple(self._events))

    @property
    def event_count(self) -> int:
        return len(self._events)


async def execute_plan(
    *,
    plan: WorkflowPlan,
    context: WorkflowExecutionContext,
    handlers: StepHandlerRegistry,
    clock: Clock,
    timeline_recorder: "_TimelineRecorder | None" = None,
) -> tuple[WorkflowExecution, WorkflowExecutionContext]:
    recorder = timeline_recorder or _TimelineRecorder(clock)
    if recorder.event_count == 0:
        recorder.record(
            WorkflowExecutionEventType.EXECUTION_CREATED,
            f"Execution created for plan '{plan.plan_id.value}'.",
        )

    started_at = clock()
    step_results: list[WorkflowStepResult] = []
    failed = False

    for step in plan.steps:
        if failed:
            step_results.append(
                _skipped_result(step, clock)
            )
            continue

        recorder.record(
            WorkflowExecutionEventType.STEP_STARTED,
            f"Step {step.ordinal} '{step.step_type.value}' started.",
        )
        step_started_at = clock()

        failure = _check_required_artifacts(step, context)
        if failure is None:
            try:
                handler = handlers.resolve(step.step_type)
            except Exception as error:  # StepHandlerNotRegisteredError
                failure = WorkflowStepFailure(
                    code=(
                        EngineeringEngineFailureCode.STEP_HANDLER_NOT_REGISTERED
                    ),
                    message="No handler is registered for this step type.",
                    detail=str(error),
                )
            else:
                try:
                    context = await handler.execute(step, context)
                except StepHandlerError as error:
                    failure = WorkflowStepFailure(
                        code=error.code,
                        message=error.message,
                        detail=error.detail,
                    )
                except Exception as error:  # noqa: BLE001 - see below
                    # A handler raising something unexpected is a
                    # programming error, not a domain outcome. It is
                    # deliberately caught here so it becomes a typed,
                    # provider-neutral engine failure rather than
                    # escaping as a raw exception through the engine
                    # domain (Milestone 23A's failure-model rule).
                    failure = WorkflowStepFailure(
                        code=(
                            EngineeringEngineFailureCode.INTERNAL_EXECUTION_ERROR
                        ),
                        message="An unexpected error occurred while "
                        "executing this step.",
                        detail=f"{type(error).__name__}: {error}",
                    )
                else:
                    failure = _check_produced_artifacts(step, context)

        step_completed_at = clock()

        if failure is None:
            step_results.append(
                WorkflowStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    ordinal=step.ordinal,
                    status=WorkflowStepStatus.COMPLETED,
                    produced_artifacts=step.produced_artifacts,
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                )
            )
            recorder.record(
                WorkflowExecutionEventType.STEP_COMPLETED,
                f"Step {step.ordinal} '{step.step_type.value}' completed.",
            )
        else:
            failed = True
            step_results.append(
                WorkflowStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    ordinal=step.ordinal,
                    status=WorkflowStepStatus.FAILED,
                    produced_artifacts=(),
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                    failure=failure,
                )
            )
            recorder.record(
                WorkflowExecutionEventType.STEP_FAILED,
                f"Step {step.ordinal} '{step.step_type.value}' failed: "
                f"{failure.code.value}.",
            )

    status = (
        EngineeringEngineExecutionStatus.FAILED
        if failed
        else EngineeringEngineExecutionStatus.COMPLETED
    )
    recorder.record(
        WorkflowExecutionEventType.EXECUTION_FAILED
        if failed
        else WorkflowExecutionEventType.EXECUTION_COMPLETED,
        f"Execution {status.value}.",
    )

    completed_at = clock()
    timeline = recorder.timeline()

    execution = WorkflowExecution(
        execution_id=EngineeringEngineExecutionId(
            value=derive_execution_id(plan_id=plan.plan_id.value)
        ),
        plan_id=plan.plan_id,
        status=status,
        step_results=tuple(step_results),
        timeline=timeline,
        statistics=WorkflowExecutionStatistics(
            planned_step_count=len(plan.steps),
            completed_step_count=sum(
                1
                for result in step_results
                if result.status is WorkflowStepStatus.COMPLETED
            ),
            failed_step_count=sum(
                1
                for result in step_results
                if result.status is WorkflowStepStatus.FAILED
            ),
            skipped_step_count=sum(
                1
                for result in step_results
                if result.status is WorkflowStepStatus.SKIPPED
            ),
            timeline_event_count=len(timeline.events),
        ),
        started_at=started_at,
        completed_at=completed_at,
    )

    return execution, context


def _skipped_result(step: WorkflowStep, clock: Clock) -> WorkflowStepResult:
    at = clock()

    return WorkflowStepResult(
        step_id=step.step_id,
        step_type=step.step_type,
        ordinal=step.ordinal,
        status=WorkflowStepStatus.SKIPPED,
        produced_artifacts=(),
        started_at=at,
        completed_at=at,
    )


def _check_required_artifacts(
    step: WorkflowStep, context: WorkflowExecutionContext
) -> WorkflowStepFailure | None:
    missing = context.missing_artifacts(step.required_artifacts)
    if not missing:
        return None

    return WorkflowStepFailure(
        code=EngineeringEngineFailureCode.MISSING_REQUIRED_ARTIFACT,
        message="A required artifact has not been produced.",
        detail=", ".join(key.value for key in missing),
    )


def _check_produced_artifacts(
    step: WorkflowStep, context: WorkflowExecutionContext
) -> WorkflowStepFailure | None:
    missing = context.missing_artifacts(step.produced_artifacts)
    if not missing:
        return None

    return WorkflowStepFailure(
        code=EngineeringEngineFailureCode.MISSING_REQUIRED_ARTIFACT,
        message="This step did not produce every artifact it declares.",
        detail=", ".join(key.value for key in missing),
    )
