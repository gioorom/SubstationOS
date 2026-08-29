"""
Service tests for Engineering Request Preparation (Milestone 23B.3),
including the end-to-end path this milestone exists to create:

    raw request text -> classification -> bridge -> engine -> workflow

with **no caller-supplied retrieval criteria at any point**.

Every dependency is in-memory or faked; no real provider is called.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionStatus,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    RetrievalBridgeFailureCode,
)
from app.services import engineering_request_preparation_service
from app.services.engineering_engine.governed_retrieval_step_handlers import (
    BuildGovernedRetrievalPlanStepHandler,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from tests.domain._document_retrieval_support import entry, metadata
from tests.services._engineering_engine_support import (
    FakeDocumentMetadataPort,
    FakeEngineeringIndexRepository,
    build_test_engine,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


def _prepare(request_text: str, *, project_id: int = 1, **overrides):
    defaults = dict(
        project_id=project_id,
        engineering_session_id="sess-1",
        conversation_id="conv-1",
        turn_id="turn-1",
        request_text=request_text,
        now=NOW,
    )
    defaults.update(overrides)

    return engineering_request_preparation_service.prepare_engineering_request(
        **defaults
    )


# --- The prepared execution request ----------------------------------------


def test_a_raw_request_becomes_a_complete_engine_execution_request() -> None:
    prepared = _prepare("Quale TA è installato sul cavo C-295?")

    assert prepared.prepared is True
    request = prepared.execution_request
    assert request is not None
    assert request.project_id == 1
    assert request.intent_type is EngineeringIntentType.KNOWLEDGE_QUERY
    assert request.engineering_intent_id
    assert request.request_text == "Quale TA è installato sul cavo C-295?"
    assert request.executed_at == NOW


def test_the_derived_criteria_reach_the_execution_request() -> None:
    prepared = _prepare("Quale TA è installato sul cavo C-295?")
    request = prepared.execution_request

    assert request.retrieval_canonical_entity_id == "CABLE:C-295"
    assert request.retrieval_lexical_terms == ()
    assert request.retrieval_include_neighborhood is False
    # Never a bare entity type: Structured Retrieval's ENTITY_LOOKUP mode
    # admits the canonical-id criterion only. The resolved type is
    # reported on the designation instead.
    assert request.retrieval_entity_type is None
    assert prepared.bridge.designations[0].entity_type == "CABLE"


def test_an_explanation_carries_its_policy_driven_neighborhood() -> None:
    prepared = _prepare("Spiegami il funzionamento della protezione 87T")
    request = prepared.execution_request

    assert request.intent_type is (
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )
    assert request.retrieval_lexical_terms == ("87T",)
    assert request.retrieval_include_neighborhood is True
    assert request.retrieval_neighborhood_depth == 1


def test_a_document_lookup_carries_its_index_search_terms() -> None:
    prepared = _prepare("Trova il documento del montante T2")
    request = prepared.execution_request

    assert request.intent_type is EngineeringIntentType.DOCUMENT_LOOKUP
    assert request.retrieval_lexical_terms == ("T2",)
    assert request.retrieval_canonical_entity_id is None


def test_runtime_selection_passes_through_but_criteria_never_do() -> None:
    """The only caller-supplied parameters are provenance and runtime
    selection - there is no way to pass retrieval criteria through this
    service at all."""

    prepared = _prepare(
        "Trova il documento del montante T2",
        provider_id="fake",
        model_identifier="fake-model",
        request_correlation_id="corr-1",
    )
    request = prepared.execution_request

    assert request.provider_id == "fake"
    assert request.model_identifier == "fake-model"
    assert request.request_correlation_id == "corr-1"

    signature = (
        engineering_request_preparation_service.prepare_engineering_request
    ).__code__.co_varnames
    assert not any("retrieval" in name for name in signature)


# --- The mode the bridge declares is the mode the engine derives -----------


@pytest.mark.parametrize(
    ("request_text", "expected_designations"),
    [
        ("Quale TA è installato sul cavo C-295?", ["C-295"]),
        ("Quale TA è installato sul montante T2?", ["T2"]),
        ("Spiegami il funzionamento della protezione 87T", ["87T"]),
    ],
)
def test_the_engine_resolves_exactly_the_designations_the_bridge_evidenced(
    request_text: str, expected_designations: list[str]
) -> None:
    """
    The invariant that makes the bridge honest, restated for governed
    retrieval (EPIC 31.2): the designations the bridge found in the
    request text are exactly the designations the engine asks the
    governed graph about - no more, and none invented.

    It used to be stated as "the mode the bridge declares is the mode
    the engine derives". Governed retrieval has no modes: a designation
    resolves to governed assets or it resolves to nothing, so the
    invariant is now about *what is asked*, which is the thing that
    actually mattered.
    """

    prepared = _prepare(request_text)

    context = asyncio.run(
        BuildGovernedRetrievalPlanStepHandler().execute(
            None,
            WorkflowExecutionContext(
                execution_request=prepared.execution_request
            ),
        )
    )

    asked = [
        query.designation
        for query in context.retrieval_request.queries
        if query.query_type.value == "asset_by_designation"
    ]

    assert asked == expected_designations


# --- Unresolvable requests --------------------------------------------------


def test_an_under_specified_request_is_not_prepared() -> None:
    prepared = _prepare("Spiegami il funzionamento del trasformatore")

    assert prepared.prepared is False
    assert prepared.execution_request is None
    assert prepared.bridge.failure.code is (
        RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE
    )


def test_an_unresolvable_request_still_reports_its_classification() -> None:
    """A refusal is as inspectable as a success."""

    prepared = _prepare("Spiegami il funzionamento del trasformatore")

    assert prepared.intent.intent_type is (
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )
    assert prepared.bridge.resolved is False


def test_an_unmapped_intent_is_not_prepared() -> None:
    """Drawing requests have no workflow, so preparation refuses rather
    than deriving criteria nobody can execute."""

    prepared = _prepare("Disegna lo schema del cavo C-295")

    assert prepared.prepared is False
    assert prepared.bridge.failure.code is (
        RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING
    )


# --- End to end: raw request -> prepared request -> engine -> workflow ------


def _execute(engine, request):
    return asyncio.run(engine.execute(request))


def test_a_raw_knowledge_query_travels_to_a_completed_execution() -> None:
    """The gap this milestone closes, proved in one test: nothing but the
    engineer's own sentence goes in, and a completed workflow comes out."""

    prepared = _prepare(
        "Quale TA è installato sul cavo C-295?",
        provider_id="fake",
        model_identifier="fake-model",
    )
    engine = build_test_engine()

    result = _execute(engine, prepared.execution_request)

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "knowledge-query"
    assert result.engineering_response is not None


def test_a_raw_explanation_travels_to_a_completed_execution() -> None:
    prepared = _prepare(
        "Spiegami il funzionamento della protezione 87T",
        provider_id="fake",
        model_identifier="fake-model",
    )
    engine = build_test_engine()

    result = _execute(engine, prepared.execution_request)

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "engineering-explanation"


def test_a_raw_document_lookup_travels_to_a_completed_execution() -> None:
    prepared = _prepare("Trova il documento del montante T2")
    engine = build_test_engine(
        engineering_index_repository=FakeEngineeringIndexRepository(
            [entry(identifier="T2")]
        ),
        document_metadata_port=FakeDocumentMetadataPort([metadata()]),
    )

    result = _execute(engine, prepared.execution_request)

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.selection.workflow_id.value == "document-lookup"
    assert len(result.engineering_response.document_references) == 1


def test_the_whole_path_is_reproducible() -> None:
    first = _prepare("Quale TA è installato sul cavo C-295?")
    second = _prepare("Quale TA è installato sul cavo C-295?")

    assert first.execution_request == second.execution_request
    assert first.bridge == second.bridge
