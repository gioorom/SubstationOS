"""
Engine tests for the ENGINEERING_COMPARISON workflow (Milestone 24.2) -
the first workflow with two subjects and two independently retrieved
evidence sets.

The properties that matter most, and are hardest to get right:

1. **The two sides never merge.** Provenance survives retrieval, context
   and prompt.
2. **Direction is preserved.** "Compare A with B" never becomes "compare
   B with A".
3. **A missing side is never a difference.** This is the safety property:
   given evidence for T1 and none for T2, no fluent answer can turn the
   gap into "T2 lacks what T1 has".

Every dependency is an in-memory fake; no real provider is called.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.application.models.llm_invocation import LLMProviderErrorCategory
from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    ComparisonOperandCriteria,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowStepStatus,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_engine.workflow_definitions import (
    ENGINEERING_COMPARISON_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_response.engineering_response_models import (
    ComparisonOutcome,
    EngineeringResponseOrigin,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptObjective,
    PromptSectionType,
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
    FakeGovernedKnowledgeReader,
    PopulatedFakeGovernedKnowledgeReader,
    build_test_engine,
    execution_request,
    no_op_sleeper,
    provider_registry,
    runtime_configuration,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)
COMPARABLE = "COMPARABLE\nUNCHANGED: both carry the same protection (c1)."


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


def _comparison_request(left: str = "T1", right: str = "T2", **overrides):
    defaults = dict(
        request_text=f"Confronta il trasformatore {left} con {right}",
        intent_type=EngineeringIntentType.ENGINEERING_COMPARISON,
        retrieval_entity_type=None,
        comparison_left=ComparisonOperandCriteria(
            designation=left,
            retrieval_lexical_terms=(left,),
            retrieval_include_neighborhood=True,
            retrieval_neighborhood_depth=1,
        ),
        comparison_right=ComparisonOperandCriteria(
            designation=right,
            retrieval_lexical_terms=(right,),
            retrieval_include_neighborhood=True,
            retrieval_neighborhood_depth=1,
        ),
    )
    defaults.update(overrides)

    return execution_request(**defaults)


def _engine(text: str = COMPARABLE, *, graph=None, **overrides):
    return build_test_engine(
        outcomes=(FakeInvocationOutcome(text=text),),
        governed_knowledge_reader=(
            graph or PopulatedFakeGovernedKnowledgeReader(("T1", "T2"))
        ),
        **overrides,
    )


def _compare(text: str = COMPARABLE, *, graph=None, request=None):
    return _execute(
        _engine(text, graph=graph), request or _comparison_request()
    )


# --- 1. Registration and registry resolution ------------------------------


def test_the_comparison_workflow_is_registered() -> None:
    registry = build_workflow_registry()

    assert registry.is_registered(
        EngineeringIntentType.ENGINEERING_COMPARISON
    )


def test_the_registry_resolves_the_comparison_intent() -> None:
    registry = build_workflow_registry()

    definition = registry.resolve(
        EngineeringIntentType.ENGINEERING_COMPARISON
    )

    assert definition is ENGINEERING_COMPARISON_WORKFLOW
    assert definition.workflow_type is WorkflowType.ENGINEERING_COMPARISON


def test_selecting_the_comparison_intent_yields_a_selection() -> None:
    result = build_workflow_registry().select_workflow(
        EngineeringIntentType.ENGINEERING_COMPARISON
    )

    assert result.selected is True
    assert result.selection.workflow_id.value == "engineering-comparison"


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
        definition=ENGINEERING_COMPARISON_WORKFLOW,
        request=_comparison_request(),
    )

    assert registry.missing_handlers(plan) == ()


def test_the_definition_declares_two_independent_retrieval_steps() -> None:
    step_types = [
        step.step_type for step in ENGINEERING_COMPARISON_WORKFLOW.steps
    ]

    assert WorkflowStepType.EXECUTE_LEFT_RETRIEVAL in step_types
    assert WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL in step_types
    assert step_types.index(
        WorkflowStepType.EXECUTE_LEFT_RETRIEVAL
    ) < step_types.index(WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL)


# --- 2. Successful end-to-end comparison ----------------------------------


def test_a_comparison_executes_the_full_workflow_to_a_response() -> None:
    result = _compare()

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True
    assert result.selection.workflow_id.value == "engineering-comparison"
    assert all(
        step.status is WorkflowStepStatus.COMPLETED
        for step in result.execution.step_results
    )
    assert result.engineering_response.comparison is not None


def test_a_comparable_pair_reports_comparable() -> None:
    assessment = _compare().engineering_response.comparison

    assert assessment.outcome is ComparisonOutcome.COMPARABLE
    assert assessment.stated_by_model is True
    assert assessment.evidence_bounded is False
    assert assessment.left_evidence_count > 0
    assert assessment.right_evidence_count > 0


def test_conflicting_evidence_is_reported_as_such() -> None:
    assessment = _compare(
        "CONFLICTING_EVIDENCE\nc1 says one thing, c2 another."
    ).engineering_response.comparison

    assert assessment.outcome is ComparisonOutcome.CONFLICTING_EVIDENCE


def test_a_non_compliant_answer_reports_no_outcome() -> None:
    result = _compare("They look broadly similar to me.")
    assessment = result.engineering_response.comparison

    assert assessment.outcome is None
    assert assessment.stated_by_model is False
    assert result.status is EngineeringEngineExecutionStatus.COMPLETED


def test_the_response_is_an_ordinary_llm_engineering_response() -> None:
    response = _compare().engineering_response

    assert response.origin is EngineeringResponseOrigin.LLM_INVOCATION
    assert response.metadata.provider_id == "fake"
    assert response.verification is None
    assert response.document_references == ()


def test_aggregate_updates_are_prepared_never_applied() -> None:
    result = _compare()

    assert result.prepared_updates.conversation_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.prepared_updates.session_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )


# --- 3. Dual retrieval and provenance -------------------------------------


def test_both_sides_are_retrieved_independently() -> None:
    graph = PopulatedFakeGovernedKnowledgeReader(("T1", "T2"))

    _compare(graph=graph)

    # Two retrievals, not one shared read.
    assert graph.read_calls >= 2


def test_the_context_keeps_the_two_sides_separate() -> None:
    """The provenance guarantee: each side is its own whole
    ``ContextPackage``, never a merged candidate list."""

    from app.services.engineering_engine.comparison_step_handlers import (
        BuildComparisonContextStepHandler,
    )
    from app.services.engineering_engine.governed_retrieval_step_handlers import (  # noqa: E501
        BuildComparisonGovernedRetrievalPlansStepHandler,
        ExecuteLeftGovernedRetrievalStepHandler,
        ExecuteRightGovernedRetrievalStepHandler,
    )
    from app.services.engineering_engine.execution_context import (
        WorkflowExecutionContext,
    )

    graph = PopulatedFakeGovernedKnowledgeReader(("T1", "T2"))
    context = WorkflowExecutionContext(execution_request=_comparison_request())

    context = asyncio.run(
        BuildComparisonGovernedRetrievalPlansStepHandler().execute(None, context)
    )
    context = asyncio.run(
        ExecuteLeftGovernedRetrievalStepHandler(graph).execute(None, context)
    )
    context = asyncio.run(
        ExecuteRightGovernedRetrievalStepHandler(graph).execute(None, context)
    )
    context = asyncio.run(
        BuildComparisonContextStepHandler().execute(None, context)
    )

    comparison = context.comparison_context
    assert comparison.left.designation == "T1"
    assert comparison.right.designation == "T2"
    assert comparison.left.package is not comparison.right.package

    left_ids = {
        item.item_id for item in comparison.left.package.selected_items
    }
    right_ids = {
        item.item_id for item in comparison.right.package.selected_items
    }
    assert left_ids and right_ids
    assert left_ids != right_ids


def test_the_left_request_never_becomes_the_right_result() -> None:
    from app.services.engineering_engine.governed_retrieval_step_handlers import (  # noqa: E501
        BuildComparisonGovernedRetrievalPlansStepHandler,
    )
    from app.services.engineering_engine.execution_context import (
        WorkflowExecutionContext,
    )

    context = asyncio.run(
        BuildComparisonGovernedRetrievalPlansStepHandler().execute(
            None,
            WorkflowExecutionContext(execution_request=_comparison_request()),
        )
    )

    assert context.left_retrieval_request.queries[0].designation == "T1"
    assert context.right_retrieval_request.queries[0].designation == "T2"


def test_the_prompt_retains_left_and_right_direction() -> None:
    from app.domain.prompt_builder.comparison_prompt_composition import (
        compose_comparison_sections,
    )
    from app.services import context_builder_service
    from tests._governed_context import designation_result

    # Each side keeps its **own** governed results: a comparison never
    # shares one retrieval between two subjects.
    left = (designation_result("T1", ()),)
    right = (designation_result("T2", ()),)
    comparison = context_builder_service.build_comparison_context_package(
        project_id=1,
        left_designation="T1",
        left_results=left,
        right_designation="T2",
        right_results=right,
        now=NOW,
    )

    assembly = compose_comparison_sections(comparison)
    by_type = {s.section_type: s for s in assembly.sections}

    left = by_type[PromptSectionType.LEFT_KNOWLEDGE]
    right = by_type[PromptSectionType.RIGHT_KNOWLEDGE]
    assert any("T1" in line for line in left.content)
    assert any("T2" in line for line in right.content)
    assert left.content != right.content

    engineering = by_type[PromptSectionType.ENGINEERING_CONTEXT].content
    assert any("LEFT subject: T1" in line for line in engineering)
    assert any("RIGHT subject: T2" in line for line in engineering)
    assert any("LEFT to RIGHT" in line for line in engineering)


def test_the_prompt_uses_the_comparison_objective() -> None:
    from app.services import context_builder_service, prompt_builder_service
    from tests._governed_context import designation_result

    # Each side keeps its **own** governed results: a comparison never
    # shares one retrieval between two subjects.
    left = (designation_result("T1", ()),)
    right = (designation_result("T2", ()),)
    comparison = context_builder_service.build_comparison_context_package(
        project_id=1,
        left_designation="T1",
        left_results=left,
        right_designation="T2",
        right_results=right,
        now=NOW,
    )

    result = prompt_builder_service.build_comparison_prompt_package(
        comparison_context=comparison, now=NOW
    )

    assert result.package.objective is PromptObjective.ENGINEERING_COMPARISON
    assert result.validation.valid is True


# --- 4. Partial and empty results -----------------------------------------


@pytest.mark.parametrize(
    ("label", "present"),
    [("right side empty", ("T1",)), ("left side empty", ("T2",))],
)
def test_a_missing_side_is_never_reported_as_a_difference(
    label: str, present: tuple[str, ...]
) -> None:
    """The safety property. The model confidently claims a difference; the
    system refuses to record one, because the absent side's silence is a
    gap in the project's knowledge, not a finding."""

    result = _compare(
        "COMPARABLE\nT2 is missing the differential protection T1 has.",
        graph=PopulatedFakeGovernedKnowledgeReader(present),
    )
    assessment = result.engineering_response.comparison

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert assessment.outcome is ComparisonOutcome.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_bounded is True
    assert assessment.stated_by_model is True
    assert result.validation.valid is True


def test_both_sides_empty_reports_insufficient_evidence() -> None:
    result = _compare(
        "COMPARABLE\nThey are identical.", graph=FakeGovernedKnowledgeReader()
    )
    assessment = result.engineering_response.comparison

    assert assessment.outcome is ComparisonOutcome.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_bounded is True
    assert assessment.left_evidence_count == 0
    assert assessment.right_evidence_count == 0


def test_a_missing_side_is_warned_about_by_name() -> None:
    response = _compare(
        COMPARABLE, graph=PopulatedFakeGovernedKnowledgeReader(("T1",))
    ).engineering_response

    messages = " ".join(warning.message for warning in response.warnings)
    assert "RIGHT" in messages
    assert "T2" in messages
    assert "not a finding that it is absent" in messages


def test_a_missing_side_raises_uncertainty_to_high() -> None:
    response = _compare(
        COMPARABLE, graph=PopulatedFakeGovernedKnowledgeReader(("T1",))
    ).engineering_response

    assert response.overall_uncertainty.value == "high"


def test_the_limitations_state_the_override_was_applied() -> None:
    response = _compare(
        COMPARABLE, graph=PopulatedFakeGovernedKnowledgeReader(("T1",))
    ).engineering_response

    limitations = next(
        section
        for section in response.sections
        if section.section_type.value == "limitations"
    )
    assert any("INSUFFICIENT_EVIDENCE" in line for line in limitations.body)


# --- 5. Failure attribution ------------------------------------------------


class _SideFailingGraph(PopulatedFakeGovernedKnowledgeReader):
    """
    Fails once a given number of governed reads have succeeded, so a
    left-only or right-only retrieval failure can be provoked
    deterministically.

    The threshold is expressed as "reads already served" rather than as
    a call index, because how many governed reads one side performs is a
    property of the plan (an asset query, plus a quantity traversal when
    the operand asks for relationships) and not something a failure test
    should have to restate.
    """

    def __init__(self, *, fail_after_reads: int) -> None:
        super().__init__(("T1", "T2"))
        self._fail_after_reads = fail_after_reads
        self._served = 0

    def nodes(self, *, states, kind=None, project_id=None, document_id=None):
        if self._served >= self._fail_after_reads:
            raise RuntimeError("governed graph read exploded")

        self._served += 1

        return super().nodes(
            states=states,
            kind=kind,
            project_id=project_id,
            document_id=document_id,
        )


#: How many governed node reads one comparison side performs: the asset
#: designation query, plus the subject resolution of its quantity
#: traversal.
_READS_PER_SIDE = 2


def test_a_left_retrieval_failure_is_attributed_to_the_left_step() -> None:
    result = _compare(graph=_SideFailingGraph(fail_after_reads=0))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.step_type is (
        WorkflowStepType.EXECUTE_LEFT_RETRIEVAL
    )
    assert result.engineering_response is None


def test_a_right_retrieval_failure_is_attributed_to_the_right_step() -> None:
    """The reason retrieval is two steps rather than one: a combined step
    would report these two failures identically."""

    result = _compare(
        graph=_SideFailingGraph(fail_after_reads=_READS_PER_SIDE)
    )

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.step_type is (
        WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL
    )

    statuses = {
        step.step_type: step.status for step in result.execution.step_results
    }
    assert statuses[WorkflowStepType.EXECUTE_LEFT_RETRIEVAL] is (
        WorkflowStepStatus.COMPLETED
    )
    assert statuses[WorkflowStepType.BUILD_COMPARISON_CONTEXT] is (
        WorkflowStepStatus.SKIPPED
    )


def test_a_missing_operand_is_an_invalid_request() -> None:
    result = _compare(request=_comparison_request(comparison_right=None))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.failure.step_type is (
        WorkflowStepType.BUILD_COMPARISON_RETRIEVAL_REQUESTS
    )
    assert "never inferred" in result.failure.detail


def test_a_runtime_failure_uses_the_existing_code() -> None:
    engine = build_test_engine(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=(
                    LLMProviderErrorCategory.AUTHENTICATION_FAILURE
                ),
            ),
        ),
        governed_knowledge_reader=PopulatedFakeGovernedKnowledgeReader(("T1", "T2")),
    )

    result = _execute(engine, _comparison_request())

    assert result.failure.code is EngineeringEngineFailureCode.RUNTIME_FAILURE
    assert result.failure.step_type is WorkflowStepType.INVOKE_LLM_RUNTIME


def test_a_prompt_failure_is_attributed_to_the_comparison_prompt_step() -> None:
    from app.domain.prompt_builder.prompt_builder_exceptions import (
        PromptBuilderError,
    )
    from app.services.engineering_engine import comparison_step_handlers

    def _explode(**_kwargs):
        raise PromptBuilderError("prompt builder refused")

    original = (
        comparison_step_handlers.prompt_builder_service
        .build_comparison_prompt_package
    )
    comparison_step_handlers.prompt_builder_service.build_comparison_prompt_package = (  # noqa: E501
        _explode
    )
    try:
        result = _compare()
    finally:
        comparison_step_handlers.prompt_builder_service.build_comparison_prompt_package = (  # noqa: E501
            original
        )

    assert result.failure.code is (
        EngineeringEngineFailureCode.PROMPT_BUILD_FAILURE
    )
    assert result.failure.step_type is (
        WorkflowStepType.BUILD_COMPARISON_PROMPT
    )


def test_an_invalid_request_fails_before_planning() -> None:
    result = _compare(request=_comparison_request(project_id=0))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.plan is None


# --- 6. The other workflows are unchanged ---------------------------------


def test_a_verification_still_executes_and_carries_no_comparison() -> None:
    engine = _engine("SUPPORTED\nc1 records it.")

    result = _execute(
        engine,
        execution_request(
            intent_type=EngineeringIntentType.VERIFICATION_REQUEST,
            request_text="Verify that protection 87T is present.",
        ),
    )

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.engineering_response.verification is not None
    assert result.engineering_response.comparison is None


@pytest.mark.parametrize(
    "intent_type",
    [
        EngineeringIntentType.KNOWLEDGE_QUERY,
        EngineeringIntentType.ENGINEERING_EXPLANATION,
    ],
)
def test_single_sided_workflows_carry_no_comparison(
    intent_type: EngineeringIntentType,
) -> None:
    result = _execute(_engine(), execution_request(intent_type=intent_type))

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.engineering_response.comparison is None


def test_a_document_lookup_still_executes() -> None:
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
    assert result.engineering_response.comparison is None


# --- 7. End to end from a raw sentence ------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        "Confronta il trasformatore T1 con T2",
        "Quali differenze ci sono tra il montante M1 e M2?",
        "Confronta il cavo C-295 con il cavo C-300",
    ],
)
def test_a_raw_sentence_travels_to_a_comparison(request_text: str) -> None:
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
    assert prepared.comparison_bridge.resolved is True
    assert prepared.execution_request.comparison_left is not None
    assert prepared.execution_request.comparison_right is not None

    result = _execute(_engine(), prepared.execution_request)

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "engineering-comparison"


def test_the_prepared_request_preserves_operand_order() -> None:
    prepared = (
        engineering_request_preparation_service.prepare_engineering_request(
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text="Confronta il trasformatore T1 con T2",
            now=NOW,
        )
    )
    request = prepared.execution_request

    assert request.comparison_left.designation == "T1"
    assert request.comparison_right.designation == "T2"
    # The single-operand retrieval fields stay unset: a comparison has no
    # one retrieval configuration, and filling them with a side's would
    # make that side look like the whole request.
    assert request.retrieval_lexical_terms == ()
    assert request.retrieval_canonical_entity_id is None


def test_preparing_the_same_sentence_twice_is_identical() -> None:
    def _prepare():
        return (
            engineering_request_preparation_service
            .prepare_engineering_request(
                project_id=1,
                engineering_session_id="sess-1",
                conversation_id="conv-1",
                turn_id="turn-1",
                request_text="Confronta il trasformatore T1 con T2",
                now=NOW,
            )
        )

    assert _prepare().execution_request == _prepare().execution_request


def test_a_one_sided_request_is_not_prepared() -> None:
    prepared = (
        engineering_request_preparation_service.prepare_engineering_request(
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text="Confronta il trasformatore T1",
            now=NOW,
        )
    )

    assert prepared.prepared is False
    assert prepared.execution_request is None
    assert prepared.comparison_bridge.resolved is False
