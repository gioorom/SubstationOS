"""
Structural validation for the Engineering Engine (Milestone 23A):
execution requests, workflow definitions, workflow plans, workflow
executions, and execution results.

**Validation is structural.** It never validates engineering
correctness, never judges whether the selected workflow was the "right"
one, and never inspects an ``EngineeringResponse``'s own content
(Engineering Response validates itself - ADR-0015).
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    EngineeringEngineExecutionRequest,
    EngineeringEngineExecutionResult,
    EngineeringEngineExecutionStatus,
    EngineeringEngineValidationResult,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionEventType,
    WorkflowPlan,
    WorkflowStepStatus,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    derive_execution_id,
    derive_workflow_plan_id,
    derive_workflow_step_id,
)


def validate_execution_request(
    request: EngineeringEngineExecutionRequest,
) -> EngineeringEngineValidationResult:
    errors: list[str] = []

    if request.project_id <= 0:
        errors.append("project_id is not positive.")

    for field_name, value in (
        ("engineering_session_id", request.engineering_session_id),
        ("conversation_id", request.conversation_id),
        ("turn_id", request.turn_id),
        ("engineering_intent_id", request.engineering_intent_id),
    ):
        if not value or not value.strip():
            errors.append(f"{field_name} is blank.")

    if not request.request_text or not request.request_text.strip():
        errors.append("request_text is blank.")

    if request.executed_at is None:
        errors.append("executed_at is missing.")

    if request.retrieval_limit <= 0:
        errors.append("retrieval_limit is not positive.")

    if request.retrieval_neighborhood_depth < 0:
        errors.append("retrieval_neighborhood_depth is negative.")

    return EngineeringEngineValidationResult(
        valid=not errors, errors=tuple(errors)
    )


def validate_workflow_definition(
    definition: WorkflowDefinition,
) -> EngineeringEngineValidationResult:
    errors: list[str] = []

    if not definition.workflow_id.value.strip():
        errors.append("workflow_id is blank.")
    if not definition.workflow_version.strip():
        errors.append("workflow_version is blank.")
    if not definition.steps:
        errors.append("A workflow definition must declare at least one step.")

    declared_capabilities = set(definition.required_capabilities)
    for step in definition.steps:
        if step.required_capability not in declared_capabilities:
            errors.append(
                f"Step '{step.step_type.value}' requires capability "
                f"'{step.required_capability.value}', which the "
                "definition does not declare."
            )
            break

    # Every artifact a step requires must be produced by an earlier step,
    # or be the execution request itself (always present at start).
    produced_so_far = set()
    for step in definition.steps:
        for artifact in step.required_artifacts:
            if artifact.value == "execution_request":
                continue
            if artifact not in produced_so_far:
                errors.append(
                    f"Step '{step.step_type.value}' requires artifact "
                    f"'{artifact.value}' before any step produces it."
                )
                break
        produced_so_far.update(step.produced_artifacts)

    step_types = [step.step_type for step in definition.steps]
    if len(set(step_types)) != len(step_types):
        errors.append("A workflow definition declares a duplicate step type.")

    return EngineeringEngineValidationResult(
        valid=not errors, errors=tuple(errors)
    )


def validate_plan(plan: WorkflowPlan) -> EngineeringEngineValidationResult:
    errors: list[str] = []

    expected_plan_id = derive_workflow_plan_id(
        project_id=plan.metadata.project_id,
        conversation_id=plan.metadata.conversation_id,
        turn_id=plan.metadata.turn_id,
        engineering_intent_id=plan.metadata.engineering_intent_id,
        workflow_id=plan.metadata.workflow_id,
        workflow_version=plan.version.workflow_version,
    )
    if plan.plan_id.value != expected_plan_id:
        errors.append(
            "plan_id is not deterministically derived from its own "
            "provenance and workflow version."
        )

    if not plan.steps:
        errors.append("A plan must contain at least one step.")

    ordinals = [step.ordinal for step in plan.steps]
    if ordinals != list(range(len(plan.steps))):
        errors.append("Step ordinals are not contiguous from zero.")
    if len(set(ordinals)) != len(ordinals):
        errors.append("Step ordinals are not unique.")

    for step in plan.steps:
        expected_step_id = derive_workflow_step_id(
            plan_id=plan.plan_id.value,
            ordinal=step.ordinal,
            step_type=step.step_type.value,
        )
        if step.step_id.value != expected_step_id:
            errors.append(
                f"Step at ordinal {step.ordinal} does not have a "
                "deterministically derived step id."
            )
            break

    declared_capabilities = set(plan.required_capabilities)
    for step in plan.steps:
        if step.required_capability not in declared_capabilities:
            errors.append(
                f"Step '{step.step_type.value}' requires an undeclared "
                "capability."
            )
            break

    produced_so_far = set()
    for step in plan.steps:
        for artifact in step.required_artifacts:
            if artifact.value == "execution_request":
                continue
            if artifact not in produced_so_far:
                errors.append(
                    f"Step '{step.step_type.value}' requires artifact "
                    f"'{artifact.value}' before any step produces it."
                )
                break
        produced_so_far.update(step.produced_artifacts)

    if plan.statistics.step_count != len(plan.steps):
        errors.append(
            "Plan statistics step_count is inconsistent with its steps."
        )
    expected_optional = sum(1 for step in plan.steps if step.optional)
    if plan.statistics.optional_step_count != expected_optional:
        errors.append(
            "Plan statistics optional_step_count is inconsistent with its "
            "steps."
        )
    if plan.statistics.required_step_count != len(plan.steps) - expected_optional:
        errors.append(
            "Plan statistics required_step_count is inconsistent with its "
            "steps."
        )
    if plan.statistics.required_capability_count != len(
        plan.required_capabilities
    ):
        errors.append(
            "Plan statistics required_capability_count is inconsistent "
            "with its declared capabilities."
        )

    if (
        not plan.version.engine_version
        or not plan.version.workflow_version
        or not plan.version.plan_policy_version
    ):
        errors.append("Plan version fields are incomplete.")

    if (
        plan.metadata.project_id <= 0
        or not plan.metadata.conversation_id
        or not plan.metadata.turn_id
        or not plan.metadata.engineering_intent_id
        or plan.metadata.planned_at is None
    ):
        errors.append("Plan metadata is incomplete.")

    return EngineeringEngineValidationResult(
        valid=not errors, errors=tuple(errors)
    )


def validate_execution(
    execution: WorkflowExecution, plan: WorkflowPlan
) -> EngineeringEngineValidationResult:
    errors: list[str] = []

    if execution.execution_id.value != derive_execution_id(
        plan_id=plan.plan_id.value
    ):
        errors.append(
            "execution_id is not deterministically derived from its plan."
        )

    if execution.plan_id != plan.plan_id:
        errors.append("execution references a different plan.")

    if len(execution.step_results) > len(plan.steps):
        errors.append("execution reports more step results than the plan has steps.")

    for index, result in enumerate(execution.step_results):
        if index < len(plan.steps):
            planned = plan.steps[index]
            if result.step_id != planned.step_id:
                errors.append(
                    f"Step result at position {index} does not match the "
                    "planned step id."
                )
                break
            if result.ordinal != planned.ordinal:
                errors.append(
                    f"Step result at position {index} does not match the "
                    "planned ordinal."
                )
                break

    failed = [
        result
        for result in execution.step_results
        if result.status is WorkflowStepStatus.FAILED
    ]
    if len(failed) > 1:
        errors.append("More than one step failed - execution must stop at the first.")
    for result in failed:
        if result.failure is None:
            errors.append("A failed step result carries no failure.")
            break

    for result in execution.step_results:
        if result.status is not WorkflowStepStatus.FAILED and (
            result.failure is not None
        ):
            errors.append("A non-failed step result carries a failure.")
            break

    # A failed execution must stop: no completed step may follow a failure.
    failure_index = next(
        (
            index
            for index, result in enumerate(execution.step_results)
            if result.status is WorkflowStepStatus.FAILED
        ),
        None,
    )
    if failure_index is not None:
        for result in execution.step_results[failure_index + 1 :]:
            if result.status is WorkflowStepStatus.COMPLETED:
                errors.append(
                    "A step completed after an earlier step failed - "
                    "execution must stop at the first failure."
                )
                break

    if execution.status is EngineeringEngineExecutionStatus.COMPLETED:
        if failed:
            errors.append("A COMPLETED execution reports a failed step.")
        if len(execution.step_results) != len(plan.steps):
            errors.append(
                "A COMPLETED execution did not execute every planned step."
            )
    elif execution.status is EngineeringEngineExecutionStatus.FAILED:
        if not failed:
            errors.append("A FAILED execution reports no failed step.")

    events = execution.timeline.events
    if not events:
        errors.append("Execution timeline must contain at least one event.")
    else:
        if events[0].event_type is not (
            WorkflowExecutionEventType.EXECUTION_CREATED
        ):
            errors.append("Timeline does not begin with EXECUTION_CREATED.")

        expected_sequence = 0
        previous_at = None
        for event in events:
            if event.sequence != expected_sequence:
                errors.append(
                    "Timeline events are not sequenced contiguously from zero."
                )
                break
            expected_sequence += 1
            if previous_at is not None and event.occurred_at < previous_at:
                errors.append("Timeline events are not chronologically ordered.")
                break
            previous_at = event.occurred_at

    statistics = execution.statistics
    if statistics.planned_step_count != len(plan.steps):
        errors.append(
            "Execution statistics planned_step_count is inconsistent with "
            "the plan."
        )
    expected_completed = sum(
        1
        for result in execution.step_results
        if result.status is WorkflowStepStatus.COMPLETED
    )
    if statistics.completed_step_count != expected_completed:
        errors.append(
            "Execution statistics completed_step_count is inconsistent "
            "with the step results."
        )
    if statistics.failed_step_count != len(failed):
        errors.append(
            "Execution statistics failed_step_count is inconsistent with "
            "the step results."
        )
    expected_skipped = sum(
        1
        for result in execution.step_results
        if result.status is WorkflowStepStatus.SKIPPED
    )
    if statistics.skipped_step_count != expected_skipped:
        errors.append(
            "Execution statistics skipped_step_count is inconsistent with "
            "the step results."
        )
    if statistics.timeline_event_count != len(events):
        errors.append(
            "Execution statistics timeline_event_count is inconsistent "
            "with the timeline."
        )

    return EngineeringEngineValidationResult(
        valid=not errors, errors=tuple(errors)
    )


def validate_execution_result(
    result: EngineeringEngineExecutionResult,
) -> EngineeringEngineValidationResult:
    errors: list[str] = []

    if result.project_id <= 0:
        errors.append("project_id is not positive.")
    if result.project_id != result.metadata.project_id:
        errors.append("project_id is inconsistent with metadata.")

    metadata = result.metadata
    if (
        not metadata.engine_version
        or not metadata.plan_policy_version
        or not metadata.engineering_session_id
        or not metadata.conversation_id
        or not metadata.turn_id
        or not metadata.engineering_intent_id
        or metadata.executed_at is None
    ):
        errors.append("Execution metadata is incomplete.")

    if result.status is EngineeringEngineExecutionStatus.COMPLETED:
        if result.engineering_response is None:
            errors.append(
                "A COMPLETED execution must carry an EngineeringResponse."
            )
        if result.failure is not None:
            errors.append("A COMPLETED execution must carry no failure.")
        if result.plan is None or result.execution is None:
            errors.append(
                "A COMPLETED execution must carry both a plan and an "
                "execution record."
            )
        if result.selection is None:
            errors.append("A COMPLETED execution must carry a workflow selection.")
    else:
        if result.engineering_response is not None:
            errors.append(
                "A non-completed execution must not carry an "
                "EngineeringResponse."
            )
        if result.failure is None:
            errors.append("A non-completed execution must carry a failure.")

    if result.status is EngineeringEngineExecutionStatus.UNSUPPORTED:
        if result.plan is not None or result.execution is not None:
            errors.append(
                "An UNSUPPORTED execution must not carry a plan or an "
                "execution record - no downstream component may run."
            )
        if result.prepared_updates is not None:
            errors.append(
                "An UNSUPPORTED execution must not carry prepared updates."
            )

    if result.prepared_updates is not None:
        conversation_update = result.prepared_updates.conversation_update
        session_update = result.prepared_updates.session_update
        for proposal in (conversation_update, session_update):
            if proposal is None:
                continue
            if proposal.disposition is AggregateUpdateDisposition.APPLIED:
                errors.append(
                    "Milestone 23A never applies aggregate updates - a "
                    "proposal must not claim APPLIED."
                )
                break

    return EngineeringEngineValidationResult(
        valid=not errors, errors=tuple(errors)
    )
