"""
The Workflow Planner (Milestone 23A). Converts a declarative
``WorkflowDefinition`` plus an ``EngineeringEngineExecutionRequest``
into an immutable, deterministically identified ``WorkflowPlan``.

Pure and deterministic: no I/O, no service call, no wall-clock read
(``planned_at`` comes from the request's own caller-supplied
``executed_at``). Given the same request, definition, and versions, the
plan - including every step id - is byte-for-byte identical. See
ADR-0020 on planning determinism versus runtime nondeterminism.

Planning is deliberately separate from execution: a caller may build
and inspect a plan without running anything.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionRequest,
    WorkflowDefinition,
    WorkflowPlan,
    WorkflowPlanId,
    WorkflowPlanMetadata,
    WorkflowPlanStatistics,
    WorkflowPlanVersion,
    WorkflowStep,
    WorkflowStepId,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    ENGINE_VERSION,
    PLAN_POLICY_VERSION,
    derive_workflow_plan_id,
    derive_workflow_step_id,
)


def build_plan(
    *,
    definition: WorkflowDefinition,
    request: EngineeringEngineExecutionRequest,
) -> WorkflowPlan:
    plan_id_value = derive_workflow_plan_id(
        project_id=request.project_id,
        conversation_id=request.conversation_id,
        turn_id=request.turn_id,
        engineering_intent_id=request.engineering_intent_id,
        workflow_id=definition.workflow_id.value,
        workflow_version=definition.workflow_version,
    )
    plan_id = WorkflowPlanId(value=plan_id_value)

    steps = tuple(
        WorkflowStep(
            step_id=WorkflowStepId(
                value=derive_workflow_step_id(
                    plan_id=plan_id_value,
                    ordinal=ordinal,
                    step_type=step_definition.step_type.value,
                )
            ),
            step_type=step_definition.step_type,
            ordinal=ordinal,
            required_capability=step_definition.required_capability,
            required_artifacts=step_definition.required_artifacts,
            produced_artifacts=step_definition.produced_artifacts,
            optional=step_definition.optional,
        )
        for ordinal, step_definition in enumerate(definition.steps)
    )

    optional_count = sum(1 for step in steps if step.optional)

    return WorkflowPlan(
        plan_id=plan_id,
        workflow_id=definition.workflow_id,
        workflow_type=definition.workflow_type,
        steps=steps,
        required_capabilities=definition.required_capabilities,
        metadata=WorkflowPlanMetadata(
            project_id=request.project_id,
            engineering_session_id=request.engineering_session_id,
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            engineering_intent_id=request.engineering_intent_id,
            intent_type=request.intent_type,
            workflow_id=definition.workflow_id.value,
            workflow_type=definition.workflow_type,
            planned_at=request.executed_at,
        ),
        statistics=WorkflowPlanStatistics(
            step_count=len(steps),
            required_step_count=len(steps) - optional_count,
            optional_step_count=optional_count,
            required_capability_count=len(definition.required_capabilities),
        ),
        version=WorkflowPlanVersion(
            engine_version=ENGINE_VERSION,
            workflow_version=definition.workflow_version,
            plan_policy_version=PLAN_POLICY_VERSION,
        ),
    )
