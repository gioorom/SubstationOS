from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionRequest,
    WorkflowArtifactKey,
    WorkflowCapability,
    WorkflowDefinition,
    WorkflowId,
    WorkflowStepDefinition,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    ENGINE_VERSION,
    PLAN_POLICY_VERSION,
)
from app.domain.engineering_engine.engineering_engine_validation import (
    validate_execution_request,
    validate_plan,
    validate_workflow_definition,
)
from app.domain.engineering_engine.workflow_definitions import (
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


def _request(**overrides) -> EngineeringEngineExecutionRequest:
    defaults = dict(
        project_id=1,
        engineering_session_id="sess-1",
        conversation_id="conv-1",
        turn_id="turn-1",
        request_text="Quale TA è installato sul montante T2?",
        engineering_intent_id="conv-1:turn-1:1.0",
        intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        executed_at=NOW,
    )
    defaults.update(overrides)
    return EngineeringEngineExecutionRequest(**defaults)


# --- Execution request validation -----------------------------------------


def test_a_well_formed_execution_request_is_valid() -> None:
    result = validate_execution_request(_request())

    assert result.valid is True
    assert result.errors == ()


def test_a_non_positive_project_id_is_rejected() -> None:
    result = validate_execution_request(_request(project_id=0))

    assert result.valid is False
    assert any("project_id" in e for e in result.errors)


def test_blank_provenance_is_rejected() -> None:
    result = validate_execution_request(_request(turn_id="  "))

    assert result.valid is False
    assert any("turn_id is blank" in e for e in result.errors)


def test_blank_request_text_is_rejected() -> None:
    result = validate_execution_request(_request(request_text="   "))

    assert result.valid is False
    assert any("request_text is blank" in e for e in result.errors)


def test_a_non_positive_retrieval_limit_is_rejected() -> None:
    result = validate_execution_request(_request(retrieval_limit=0))

    assert result.valid is False
    assert any("retrieval_limit" in e for e in result.errors)


# --- Workflow definition validation ------------------------------------------


def test_the_knowledge_query_definition_is_valid() -> None:
    result = validate_workflow_definition(KNOWLEDGE_QUERY_WORKFLOW)

    assert result.valid is True
    assert result.errors == ()


def test_the_knowledge_query_definition_declares_the_real_pipeline() -> None:
    step_types = [step.step_type for step in KNOWLEDGE_QUERY_WORKFLOW.steps]

    assert step_types == [
        WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
        WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
        WorkflowStepType.EXECUTE_RETRIEVAL,
        WorkflowStepType.BUILD_CONTEXT,
        WorkflowStepType.BUILD_PROMPT,
        WorkflowStepType.INVOKE_LLM_RUNTIME,
        WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
        WorkflowStepType.VALIDATE_ENGINEERING_RESPONSE,
        WorkflowStepType.PREPARE_CONVERSATION_UPDATE,
        WorkflowStepType.PREPARE_SESSION_UPDATE,
    ]


def test_a_definition_with_no_steps_is_rejected() -> None:
    broken = replace(KNOWLEDGE_QUERY_WORKFLOW, steps=())

    result = validate_workflow_definition(broken)

    assert result.valid is False
    assert any("at least one step" in e for e in result.errors)


def test_a_definition_requiring_an_unproduced_artifact_is_rejected() -> None:
    broken = replace(
        KNOWLEDGE_QUERY_WORKFLOW,
        steps=(
            WorkflowStepDefinition(
                step_type=WorkflowStepType.BUILD_CONTEXT,
                required_capability=WorkflowCapability.CONTEXT_BUILDING,
                required_artifacts=(WorkflowArtifactKey.RETRIEVAL_RESULT,),
                produced_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
            ),
        ),
    )

    result = validate_workflow_definition(broken)

    assert result.valid is False
    assert any("before any step produces it" in e for e in result.errors)


def test_a_definition_with_an_undeclared_capability_is_rejected() -> None:
    broken = replace(
        KNOWLEDGE_QUERY_WORKFLOW,
        required_capabilities=(WorkflowCapability.REQUEST_VALIDATION,),
    )

    result = validate_workflow_definition(broken)

    assert result.valid is False
    assert any("does not declare" in e for e in result.errors)


def test_a_definition_with_a_duplicate_step_type_is_rejected() -> None:
    first = KNOWLEDGE_QUERY_WORKFLOW.steps[0]
    broken = replace(KNOWLEDGE_QUERY_WORKFLOW, steps=(first, first))

    result = validate_workflow_definition(broken)

    assert result.valid is False
    assert any("duplicate step type" in e for e in result.errors)


# --- Plan building -------------------------------------------------------------


def test_a_built_plan_is_valid() -> None:
    plan = build_plan(
        definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request()
    )

    result = validate_plan(plan)
    assert result.valid is True
    assert result.errors == ()


def test_plan_identity_is_deterministically_derived() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert plan.plan_id.value == (
        "1:conv-1:turn-1:conv-1:turn-1:1.0:knowledge-query:1.0"
    )


def test_step_identity_is_deterministically_derived() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert plan.steps[0].step_id.value == (
        f"{plan.plan_id.value}#0:validate_execution_request"
    )
    assert plan.steps[5].step_id.value == (
        f"{plan.plan_id.value}#5:invoke_llm_runtime"
    )


def test_identical_inputs_produce_an_identical_plan() -> None:
    first = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    second = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert first == second


def test_a_different_turn_produces_a_different_plan_identity() -> None:
    first = build_plan(
        definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request(turn_id="turn-1")
    )
    second = build_plan(
        definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request(turn_id="turn-2")
    )

    assert first.plan_id != second.plan_id


def test_a_different_workflow_version_produces_a_different_plan_identity() -> (
    None
):
    other_definition = replace(
        KNOWLEDGE_QUERY_WORKFLOW, workflow_version="2.0"
    )

    first = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    second = build_plan(definition=other_definition, request=_request())

    assert first.plan_id != second.plan_id


def test_step_ordinals_are_contiguous_from_zero() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert [step.ordinal for step in plan.steps] == list(
        range(len(plan.steps))
    )


def test_plan_statistics_are_derivable() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert plan.statistics.step_count == len(plan.steps)
    assert plan.statistics.optional_step_count == 0
    assert plan.statistics.required_step_count == len(plan.steps)
    assert plan.statistics.required_capability_count == len(
        KNOWLEDGE_QUERY_WORKFLOW.required_capabilities
    )


def test_plan_version_records_engine_workflow_and_policy_versions() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert plan.version.engine_version == ENGINE_VERSION
    assert plan.version.plan_policy_version == PLAN_POLICY_VERSION
    assert plan.version.workflow_version == (
        KNOWLEDGE_QUERY_WORKFLOW.workflow_version
    )


def test_planned_at_comes_from_the_request_not_the_wall_clock() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())

    assert plan.metadata.planned_at == NOW


# --- Plan validation ----------------------------------------------------------


def test_a_plan_with_a_non_derived_id_is_rejected() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    broken = replace(plan, plan_id=replace(plan.plan_id, value="random"))

    result = validate_plan(broken)

    assert result.valid is False
    assert any("deterministically derived" in e for e in result.errors)


def test_a_plan_with_non_contiguous_ordinals_is_rejected() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    broken_step = replace(plan.steps[0], ordinal=7)
    broken = replace(plan, steps=(broken_step,) + plan.steps[1:])

    result = validate_plan(broken)

    assert result.valid is False
    assert any("contiguous" in e for e in result.errors)


def test_a_plan_with_inconsistent_statistics_is_rejected() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    broken = replace(plan, statistics=replace(plan.statistics, step_count=99))

    result = validate_plan(broken)

    assert result.valid is False
    assert any("step_count" in e for e in result.errors)


def test_an_empty_plan_is_rejected() -> None:
    plan = build_plan(definition=KNOWLEDGE_QUERY_WORKFLOW, request=_request())
    broken = replace(
        plan, steps=(), statistics=replace(plan.statistics, step_count=0)
    )

    result = validate_plan(broken)

    assert result.valid is False
    assert any("at least one step" in e for e in result.errors)


def test_a_plan_step_requiring_an_unproduced_artifact_is_rejected() -> None:
    definition = WorkflowDefinition(
        workflow_id=WorkflowId(value="broken"),
        workflow_type=WorkflowType.KNOWLEDGE_QUERY,
        supported_intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        workflow_version="1.0",
        steps=(
            WorkflowStepDefinition(
                step_type=WorkflowStepType.BUILD_PROMPT,
                required_capability=WorkflowCapability.PROMPT_BUILDING,
                required_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
                produced_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
            ),
        ),
        required_capabilities=(WorkflowCapability.PROMPT_BUILDING,),
    )
    plan = build_plan(definition=definition, request=_request())

    result = validate_plan(plan)

    assert result.valid is False
    assert any("before any step produces it" in e for e in result.errors)
