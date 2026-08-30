"""
The Engineering Engine's deterministic reasoning step, end to end
(EPIC 32.1).

Every test here drives the **real** application path: the real engine,
the real workflow plan, the real governed retrieval, the real Context
Assembly, the real rule, the real response builder. Nothing is stubbed
but the governed graph itself (the substrate) and the LLM provider (the
prose). That is the point - a reasoning capability proved only against a
hand-built `ContextPackage` would say nothing about what the platform
actually concludes when somebody asks it a question.

The four outcomes each get a baseline, because they are four different
engineering findings and the whole design rests on never collapsing
them:

    CONSISTENT              the governed values agree
    INCONSISTENT            approved knowledge disagrees with itself
    INSUFFICIENT_KNOWLEDGE  the graph does not answer the question
    AMBIGUOUS               the question named more than one asset

Two further tests hold the boundary that matters most: reasoning
**promotes nothing**, and a workflow that does not declare the reasoning
step does not reason.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringWarningCategory,
)
from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionStatus,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
)

from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphNodeKind,
)

from tests._governed_graph_builder import governed_asset_with_quantity
from tests.services._engineering_engine_support import (
    NOW,
    PopulatedFakeGovernedKnowledgeReader,
    build_test_engine,
    execution_request,
)


class GovernedInstallation(PopulatedFakeGovernedKnowledgeReader):
    """
    A governed graph a test can shape.

    ``PopulatedFakeGovernedKnowledgeReader`` gives every designation
    exactly one rated power, which can only ever produce ``CONSISTENT``.
    This adds the three shapes the other outcomes need: a second value
    for the same asset, a designation with no quantity at all, and a
    designation held by two distinct assets.
    """

    def _add(self, asset, quantity, edge) -> None:
        self._nodes[asset.node_id.value] = asset
        self._nodes[quantity.node_id.value] = quantity
        self._edges[edge.edge_id.value] = edge

    def with_second_value(
        self, designation: str, quantity_label: str, quantity_value: str
    ) -> "GovernedInstallation":
        """A second approved rated power for an asset that already has
        one - two documents, both reviewed, that do not agree."""

        _, quantity, edge = governed_asset_with_quantity(
            designation=designation,
            quantity_label=quantity_label,
            quantity_value=quantity_value,
            document_id=90,
            created_at=NOW,
        )
        # Re-point the second document's edge at the asset already in the
        # graph, so this is one asset with two governed values rather
        # than two assets that happen to share a name.
        asset_node_id = next(
            node.node_id.value
            for node in self._nodes.values()
            if node.kind is GraphNodeKind.ENGINEERING_ASSET
            and node.label == designation
        )
        self._nodes[quantity.node_id.value] = quantity
        self._edges[edge.edge_id.value] = replace(
            edge, subject_node_id=asset_node_id
        )
        return self

    def with_quantity_less_asset(
        self, designation: str
    ) -> "GovernedInstallation":
        """An approved asset nobody recorded a rated power for. The
        commonest real gap, and the one an inference engine is most
        tempted to fill."""

        asset, _, _ = governed_asset_with_quantity(
            designation=designation, document_id=91, created_at=NOW
        )
        self._nodes[asset.node_id.value] = asset
        return self

    def with_duplicate_designation(
        self, designation: str
    ) -> "GovernedInstallation":
        """Two distinct governed assets carrying the same designation -
        never merged, because merging them would invent an equipment
        item nobody approved."""

        self._add(
            *governed_asset_with_quantity(
                designation=designation, document_id=92, created_at=NOW
            )
        )
        return self


def _ask(reader, designation: str, *, answer: str = "SUPPORTED\nAs recorded."):
    engine = build_test_engine(
        outcomes=(FakeInvocationOutcome(text=answer),),
        governed_knowledge_reader=reader,
    )
    request = execution_request(
        request_text=f"Verify the rated power of {designation}.",
        intent_type=EngineeringIntentType.VERIFICATION_REQUEST,
        retrieval_entity_type=None,
        retrieval_lexical_terms=(designation,),
        retrieval_include_neighborhood=True,
        retrieval_neighborhood_depth=1,
    )

    result = asyncio.run(engine.execute(request))
    assert result.status is EngineeringEngineExecutionStatus.COMPLETED, (
        result.failure
    )
    return result


def _reasoning(result):
    reasoning = result.engineering_response.derived_reasoning
    assert reasoning is not None
    return reasoning


def _warning_categories(result) -> set[EngineeringWarningCategory]:
    return {
        warning.category for warning in result.engineering_response.warnings
    }


# --- The four outcomes ---------------------------------------------------


def test_agreeing_governed_values_are_reported_consistent() -> None:
    result = _ask(PopulatedFakeGovernedKnowledgeReader(("87T",)), "87T")
    reasoning = _reasoning(result)

    assert reasoning.outcome is ReasoningOutcome.CONSISTENT
    assert reasoning.rule_id == "governed_quantity_consistency"
    assert reasoning.rule_version == "1.0"
    # Nothing for a reader to act on, so nothing is warned about.
    assert (
        EngineeringWarningCategory.CONFLICTING_KNOWLEDGE
        not in _warning_categories(result)
    )


def test_disagreeing_governed_values_are_reported_inconsistent() -> None:
    """
    Two approved documents, two different rated powers, one asset.

    This is the finding the whole milestone exists to produce: the
    conflict is *inside reviewed knowledge*, so it cannot be resolved by
    retrieving better or asking the model again. Somebody has to fix the
    source.
    """

    reader = GovernedInstallation(("87T",)).with_second_value(
        "87T", "800 kVA", "800.0"
    )
    result = _ask(reader, "87T")
    reasoning = _reasoning(result)

    assert reasoning.outcome is ReasoningOutcome.INCONSISTENT
    assert reasoning.diagnostic_code is ReasoningDiagnosticCode.VALUES_CONFLICT
    assert len(reasoning.supports) == 2

    assert (
        EngineeringWarningCategory.CONFLICTING_KNOWLEDGE
        in _warning_categories(result)
    )


def test_a_missing_governed_quantity_is_insufficient_not_a_conclusion() -> (
    None
):
    """
    The gap is reported as a gap.

    "The graph does not record a rated power for this asset" must never
    become "this asset is consistent" - an absence of contradiction is
    not agreement, and treating it as such is how a real installation
    gets signed off on something nobody looked at.
    """

    reader = GovernedInstallation(()).with_quantity_less_asset("87T")
    result = _ask(reader, "87T")
    reasoning = _reasoning(result)

    assert reasoning.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    assert reasoning.supports == ()

    assert (
        EngineeringWarningCategory.INSUFFICIENT_EVIDENCE
        in _warning_categories(result)
    )


def test_a_duplicated_designation_is_reported_ambiguous() -> None:
    """
    Two governed assets share a designation and were not merged, so the
    question has more than one subject.

    No conclusion is derived. Picking one of them would be inventing an
    engineering finding about a piece of equipment the asker may not have
    meant.
    """

    reader = GovernedInstallation(("87T",)).with_duplicate_designation("87T")
    result = _ask(reader, "87T")
    reasoning = _reasoning(result)

    assert reasoning.outcome is ReasoningOutcome.AMBIGUOUS
    assert (
        reasoning.diagnostic_code is ReasoningDiagnosticCode.AMBIGUOUS_SUBJECT
    )
    assert reasoning.supports == ()

    assert (
        EngineeringWarningCategory.AMBIGUOUS_KNOWLEDGE
        in _warning_categories(result)
    )


# --- Traceability (AF-REASON-002) ---------------------------------------


def test_a_conclusion_names_the_governed_facts_it_came_from() -> None:
    """A reader can walk from the conclusion back to the approved
    statement without trusting the reasoner."""

    result = _ask(PopulatedFakeGovernedKnowledgeReader(("87T",)), "87T")
    reasoning = _reasoning(result)

    support = reasoning.supports[0]
    assert support.node_id
    assert support.edge_id
    assert support.statement_key
    assert support.review_id > 0
    assert support.reviewer_display_name
    assert support.document_id > 0
    # Reported exactly as governed: no rounding, no unit conversion.
    assert support.value == "630.0"
    assert support.unit == "kVA"


def test_the_same_governed_knowledge_yields_the_same_conclusion_id() -> None:
    """Determinism, proved through the whole application path rather
    than on the identity function alone."""

    first = _reasoning(_ask(PopulatedFakeGovernedKnowledgeReader(("87T",)), "87T"))
    second = _reasoning(
        _ask(PopulatedFakeGovernedKnowledgeReader(("87T",)), "87T")
    )

    assert first.result_id == second.result_id
    assert first.outcome is second.outcome


# --- AF-REASON-003: nothing is promoted ---------------------------------


def test_reasoning_promotes_nothing_into_governed_knowledge() -> None:
    """
    The governed graph is byte-identical before and after an execution
    that reasoned - including the inconsistent case, which is the one a
    future "just record the conclusion" change would target first.

    A conclusion has no Human Review behind it. Writing one into the
    graph would fabricate governance, and provenance a caller asserts is
    not provenance.
    """

    reader = GovernedInstallation(("87T",)).with_second_value(
        "87T", "800 kVA", "800.0"
    )

    before_nodes = deepcopy(reader._nodes)
    before_edges = deepcopy(reader._edges)

    result = _ask(reader, "87T")
    assert _reasoning(result).outcome is ReasoningOutcome.INCONSISTENT

    assert reader._nodes == before_nodes
    assert reader._edges == before_edges


def test_a_workflow_that_does_not_reason_reports_no_conclusion() -> None:
    """
    Reasoning is a capability a workflow opts into. A knowledge query
    runs the same retrieval and the same Context Assembly and comes back
    with ``derived_reasoning`` of ``None`` - not an empty conclusion, and
    not a ``CONSISTENT`` one it never derived.
    """

    engine = build_test_engine(
        outcomes=(FakeInvocationOutcome(text="The rated power is 630 kVA."),),
        governed_knowledge_reader=PopulatedFakeGovernedKnowledgeReader(
            ("87T",)
        ),
    )
    request = execution_request(
        request_text="What is the rated power of 87T?",
        intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        retrieval_lexical_terms=("87T",),
    )

    result = asyncio.run(engine.execute(request))

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED
    assert result.engineering_response.derived_reasoning is None
