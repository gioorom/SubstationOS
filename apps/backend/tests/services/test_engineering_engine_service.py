from __future__ import annotations

import asyncio

import pytest

from app.application.models.llm_invocation import LLMProviderErrorCategory
from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowExecutionEventType,
    WorkflowStepStatus,
    WorkflowStepType,
)
from app.domain.engineering_engine.workflow_definitions import (
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
)
from app.services.engineering_engine.composition import build_workflow_registry
from tests.services._engineering_engine_support import (
    NOW,
    FakeGraphQueryRepository,
    build_test_engine,
    execution_request,
    runtime_configuration,
)


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


# --- The required representative end-to-end case --------------------------


def test_knowledge_query_executes_the_full_workflow_to_an_engineering_response() -> (
    None
):
    engine = build_test_engine()

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True

    # Workflow selected.
    assert result.selection.workflow_id.value == "knowledge-query"
    assert result.selection.intent_type is (
        EngineeringIntentType.KNOWLEDGE_QUERY
    )

    # Valid plan created.
    assert len(result.plan.steps) == len(KNOWLEDGE_QUERY_WORKFLOW.steps)

    # Every step ran, in order, and completed.
    assert [r.step_type for r in result.execution.step_results] == [
        step.step_type for step in result.plan.steps
    ]
    assert all(
        r.status is WorkflowStepStatus.COMPLETED
        for r in result.execution.step_results
    )

    # EngineeringResponse built and validated.
    assert result.engineering_response is not None
    assert result.engineering_response.project_id == 1

    # Aggregate update outcome explicitly represented.
    assert result.prepared_updates is not None
    assert result.prepared_updates.conversation_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.prepared_updates.session_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.failure is None


def test_a_successful_execution_records_a_complete_timeline() -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request())
    event_types = [e.event_type for e in result.execution.timeline.events]

    assert event_types[0] is WorkflowExecutionEventType.EXECUTION_CREATED
    assert WorkflowExecutionEventType.WORKFLOW_SELECTED in event_types
    assert WorkflowExecutionEventType.PLAN_BUILT in event_types
    assert WorkflowExecutionEventType.PLAN_VALIDATED in event_types
    assert event_types[-1] is WorkflowExecutionEventType.EXECUTION_COMPLETED
    assert [e.sequence for e in result.execution.timeline.events] == list(
        range(len(result.execution.timeline.events))
    )


def test_execution_identity_is_deterministic() -> None:
    first = _execute(build_test_engine(), execution_request())
    second = _execute(build_test_engine(), execution_request())

    assert first.execution_id == second.execution_id
    assert first.plan == second.plan


# --- The required unsupported case ------------------------------------------


def test_a_drawing_request_is_unsupported_and_runs_nothing() -> None:
    repository = FakeGraphQueryRepository()
    engine = build_test_engine(graph_query_repository=repository)

    result = _execute(
        engine,
        execution_request(intent_type=EngineeringIntentType.DRAWING_REQUEST),
    )

    assert result.status is EngineeringEngineExecutionStatus.UNSUPPORTED
    assert result.failure.code is (
        EngineeringEngineFailureCode.UNSUPPORTED_INTENT
    )
    # No retrieval, no prompt, no runtime invocation - nothing ran.
    assert result.plan is None
    assert result.execution is None
    assert result.engineering_response is None
    assert result.prepared_updates is None
    assert repository.list_nodes_calls == 0
    assert result.validation.valid is True


@pytest.mark.parametrize(
    "intent_type",
    [
        intent
        for intent in EngineeringIntentType
        if not build_workflow_registry().is_registered(intent)
    ],
)
def test_every_unregistered_intent_is_unsupported(
    intent_type: EngineeringIntentType,
) -> None:
    """Derived from the registry rather than hard-coded, so registering a
    new workflow never silently leaves this asserting the old set. Which
    workflows *are* registered is asserted explicitly in
    ``test_engineering_engine_registries.py``."""

    engine = build_test_engine()

    result = _execute(engine, execution_request(intent_type=intent_type))

    assert result.status is EngineeringEngineExecutionStatus.UNSUPPORTED
    assert result.engineering_response is None


def test_an_unsupported_intent_never_routes_through_the_knowledge_workflow() -> (
    None
):
    engine = build_test_engine()

    result = _execute(
        engine,
        execution_request(
            intent_type=EngineeringIntentType.NAVIGATION_REQUEST
        ),
    )

    assert result.selection is None


# --- Failure cases ------------------------------------------------------------


def test_an_invalid_execution_request_fails_before_planning() -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request(project_id=0))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.plan is None
    assert result.execution is None


def test_a_retrieval_failure_stops_execution_at_that_step() -> None:
    engine = build_test_engine(
        graph_query_repository=FakeGraphQueryRepository(
            raises=RuntimeError("graph query exploded")
        )
    )

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.step_type is WorkflowStepType.EXECUTE_RETRIEVAL
    assert result.engineering_response is None

    statuses = {
        r.step_type: r.status for r in result.execution.step_results
    }
    assert statuses[WorkflowStepType.EXECUTE_RETRIEVAL] is (
        WorkflowStepStatus.FAILED
    )
    for later in (
        WorkflowStepType.BUILD_CONTEXT,
        WorkflowStepType.BUILD_PROMPT,
        WorkflowStepType.INVOKE_LLM_RUNTIME,
        WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
        WorkflowStepType.PREPARE_CONVERSATION_UPDATE,
        WorkflowStepType.PREPARE_SESSION_UPDATE,
    ):
        assert statuses[later] is WorkflowStepStatus.SKIPPED
    assert result.validation.valid is True


def test_a_runtime_failure_stops_execution_at_the_runtime_step() -> None:
    engine = build_test_engine(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=(
                    LLMProviderErrorCategory.AUTHENTICATION_FAILURE
                ),
            ),
        )
    )

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE
    assert result.failure.step_type is WorkflowStepType.INVOKE_LLM_RUNTIME
    assert result.engineering_response is None

    statuses = {r.step_type: r.status for r in result.execution.step_results}
    assert statuses[WorkflowStepType.BUILD_PROMPT] is (
        WorkflowStepStatus.COMPLETED
    )
    assert statuses[WorkflowStepType.BUILD_ENGINEERING_RESPONSE] is (
        WorkflowStepStatus.SKIPPED
    )


def test_a_disabled_runtime_fails_with_a_typed_runtime_failure() -> None:
    engine = build_test_engine(
        runtime_config=runtime_configuration(enabled=False)
    )

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE


def test_a_missing_credential_fails_with_a_typed_runtime_failure() -> None:
    engine = build_test_engine(credential_present=False)

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE
    assert result.engineering_response is None


def test_no_raw_provider_exception_escapes_the_engine() -> None:
    """A handler raising something entirely unexpected becomes a typed,
    provider-neutral engine failure rather than propagating."""

    engine = build_test_engine(
        graph_query_repository=FakeGraphQueryRepository(
            raises=ValueError("something nobody anticipated")
        )
    )

    result = _execute(engine, execution_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert isinstance(result.failure.code, EngineeringEngineFailureCode)
    assert result.failure.detail is not None


# --- Independently testable operations -----------------------------------------


def test_select_workflow_is_independently_callable() -> None:
    engine = build_test_engine()

    result = engine.select_workflow(execution_request())

    assert result.selected is True


def test_build_plan_is_independently_callable_without_executing() -> None:
    repository = FakeGraphQueryRepository()
    engine = build_test_engine(graph_query_repository=repository)

    plan = engine.build_plan(execution_request(), KNOWLEDGE_QUERY_WORKFLOW)

    assert len(plan.steps) == len(KNOWLEDGE_QUERY_WORKFLOW.steps)
    assert repository.list_nodes_calls == 0


def test_validate_plan_is_independently_callable() -> None:
    engine = build_test_engine()
    plan = engine.build_plan(execution_request(), KNOWLEDGE_QUERY_WORKFLOW)

    assert engine.validate_plan(plan).valid is True


# --- Aggregate update policy ------------------------------------------------------


def test_prepared_updates_name_the_target_aggregates_without_applying() -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request())
    updates = result.prepared_updates

    assert updates.conversation_update.conversation_id == "conv-1"
    assert updates.conversation_update.turn_id == "turn-1"
    assert updates.session_update.engineering_session_id == "sess-1"
    assert "Not applied by the engine" in (
        updates.conversation_update.description
    )
    assert "Not applied by the engine" in updates.session_update.description


def test_the_engine_never_claims_an_update_was_applied() -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request())

    for proposal in (
        result.prepared_updates.conversation_update,
        result.prepared_updates.session_update,
    ):
        assert proposal.disposition is not AggregateUpdateDisposition.APPLIED


# --- Execution statistics -----------------------------------------------------------


def test_execution_statistics_are_derivable() -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request())
    statistics = result.execution.statistics

    assert statistics.planned_step_count == len(result.plan.steps)
    assert statistics.completed_step_count == len(result.plan.steps)
    assert statistics.failed_step_count == 0
    assert statistics.skipped_step_count == 0
    assert statistics.timeline_event_count == len(
        result.execution.timeline.events
    )
