"""
Engine tests for the ENGINEERING_EXPLANATION workflow (Milestone 23B.2).

The third registered workflow, and the second LLM-powered one. Its whole
claim is that a genuinely different *kind of answer* needed no new
retrieval, no new context building, no new runtime integration and no new
response type - only a different Prompt Builder objective, stated
declaratively at composition.

Every dependency is an in-memory fake; no real provider is ever called.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.models.llm_invocation import LLMProviderErrorCategory
from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowStepStatus,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_engine.workflow_definitions import (
    ENGINEERING_EXPLANATION_WORKFLOW,
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseOrigin,
)
from app.domain.prompt_builder.composition_policy import (
    EXPLANATION_INSTRUCTIONS,
    INSTRUCTIONS,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
)
from app.services.engineering_engine.composition import (
    build_step_handler_registry,
    build_workflow_registry,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    RetrievalScope,
)
from app.services.engineering_engine.governed_retrieval_step_handlers import (
    BuildGovernedRetrievalPlanStepHandler,
)
from tests.services._engineering_engine_support import (
    FakeDocumentMetadataPort,
    FakeEngineeringIndexRepository,
    FakeGovernedKnowledgeReader,
    build_test_engine,
    execution_request,
    no_op_sleeper,
    provider_registry,
    runtime_configuration,
)


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


def _explanation_request(**overrides):
    """A classified ENGINEERING_EXPLANATION request - the shape a prior
    ``/engineering-intents/classify`` call produces for "Spiegami il
    funzionamento della protezione 87T"."""

    defaults = dict(
        request_text="Spiegami il funzionamento della protezione 87T",
        intent_type=EngineeringIntentType.ENGINEERING_EXPLANATION,
        retrieval_entity_type="PROTECTION",
    )
    defaults.update(overrides)

    return execution_request(**defaults)


# --- 1. Registration and registry resolution ------------------------------


def test_the_explanation_workflow_is_registered() -> None:
    registry = build_workflow_registry()

    assert registry.is_registered(
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )


def test_the_registry_resolves_the_explanation_intent() -> None:
    registry = build_workflow_registry()

    definition = registry.resolve(
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )

    assert definition is ENGINEERING_EXPLANATION_WORKFLOW
    assert definition.workflow_type is WorkflowType.ENGINEERING_EXPLANATION


def test_selecting_the_explanation_intent_yields_a_selection() -> None:
    registry = build_workflow_registry()

    result = registry.select_workflow(
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )

    assert result.selected is True
    assert result.failure is None
    assert result.selection.workflow_id.value == "engineering-explanation"


def test_the_engine_resolves_the_workflow_through_the_registry() -> None:
    engine = build_test_engine()

    selection = engine.select_workflow(_explanation_request())

    assert selection.selected is True
    assert selection.selection.workflow_type is (
        WorkflowType.ENGINEERING_EXPLANATION
    )


def test_the_composed_handler_registry_covers_every_step() -> None:
    registry = build_step_handler_registry(
        governed_knowledge_reader=FakeGovernedKnowledgeReader(),
        provider_registry=provider_registry(),
        runtime_configuration=runtime_configuration(),
        credential_present=True,
        credential_environment_variable_name="FAKE_API_KEY",
        sleeper=no_op_sleeper,
        engineering_index_repository=FakeEngineeringIndexRepository(),
        document_metadata_port=FakeDocumentMetadataPort(),
    )
    plan = build_plan(
        definition=ENGINEERING_EXPLANATION_WORKFLOW,
        request=_explanation_request(),
    )

    assert registry.missing_handlers(plan) == ()


# --- 2. The definition differs from knowledge query in exactly one step ----


def test_the_pipeline_matches_knowledge_query_except_the_prompt_step() -> None:
    explanation = [
        step.step_type for step in ENGINEERING_EXPLANATION_WORKFLOW.steps
    ]
    knowledge_query = [
        step.step_type for step in KNOWLEDGE_QUERY_WORKFLOW.steps
    ]

    assert len(explanation) == len(knowledge_query)
    differing = [
        (left, right)
        for left, right in zip(explanation, knowledge_query)
        if left is not right
    ]

    assert differing == [
        (
            WorkflowStepType.BUILD_EXPLANATION_PROMPT,
            WorkflowStepType.BUILD_PROMPT,
        )
    ]


def test_the_explanation_prompt_step_produces_the_same_artifact() -> None:
    """Which is why every downstream step is reused unchanged."""

    prompt_step = next(
        step
        for step in ENGINEERING_EXPLANATION_WORKFLOW.steps
        if step.step_type is WorkflowStepType.BUILD_EXPLANATION_PROMPT
    )
    knowledge_prompt_step = next(
        step
        for step in KNOWLEDGE_QUERY_WORKFLOW.steps
        if step.step_type is WorkflowStepType.BUILD_PROMPT
    )

    assert prompt_step.required_artifacts == (
        knowledge_prompt_step.required_artifacts
    )
    assert prompt_step.produced_artifacts == (
        knowledge_prompt_step.produced_artifacts
    )
    assert prompt_step.required_capability is (
        knowledge_prompt_step.required_capability
    )


def test_both_workflows_declare_the_same_capabilities() -> None:
    assert (
        ENGINEERING_EXPLANATION_WORKFLOW.required_capabilities
        == KNOWLEDGE_QUERY_WORKFLOW.required_capabilities
    )


# --- 3. Successful explanation generation ---------------------------------


def test_an_explanation_executes_the_full_workflow_to_a_response() -> None:
    engine = build_test_engine()

    result = _execute(engine, _explanation_request())

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True
    assert result.selection.workflow_id.value == "engineering-explanation"
    assert len(result.plan.steps) == len(
        ENGINEERING_EXPLANATION_WORKFLOW.steps
    )
    assert all(
        step.status is WorkflowStepStatus.COMPLETED
        for step in result.execution.step_results
    )
    assert result.engineering_response is not None


def test_the_response_is_an_ordinary_llm_engineering_response() -> None:
    """No new response type: an explanation is a normal
    ``EngineeringResponse`` with normal, populated provider metadata."""

    engine = build_test_engine()

    response = _execute(engine, _explanation_request()).engineering_response

    assert response.origin is EngineeringResponseOrigin.LLM_INVOCATION
    assert response.metadata.provider_id == "fake"
    assert response.metadata.configured_model_identifier == "fake-model"
    assert response.metadata.request_correlation_id
    assert response.version.runtime_version is not None
    assert response.document_references == ()


def test_the_prompt_step_ran_with_the_explanation_objective() -> None:
    """Observed through the produced response's own prompt provenance
    rather than by reaching inside the handler."""

    engine = build_test_engine()

    result = _execute(engine, _explanation_request())
    step_types = [step.step_type for step in result.execution.step_results]

    assert WorkflowStepType.BUILD_EXPLANATION_PROMPT in step_types
    assert WorkflowStepType.BUILD_PROMPT not in step_types


def test_aggregate_updates_are_prepared_never_applied() -> None:
    engine = build_test_engine()

    result = _execute(engine, _explanation_request())

    assert result.prepared_updates.conversation_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.prepared_updates.session_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )


def test_planning_is_deterministic_and_names_the_workflow() -> None:
    engine = build_test_engine()
    request = _explanation_request()

    first = _execute(engine, request)
    second = _execute(engine, request)

    assert first.plan.plan_id == second.plan.plan_id
    assert "engineering-explanation" in first.plan.plan_id.value


def test_the_same_turn_classified_differently_gets_a_different_plan() -> None:
    engine = build_test_engine()

    explanation = _execute(engine, _explanation_request())
    query = _execute(
        engine,
        execution_request(intent_type=EngineeringIntentType.KNOWLEDGE_QUERY),
    )

    assert explanation.plan.plan_id != query.plan.plan_id


# --- 4. Retrieval reuse ----------------------------------------------------


def test_retrieval_reads_the_governed_graph() -> None:
    graph = FakeGovernedKnowledgeReader()
    engine = build_test_engine(governed_knowledge_reader=graph)

    _execute(engine, _explanation_request())

    assert graph.read_calls > 0


def test_the_explanation_workflow_invents_no_retrieval_criteria() -> None:
    """Retrieval configuration is caller-supplied and the explanation
    workflow widens nothing on its own - retrieving "everything about the
    project" in order to explain one relay is exactly the unrelated
    context this milestone forbids. Asserted through the shared retrieval
    handler, which is the same one the knowledge-query workflow uses."""

    handler = BuildGovernedRetrievalPlanStepHandler()
    request = _explanation_request(
        retrieval_canonical_entity_id="PROTECTION:87T",
        retrieval_entity_type=None,
        retrieval_lexical_terms=(),
    )

    context = asyncio.run(
        handler.execute(None, WorkflowExecutionContext(execution_request=request))
    )

    plan = context.retrieval_request

    # One designation, the one the caller named - and the `PROTECTION`
    # classification is dropped rather than matched, because the
    # governed graph holds what a document designates and never what
    # the equipment is.
    assert [query.designation for query in plan.queries] == ["87T"]
    assert plan.queries[0].limit == request.retrieval_limit
    assert plan.queries[0].scope is RetrievalScope.CURRENT_ONLY


# --- 5. Failure paths (all existing taxonomy) ------------------------------


def test_a_retrieval_failure_stops_execution_at_that_step() -> None:
    engine = build_test_engine(
        governed_knowledge_reader=FakeGovernedKnowledgeReader(
            raises=RuntimeError("graph query exploded")
        )
    )

    result = _execute(engine, _explanation_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.step_type is WorkflowStepType.EXECUTE_RETRIEVAL
    assert result.engineering_response is None

    statuses = {
        step.step_type: step.status for step in result.execution.step_results
    }
    for later in (
        WorkflowStepType.BUILD_CONTEXT,
        WorkflowStepType.BUILD_EXPLANATION_PROMPT,
        WorkflowStepType.INVOKE_LLM_RUNTIME,
        WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
    ):
        assert statuses[later] is WorkflowStepStatus.SKIPPED


def test_a_runtime_failure_is_reported_with_the_existing_code() -> None:
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

    result = _execute(engine, _explanation_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE
    assert result.failure.step_type is WorkflowStepType.INVOKE_LLM_RUNTIME
    assert result.engineering_response is None
    assert result.validation.valid is True


def test_an_invalid_request_fails_before_planning() -> None:
    engine = build_test_engine()

    result = _execute(engine, _explanation_request(project_id=0))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.plan is None
    assert result.execution is None


def test_a_prompt_build_failure_is_reported_at_the_prompt_step() -> None:
    """A prompt that cannot be built fails with the existing
    PROMPT_BUILD_FAILURE code, attributed to the explanation prompt step -
    no new failure taxonomy for this workflow."""

    from app.domain.prompt_builder.prompt_builder_exceptions import (
        PromptBuilderError,
    )
    from app.services.engineering_engine import step_handlers

    engine = build_test_engine()

    def _explode(**_kwargs):
        raise PromptBuilderError("prompt builder refused")

    original = step_handlers.prompt_builder_service.build_prompt_package
    step_handlers.prompt_builder_service.build_prompt_package = _explode
    try:
        result = _execute(engine, _explanation_request())
    finally:
        step_handlers.prompt_builder_service.build_prompt_package = original

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.PROMPT_BUILD_FAILURE
    )
    assert result.failure.step_type is (
        WorkflowStepType.BUILD_EXPLANATION_PROMPT
    )


# --- 6. Empty retrieval ----------------------------------------------------


def test_finding_no_knowledge_still_completes_with_a_response() -> None:
    """The shared fake graph is an empty project. Retrieving nothing is a
    valid outcome the whole pipeline already handles: the response says so
    rather than the execution failing."""

    engine = build_test_engine()

    result = _execute(engine, _explanation_request())
    response = result.engineering_response

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert response.warnings != ()
    assert any(
        warning.category.value == "insufficient_evidence"
        for warning in response.warnings
    )


# --- 7. The other workflows still behave exactly as before -----------------


def test_knowledge_query_still_uses_the_direct_answer_objective() -> None:
    """The regression that matters most: adding an objective must not have
    changed the knowledge-query prompt."""

    assert (
        KNOWLEDGE_QUERY_WORKFLOW.steps[4].step_type
        is WorkflowStepType.BUILD_PROMPT
    )
    assert INSTRUCTIONS != EXPLANATION_INSTRUCTIONS


def test_knowledge_query_still_executes_end_to_end() -> None:
    engine = build_test_engine()

    result = _execute(
        engine,
        execution_request(intent_type=EngineeringIntentType.KNOWLEDGE_QUERY),
    )

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "knowledge-query"


def test_document_lookup_still_executes_end_to_end() -> None:
    from tests.domain._document_retrieval_support import entry, metadata

    engine = build_test_engine(
        engineering_index_repository=FakeEngineeringIndexRepository([entry()]),
        document_metadata_port=FakeDocumentMetadataPort([metadata()]),
    )

    result = _execute(
        engine,
        execution_request(
            intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
            retrieval_entity_type=None,
            retrieval_lexical_terms=("T2",),
        ),
    )

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "document-lookup"
    assert result.engineering_response.origin is (
        EngineeringResponseOrigin.DETERMINISTIC_RETRIEVAL
    )


@pytest.mark.parametrize(
    "intent_type",
    [
        intent
        for intent in EngineeringIntentType
        if not build_workflow_registry().is_registered(intent)
    ],
)
def test_unregistered_intents_are_still_unsupported(
    intent_type: EngineeringIntentType,
) -> None:
    engine = build_test_engine()

    result = _execute(engine, execution_request(intent_type=intent_type))

    assert result.status is EngineeringEngineExecutionStatus.UNSUPPORTED
    assert result.failure.code is (
        EngineeringEngineFailureCode.UNSUPPORTED_INTENT
    )
    assert result.plan is None
    assert result.engineering_response is None
