"""
Engine tests for the DOCUMENT_LOOKUP workflow (Milestone 23B.1).

This file is the proof the milestone actually asks for: a second workflow,
resolved through the existing registry, planned by the existing planner and
run by the existing executor - **with no LLM provider reachable from it at
all**. Every dependency is an in-memory fake; no database, no network.

The knowledge-query workflow's own tests
(``test_engineering_engine_service.py``) are untouched and still pass, which
is the other half of the same proof.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    EngineeringEngineExecutionStatus,
    EngineeringEngineFailureCode,
    WorkflowStepStatus,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_engine.workflow_definitions import (
    DOCUMENT_LOOKUP_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_index.engineering_index_exceptions import (
    EngineeringIndexError,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseOrigin,
    EngineeringResponseStatus,
)
from app.services.engineering_engine.composition import (
    build_step_handler_registry,
    build_workflow_registry,
)
from tests.domain._document_retrieval_support import entry, metadata
from tests.services._engineering_engine_support import (
    FakeDocumentMetadataPort,
    FakeEngineeringIndexRepository,
    FakeGraphQueryRepository,
    build_test_engine,
    execution_request,
    no_op_sleeper,
    provider_registry,
    runtime_configuration,
)


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


def _lookup_request(**overrides):
    """A classified DOCUMENT_LOOKUP request - the shape a prior
    ``/engineering-intents/classify`` call plus caller-supplied
    designations produces for "Trova il documento del montante T2"."""

    defaults = dict(
        request_text="Trova il documento del montante T2",
        intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
        retrieval_entity_type=None,
        retrieval_lexical_terms=("T2",),
        provider_id=None,
        model_identifier=None,
    )
    defaults.update(overrides)

    return execution_request(**defaults)


def _engine_with(entries=(), records=(), **overrides):
    return build_test_engine(
        engineering_index_repository=FakeEngineeringIndexRepository(
            entries, **overrides
        ),
        document_metadata_port=FakeDocumentMetadataPort(records),
    )


# --- 1. Registration and registry resolution ------------------------------


def test_the_document_lookup_workflow_is_registered() -> None:
    registry = build_workflow_registry()

    assert registry.is_registered(EngineeringIntentType.DOCUMENT_LOOKUP)


def test_the_registry_resolves_document_lookup_to_its_definition() -> None:
    registry = build_workflow_registry()

    definition = registry.resolve(EngineeringIntentType.DOCUMENT_LOOKUP)

    assert definition is DOCUMENT_LOOKUP_WORKFLOW
    assert definition.workflow_type is WorkflowType.DOCUMENT_LOOKUP


def test_selecting_document_lookup_yields_a_selection_not_a_failure() -> None:
    registry = build_workflow_registry()

    result = registry.select_workflow(EngineeringIntentType.DOCUMENT_LOOKUP)

    assert result.selected is True
    assert result.failure is None
    assert result.selection.workflow_id.value == "document-lookup"


def test_the_engine_resolves_the_workflow_through_the_registry() -> None:
    """The engine service selects the workflow with no knowledge of which
    workflow it is - the whole extensibility claim in one assertion."""

    engine = _engine_with()

    selection = engine.select_workflow(_lookup_request())

    assert selection.selected is True
    assert selection.selection.workflow_type is WorkflowType.DOCUMENT_LOOKUP


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
        definition=DOCUMENT_LOOKUP_WORKFLOW, request=_lookup_request()
    )

    assert registry.missing_handlers(plan) == ()


# --- 2. The workflow definition is the declared non-LLM pipeline ----------


def test_the_workflow_declares_no_prompt_context_or_runtime_step() -> None:
    step_types = {step.step_type for step in DOCUMENT_LOOKUP_WORKFLOW.steps}

    assert WorkflowStepType.BUILD_CONTEXT not in step_types
    assert WorkflowStepType.BUILD_PROMPT not in step_types
    assert WorkflowStepType.INVOKE_LLM_RUNTIME not in step_types


def test_the_workflow_reuses_the_shared_terminal_steps() -> None:
    """Response validation and both aggregate-update preparations are the
    same step types, served by the same registered handlers, as the
    knowledge-query workflow's."""

    step_types = [step.step_type for step in DOCUMENT_LOOKUP_WORKFLOW.steps]

    assert step_types == [
        WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
        WorkflowStepType.BUILD_DOCUMENT_RETRIEVAL_REQUEST,
        WorkflowStepType.EXECUTE_DOCUMENT_RETRIEVAL,
        WorkflowStepType.BUILD_DOCUMENT_LOOKUP_RESPONSE,
        WorkflowStepType.VALIDATE_ENGINEERING_RESPONSE,
        WorkflowStepType.PREPARE_CONVERSATION_UPDATE,
        WorkflowStepType.PREPARE_SESSION_UPDATE,
    ]


# --- 3. A successful document lookup, end to end -------------------------


def test_a_document_lookup_executes_to_an_engineering_response() -> None:
    engine = _engine_with([entry()], [metadata()])

    result = _execute(engine, _lookup_request())

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.validation.valid is True
    assert result.selection.workflow_id.value == "document-lookup"
    assert len(result.plan.steps) == len(DOCUMENT_LOOKUP_WORKFLOW.steps)
    assert all(
        step.status is WorkflowStepStatus.COMPLETED
        for step in result.execution.step_results
    )


def test_the_response_carries_structured_document_references() -> None:
    engine = _engine_with([entry()], [metadata()])

    response = _execute(engine, _lookup_request()).engineering_response

    assert len(response.document_references) == 1
    reference = response.document_references[0]
    assert reference.document_id == 10
    assert reference.title == "montante-T2-schema-funzionale.pdf"
    assert reference.document_format == "pdf"
    assert reference.document_category == "functional_schematic"
    assert reference.revision == "02"
    assert reference.relevance.total > 0
    assert reference.page_references == (3,)


def test_the_response_declares_that_no_provider_was_involved() -> None:
    engine = _engine_with([entry()], [metadata()])

    response = _execute(engine, _lookup_request()).engineering_response

    assert response.origin is (
        EngineeringResponseOrigin.DETERMINISTIC_RETRIEVAL
    )
    assert response.metadata.provider_id is None
    assert response.metadata.configured_model_identifier is None
    assert response.version.runtime_version is None


def test_the_graph_is_never_read_during_a_document_lookup() -> None:
    graph = FakeGraphQueryRepository()
    engine = build_test_engine(
        graph_query_repository=graph,
        engineering_index_repository=FakeEngineeringIndexRepository(
            [entry()]
        ),
        document_metadata_port=FakeDocumentMetadataPort([metadata()]),
    )

    _execute(engine, _lookup_request())

    assert graph.list_nodes_calls == 0


def test_aggregate_updates_are_prepared_never_applied() -> None:
    engine = _engine_with([entry()], [metadata()])

    result = _execute(engine, _lookup_request())

    assert result.prepared_updates.conversation_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )
    assert result.prepared_updates.session_update.disposition is (
        AggregateUpdateDisposition.PREPARED
    )


def test_planning_is_deterministic_and_identifies_the_workflow() -> None:
    engine = _engine_with([entry()], [metadata()])
    request = _lookup_request()

    first = _execute(engine, request)
    second = _execute(engine, request)

    assert first.plan.plan_id == second.plan.plan_id
    assert "document-lookup" in first.plan.plan_id.value
    assert first.execution_id == second.execution_id


def test_a_document_lookup_and_a_knowledge_query_get_different_plans() -> None:
    """The plan identity embeds the workflow id, so the same conversation
    turn classified differently is never mistaken for the same plan."""

    engine = _engine_with([entry()], [metadata()])

    lookup = _execute(engine, _lookup_request())
    query = _execute(
        engine,
        execution_request(intent_type=EngineeringIntentType.KNOWLEDGE_QUERY),
    )

    assert lookup.plan.plan_id != query.plan.plan_id


# --- 4. Empty result -----------------------------------------------------


def test_no_matching_document_completes_with_an_empty_response() -> None:
    """"No indexed document mentions this" is an answer, not a failure."""

    engine = _engine_with([entry(identifier="T2")], [metadata()])

    result = _execute(engine, _lookup_request(retrieval_lexical_terms=("99Z",)))

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.failure is None
    assert result.engineering_response.status is (
        EngineeringResponseStatus.EMPTY
    )
    assert result.engineering_response.document_references == ()
    assert result.engineering_response.warnings != ()


# --- 5. Retrieval failure ------------------------------------------------


def test_a_retrieval_failure_becomes_a_typed_engine_failure() -> None:
    engine = _engine_with(
        raises=EngineeringIndexError("the engineering index is unavailable")
    )

    result = _execute(engine, _lookup_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.RETRIEVAL_FAILURE
    )
    assert result.failure.step_type is (
        WorkflowStepType.EXECUTE_DOCUMENT_RETRIEVAL
    )
    assert result.engineering_response is None
    assert result.validation.valid is True


def test_execution_stops_at_the_first_failure_and_skips_the_rest() -> None:
    engine = _engine_with(raises=EngineeringIndexError("unavailable"))

    result = _execute(engine, _lookup_request())

    statuses = [step.status for step in result.execution.step_results]
    assert statuses.count(WorkflowStepStatus.FAILED) == 1
    assert WorkflowStepStatus.COMPLETED not in statuses[
        statuses.index(WorkflowStepStatus.FAILED) :
    ]


def test_an_unexpected_repository_error_is_still_a_typed_failure() -> None:
    """A raw exception never escapes the engine - it becomes
    INTERNAL_EXECUTION_ERROR."""

    engine = _engine_with(raises=RuntimeError("boom"))

    result = _execute(engine, _lookup_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INTERNAL_EXECUTION_ERROR
    )


# --- 6. Invalid request --------------------------------------------------


def test_a_lookup_naming_no_identifier_is_rejected_by_its_own_workflow() -> (
    None
):
    """The engine's shared request validator grows no workflow-specific
    rule: the workflow validates its own inputs, in a real, timed,
    auditable step."""

    engine = _engine_with([entry()], [metadata()])

    result = _execute(engine, _lookup_request(retrieval_lexical_terms=()))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.failure.step_type is (
        WorkflowStepType.BUILD_DOCUMENT_RETRIEVAL_REQUEST
    )


def test_a_structurally_invalid_request_fails_before_any_workflow_runs() -> (
    None
):
    engine = _engine_with([entry()], [metadata()])

    result = _execute(engine, _lookup_request(request_text="   "))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )
    assert result.plan is None
    assert result.execution is None


@pytest.mark.parametrize("limit", [0, -5])
def test_an_out_of_range_retrieval_limit_is_rejected(limit: int) -> None:
    engine = _engine_with([entry()], [metadata()])

    result = _execute(engine, _lookup_request(retrieval_limit=limit))

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST
    )


# --- 7. Missing handler registration -------------------------------------


def test_an_unwired_document_capability_fails_before_any_step_runs() -> None:
    """The workflow is registered, but its handlers were never composed.
    The engine reports the existing typed STEP_HANDLER_NOT_REGISTERED
    failure - it never reroutes the request through another workflow, and
    never pretends the capability exists."""

    engine = build_test_engine(register_document_lookup_handlers=False)

    result = _execute(engine, _lookup_request())

    assert result.status is EngineeringEngineExecutionStatus.FAILED
    assert result.failure.code is (
        EngineeringEngineFailureCode.STEP_HANDLER_NOT_REGISTERED
    )
    assert result.plan is not None
    assert result.execution is None
    assert result.engineering_response is None
    assert result.validation.valid is True


def test_the_workflow_stays_registered_even_when_its_handlers_are_not() -> (
    None
):
    """Registration is static; handler availability is per-composition.
    Conflating the two would make an unwired deployment look like an
    unsupported intent."""

    engine = build_test_engine(register_document_lookup_handlers=False)

    result = _execute(engine, _lookup_request())

    assert result.selection is not None
    assert result.selection.workflow_type is WorkflowType.DOCUMENT_LOOKUP
    assert result.failure.code is not (
        EngineeringEngineFailureCode.UNSUPPORTED_INTENT
    )
