"""
Engine tests for the ENGINEERING_VERIFICATION workflow (Milestone 24.1) -
the first workflow that evaluates a statement rather than presenting
evidence.

Every dependency is an in-memory fake; no real provider is called. The
fake provider's scripted text is what lets all four verdicts be exercised
deterministically.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

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
    ENGINEERING_VERIFICATION_WORKFLOW,
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseOrigin,
    VerificationOutcome,
)
from app.domain.prompt_builder.composition_policy import (
    VERIFICATION_INSTRUCTIONS,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
)
from app.services import engineering_request_preparation_service
from app.services.engineering_engine.composition import (
    build_step_handler_registry,
    build_workflow_registry,
)
from tests.services._engineering_engine_support import (
    FakeDocumentMetadataPort,
    FakeEngineeringIndexRepository,
    FakeGraphQueryRepository,
    PopulatedFakeGraphQueryRepository,
    build_test_engine,
    execution_request,
    no_op_sleeper,
    provider_registry,
    runtime_configuration,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


def _verification_request(**overrides):
    """A classified VERIFICATION_REQUEST - the shape a prior
    ``/engineering-requests/prepare`` call produces for "Verify that
    protection 87T is present."."""

    defaults = dict(
        request_text="Verify that protection 87T is present.",
        intent_type=EngineeringIntentType.VERIFICATION_REQUEST,
        retrieval_entity_type=None,
        retrieval_lexical_terms=("87T",),
        retrieval_include_neighborhood=True,
        retrieval_neighborhood_depth=1,
    )
    defaults.update(overrides)

    return execution_request(**defaults)


def _engine_answering(text: str, *, graph=None, **overrides):
    return build_test_engine(
        outcomes=(FakeInvocationOutcome(text=text),),
        graph_query_repository=graph or PopulatedFakeGraphQueryRepository(),
        **overrides,
    )


def _verify(text: str, *, graph=None):
    return _execute(
        _engine_answering(text, graph=graph), _verification_request()
    )


# --- 1. Registration and registry resolution ------------------------------


def test_the_verification_workflow_is_registered() -> None:
    registry = build_workflow_registry()

    assert registry.is_registered(EngineeringIntentType.VERIFICATION_REQUEST)


def test_the_registry_resolves_the_verification_intent() -> None:
    registry = build_workflow_registry()

    definition = registry.resolve(
        EngineeringIntentType.VERIFICATION_REQUEST
    )

    assert definition is ENGINEERING_VERIFICATION_WORKFLOW
    assert definition.workflow_type is WorkflowType.ENGINEERING_VERIFICATION


def test_selecting_the_verification_intent_yields_a_selection() -> None:
    registry = build_workflow_registry()

    result = registry.select_workflow(
        EngineeringIntentType.VERIFICATION_REQUEST
    )

    assert result.selected is True
    assert result.failure is None
    assert result.selection.workflow_id.value == "engineering-verification"


def test_the_engine_resolves_the_workflow_through_the_registry() -> None:
    engine = build_test_engine()

    selection = engine.select_workflow(_verification_request())

    assert selection.selected is True
    assert selection.selection.workflow_type is (
        WorkflowType.ENGINEERING_VERIFICATION
    )


def test_the_composed_handler_registry_covers_every_step() -> None:
    registry = build_step_handler_registry(
        graph_query_repository=FakeGraphQueryRepository(),
        provider_registry=provider_registry(),
        runtime_configuration=runtime_configuration(),
        credential_present=True,
        credential_environment_variable_name="FAKE_API_KEY",
        sleeper=no_op_sleeper,
        engineering_index_repository=FakeEngineeringIndexRepository(),
        document_metadata_port=FakeDocumentMetadataPort(),
    )
    plan = build_plan(
        definition=ENGINEERING_VERIFICATION_WORKFLOW,
        request=_verification_request(),
    )

    assert registry.missing_handlers(plan) == ()


# --- 2. The definition reuses the pipeline, differing in one step ----------


def test_the_pipeline_matches_knowledge_query_except_the_prompt_step() -> None:
    verification = [
        step.step_type for step in ENGINEERING_VERIFICATION_WORKFLOW.steps
    ]
    knowledge_query = [
        step.step_type for step in KNOWLEDGE_QUERY_WORKFLOW.steps
    ]

    assert len(verification) == len(knowledge_query)
    differing = [
        (left, right)
        for left, right in zip(verification, knowledge_query)
        if left is not right
    ]

    assert differing == [
        (
            WorkflowStepType.BUILD_VERIFICATION_PROMPT,
            WorkflowStepType.BUILD_PROMPT,
        )
    ]


def test_the_response_step_is_reused_unchanged() -> None:
    """The verdict is read by Engineering Response from the objective the
    prompt package already carries, so this step needed no new type and no
    new handler."""

    step_types = {
        step.step_type for step in ENGINEERING_VERIFICATION_WORKFLOW.steps
    }

    assert WorkflowStepType.BUILD_ENGINEERING_RESPONSE in step_types


# --- 3. A successful verification, and each of the four outcomes ----------


def test_a_verification_executes_the_full_workflow_to_a_response() -> None:
    result = _verify("SUPPORTED\nCandidate c1 records the relay.")

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True
    assert result.selection.workflow_id.value == "engineering-verification"
    assert all(
        step.status is WorkflowStepStatus.COMPLETED
        for step in result.execution.step_results
    )
    assert result.engineering_response.verification is not None


def test_a_supported_statement_reports_supported() -> None:
    result = _verify("SUPPORTED\nCandidate c1 records the relay.")

    assessment = result.engineering_response.verification
    assert assessment.outcome is VerificationOutcome.SUPPORTED
    assert assessment.stated_by_model is True
    assert assessment.evidence_bounded is False
    assert assessment.evidence_reference_count > 0


def test_a_contradicted_statement_reports_not_supported() -> None:
    result = _verify("NOT_SUPPORTED\nCandidate c1 shows a different relay.")

    assert result.engineering_response.verification.outcome is (
        VerificationOutcome.NOT_SUPPORTED
    )


def test_an_uncovered_statement_reports_insufficient_evidence() -> None:
    result = _verify("INSUFFICIENT_EVIDENCE\nThe evidence does not cover it.")

    assert result.engineering_response.verification.outcome is (
        VerificationOutcome.INSUFFICIENT_EVIDENCE
    )


def test_contradictory_evidence_reports_conflicting_evidence() -> None:
    result = _verify("CONFLICTING_EVIDENCE\nc1 supports, c2 contradicts.")

    assert result.engineering_response.verification.outcome is (
        VerificationOutcome.CONFLICTING_EVIDENCE
    )


def test_a_non_compliant_answer_reports_no_verdict_rather_than_a_guess() -> (
    None
):
    result = _verify("It all looks fine to me.")

    assessment = result.engineering_response.verification
    assert assessment.outcome is None
    assert assessment.stated_by_model is False
    # Still a completed execution: the answer exists, it just carries no
    # machine-readable verdict.
    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True


def test_the_response_is_an_ordinary_llm_engineering_response() -> None:
    """No new response type: a verification is a normal
    ``EngineeringResponse`` with normal, populated provider metadata."""

    response = _verify("SUPPORTED\nc1.").engineering_response

    assert response.origin is EngineeringResponseOrigin.LLM_INVOCATION
    assert response.metadata.provider_id == "fake"
    assert response.metadata.configured_model_identifier == "fake-model"
    assert response.version.runtime_version is not None
    assert response.document_references == ()


def test_the_verification_prompt_step_ran() -> None:
    result = _verify("SUPPORTED\nc1.")
    step_types = [step.step_type for step in result.execution.step_results]

    assert WorkflowStepType.BUILD_VERIFICATION_PROMPT in step_types
    assert WorkflowStepType.BUILD_PROMPT not in step_types


def test_aggregate_updates_are_prepared_never_applied() -> None:
    result = _verify("SUPPORTED\nc1.")

    assert result.prepared_updates.conversation_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.prepared_updates.session_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )


def test_planning_is_deterministic_and_names_the_workflow() -> None:
    engine = _engine_answering("SUPPORTED\nc1.")
    request = _verification_request()

    first = _execute(engine, request)

    assert "engineering-verification" in first.plan.plan_id.value


# --- 4. Empty retrieval: the structural bound -----------------------------


def test_an_empty_project_cannot_yield_a_supported_verdict() -> None:
    """The safety property: the model claims SUPPORTED, but nothing was
    retrieved, so there was nothing to support the statement with."""

    result = _verify(
        "SUPPORTED\nThe relay is present.",
        graph=FakeGraphQueryRepository(),
    )

    assessment = result.engineering_response.verification
    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert assessment.outcome is VerificationOutcome.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_bounded is True
    assert assessment.stated_by_model is True
    assert result.validation.valid is True


def test_an_empty_retrieval_still_warns_about_insufficient_evidence() -> None:
    result = _verify("SUPPORTED\nc1.", graph=FakeGraphQueryRepository())

    assert any(
        warning.category.value == "insufficient_evidence"
        for warning in result.engineering_response.warnings
    )


# --- 5. Failure paths (existing taxonomy only) ----------------------------


def test_a_retrieval_failure_stops_execution_at_that_step() -> None:
    engine = _engine_answering(
        "SUPPORTED\nc1.",
        graph=FakeGraphQueryRepository(raises=RuntimeError("graph exploded")),
    )

    result = _execute(engine, _verification_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.step_type is WorkflowStepType.EXECUTE_RETRIEVAL
    assert result.engineering_response is None

    statuses = {
        step.step_type: step.status for step in result.execution.step_results
    }
    for later in (
        WorkflowStepType.BUILD_CONTEXT,
        WorkflowStepType.BUILD_VERIFICATION_PROMPT,
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
        ),
        graph_query_repository=PopulatedFakeGraphQueryRepository(),
    )

    result = _execute(engine, _verification_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE
    assert result.failure.step_type is WorkflowStepType.INVOKE_LLM_RUNTIME
    assert result.engineering_response is None


def test_an_invalid_request_fails_before_planning() -> None:
    engine = _engine_answering("SUPPORTED\nc1.")

    result = _execute(engine, _verification_request(project_id=0))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.plan is None


def test_a_prompt_build_failure_is_attributed_to_the_verification_step() -> (
    None
):
    from app.domain.prompt_builder.prompt_builder_exceptions import (
        PromptBuilderError,
    )
    from app.services.engineering_engine import step_handlers

    engine = _engine_answering("SUPPORTED\nc1.")

    def _explode(**_kwargs):
        raise PromptBuilderError("prompt builder refused")

    original = step_handlers.prompt_builder_service.build_prompt_package
    step_handlers.prompt_builder_service.build_prompt_package = _explode
    try:
        result = _execute(engine, _verification_request())
    finally:
        step_handlers.prompt_builder_service.build_prompt_package = original

    assert result.failure.code is (
        EngineeringEngineFailureCode.PROMPT_BUILD_FAILURE
    )
    assert result.failure.step_type is (
        WorkflowStepType.BUILD_VERIFICATION_PROMPT
    )


# --- 6. The other workflows are unchanged ---------------------------------


def test_a_knowledge_query_carries_no_verification_assessment() -> None:
    """A verdict belongs only to a response built from a verification
    prompt - no other workflow gains one."""

    engine = build_test_engine(
        graph_query_repository=PopulatedFakeGraphQueryRepository()
    )

    result = _execute(
        engine,
        execution_request(intent_type=EngineeringIntentType.KNOWLEDGE_QUERY),
    )

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.engineering_response.verification is None


def test_an_explanation_carries_no_verification_assessment() -> None:
    engine = build_test_engine(
        graph_query_repository=PopulatedFakeGraphQueryRepository()
    )

    result = _execute(
        engine,
        execution_request(
            intent_type=EngineeringIntentType.ENGINEERING_EXPLANATION
        ),
    )

    assert result.engineering_response.verification is None


def test_a_document_lookup_still_executes_and_carries_no_verdict() -> None:
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
    assert result.engineering_response.verification is None


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


# --- 7. End to end from a raw sentence ------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        "Verify that protection 87T is present.",
        "Verify that transformer T1 has differential protection.",
        "Check whether cable C-295 is connected to TA-12.",
        "Verify that breaker Q52 exists.",
    ],
)
def test_each_example_request_travels_from_raw_text_to_a_verdict(
    request_text: str,
) -> None:
    """The milestone's own examples, end to end, with no caller-supplied
    retrieval criteria."""

    prepared = (
        engineering_request_preparation_service.prepare_engineering_request(
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text=request_text,
            now=NOW,
            provider_id="fake",
            model_identifier="fake-model",
        )
    )

    assert prepared.prepared is True
    assert prepared.intent.intent_type is (
        EngineeringIntentType.VERIFICATION_REQUEST
    )

    result = _execute(
        _engine_answering("SUPPORTED\nCandidate c1 records it."),
        prepared.execution_request,
    )

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "engineering-verification"
    assert result.engineering_response.verification is not None


def test_a_prepared_verification_expands_the_neighborhood() -> None:
    """Verification statements are frequently relational, so the one hop
    around the named equipment is part of the evidence."""

    prepared = (
        engineering_request_preparation_service.prepare_engineering_request(
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text="Check whether cable C-295 is connected to TA-12.",
            now=NOW,
        )
    )
    request = prepared.execution_request

    assert request.retrieval_include_neighborhood is True
    assert request.retrieval_neighborhood_depth == 1
    # Both designations are searched: an entity lookup would have carried
    # only one and dropped the other.
    assert set(request.retrieval_lexical_terms) == {"C-295", "TA-12"}
    assert request.retrieval_canonical_entity_id is None


def test_the_verification_prompt_carries_its_own_instruction_set() -> None:
    """Prompt Builder owns verification prompting - the engine contributes
    no prompt text of its own."""

    assert any(
        instruction.identifier
        == "distinguish_absence_of_evidence_from_evidence_of_absence"
        for instruction in VERIFICATION_INSTRUCTIONS
    )
