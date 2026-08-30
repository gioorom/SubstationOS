"""
Shared structural location reasoning, through the real engine
(EPIC 32.2).

The whole path, driven end to end with a fake LLM and a fake governed
reader: request -> governed retrieval -> context assembly -> deterministic
reasoning -> prompt builder -> engineering response.

The three claims these tests exist to protect:

1. **The model never decides the answer.** The conclusion is computed by
   a versioned rule before the provider is invoked, and the fake
   provider returns text that contradicts nothing because it is never
   consulted about the question.
2. **A derived conclusion never becomes governed knowledge.** The
   governed graph, and every other authoritative store the engine can
   reach, is identical before and after - including for the positive
   case, which is the one a future change is most tempted to persist.
3. **The response keeps them apart.** Governed relationships appear as
   references; the conclusion appears as derived reasoning. Neither
   appears as the other.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionStatus,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    DerivedRelationshipKind,
    ReasoningRuleFamily,
    StructuralReasoningDiagnosticCode,
    StructuralReasoningOutcome,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringWarningCategory,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
)
from tests._governed_graph_builder import governed_asset_in_location
from tests.services._engineering_engine_support import (
    NOW,
    PopulatedFakeGovernedKnowledgeReader,
    build_test_engine,
    execution_request,
)

LEFT = "+E01-QA1"
RIGHT = "+E01-QB1"


class GovernedInstallation(PopulatedFakeGovernedKnowledgeReader):
    """A governed graph carrying structural locations."""

    def with_asset_in_location(
        self,
        designation: str,
        *,
        location: str = "+E01",
        location_entity_key: str | None = None,
        document_id: int = 1,
    ) -> "GovernedInstallation":
        asset, location_node, edge = governed_asset_in_location(
            designation=designation,
            location_designation=location,
            location_entity_key=location_entity_key,
            document_id=document_id,
            created_at=NOW,
        )
        self._nodes[asset.node_id.value] = asset
        self._nodes[location_node.node_id.value] = location_node
        self._edges[edge.edge_id.value] = edge
        return self

    def with_located_asset_only(
        self, designation: str, *, document_id: int = 1
    ) -> "GovernedInstallation":
        """An approved asset nobody recorded a location for - the
        commonest real gap, and the one an inference engine is most
        tempted to fill."""

        asset, _, _ = governed_asset_in_location(
            designation=designation,
            document_id=document_id,
            created_at=NOW,
        )
        self._nodes[asset.node_id.value] = asset
        return self


def _empty() -> GovernedInstallation:
    return GovernedInstallation(designations=())


def _colocated() -> GovernedInstallation:
    """Two governed assets, one governed location, two approved
    relationships."""

    return (
        _empty()
        .with_asset_in_location(LEFT, location_entity_key="shared-e01")
        .with_asset_in_location(RIGHT, location_entity_key="shared-e01")
    )


def _ask(
    reader,
    left: str = LEFT,
    right: str = RIGHT,
    *,
    answer: str = "As recorded.",
):
    engine = build_test_engine(
        outcomes=(FakeInvocationOutcome(text=answer),),
        governed_knowledge_reader=reader,
    )
    request = execution_request(
        request_text=(
            f"Are {left} and {right} in the same structural location?"
        ),
        intent_type=(
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ),
        retrieval_entity_type=None,
        retrieval_lexical_terms=(left, right),
    )

    result = asyncio.run(engine.execute(request))

    assert result.status is EngineeringEngineExecutionStatus.COMPLETED, (
        result.failure
    )
    return result


def _reasoning_over(reader):
    """
    The conclusion, built through the **real** retrieval and context
    services over the same governed reader the engine used.

    The engine result exposes the engineering response rather than the
    prompt, so a prompt assertion reassembles the same governed context
    the engine assembled and runs the same rule over it - no fixture, no
    stub, and nothing the production path could not produce.
    """

    from datetime import datetime

    from app.domain.engineering_reasoning.reasoning_models import (
        SharedStructuralLocationQuery,
    )
    from app.domain.engineering_reasoning import (
        shared_structural_location_rule,
    )
    from app.domain.governed_retrieval.governed_retrieval_factory import (
        GovernedRetrievalQueryFactory,
    )
    from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
        RetrievalScope,
    )
    from app.services import context_builder_service
    from app.services import governed_retrieval_service

    at = datetime(2026, 1, 1, 5, 0, 0)
    results = tuple(
        governed_retrieval_service.retrieve(reader, query, now=at)
        for designation in (LEFT, RIGHT)
        for query in (
            GovernedRetrievalQueryFactory.asset_by_designation(
                designation=designation,
                scope=RetrievalScope.CURRENT_ONLY,
                limit=20,
                project_id=1,
            ),
            GovernedRetrievalQueryFactory.quantity_for_asset(
                designation=designation,
                scope=RetrievalScope.CURRENT_ONLY,
                limit=20,
                project_id=1,
            ),
        )
    )
    package = context_builder_service.build_context_package(
        project_id=1, results=results, now=at
    ).package
    subjects = sorted(
        {
            item.result.relationship.subject.node_id
            for item in package.selected_items
            if item.result.relationship is not None
            and item.result.relationship.kind is GraphEdgeKind.IS_LOCATED_IN
        }
    )

    return shared_structural_location_rule.evaluate(
        package,
        SharedStructuralLocationQuery(
            left_asset_node_id=subjects[0],
            right_asset_node_id=subjects[1],
            left_designation=LEFT,
            right_designation=RIGHT,
            project_id=1,
        ),
        evaluated_at=NOW,
    )


def _reasoning(result):
    reasoning = result.engineering_response.derived_reasoning
    assert reasoning is not None
    return reasoning


# --- CASE A: established --------------------------------------------------


def test_two_governed_assets_in_one_location_are_reported_established(
) -> None:
    reasoning = _reasoning(_ask(_colocated()))

    assert reasoning.outcome is StructuralReasoningOutcome.ESTABLISHED
    assert reasoning.rule_family is (
        ReasoningRuleFamily.STRUCTURAL_RELATIONSHIP
    )
    assert reasoning.rule_id == "shared_structural_location"
    assert reasoning.rule_version == "1.0"
    assert reasoning.diagnostic_code is (
        StructuralReasoningDiagnosticCode
        .SHARED_STRUCTURAL_LOCATION_ESTABLISHED
    )


def test_the_established_conclusion_names_its_derived_relationship(
) -> None:
    """A consumer must be able to tell a structural conclusion from a
    quantity one by **type**, not by reading prose."""

    structural = _reasoning(_ask(_colocated())).structural

    assert structural is not None
    assert structural.derived_relationship is (
        DerivedRelationshipKind.SHARES_STRUCTURAL_LOCATION_WITH
    )
    assert structural.shared_location_node_id
    assert structural.shared_location_label == "+E01"
    assert len(structural.inference_path) == 5


def test_the_conclusion_names_the_governed_relationships_it_rests_on(
) -> None:
    reasoning = _reasoning(_ask(_colocated()))

    assert len(reasoning.supports) == 2

    for support in reasoning.supports:
        assert support.edge_id
        assert support.statement_key
        assert support.review_id > 0
        assert support.document_id > 0


def test_an_established_conclusion_raises_no_warning() -> None:
    result = _ask(_colocated())

    assert EngineeringWarningCategory.INSUFFICIENT_EVIDENCE not in {
        warning.category
        for warning in result.engineering_response.warnings
    }


def test_the_prompt_separates_governed_knowledge_from_the_conclusion(
) -> None:
    """
    The model is handed the governed relationships **and** the finished
    conclusion, in different sections, with the derived one labelled as
    derived. It is never asked to work out whether they share a location.
    """

    from app.domain.prompt_builder.prompt_composition import (
        build_derived_reasoning,
    )

    derived = build_derived_reasoning(_reasoning_over(_colocated()))

    assert derived.enabled

    text = "\n".join(derived.content)

    assert "DERIVED CONCLUSION" in text
    assert "NOT a reviewed engineering statement" in text
    assert "shares_structural_location_with" in text
    assert "shared_structural_location@1.0" in text


def test_the_prompt_wording_never_claims_separation() -> None:
    """
    The wording handed to the model matters as much as the outcome. A
    model told only "insufficient" writes "they are in different
    places", because that is what the word suggests in English.
    """

    from app.domain.prompt_builder.prompt_composition import (
        _STRUCTURAL_OUTCOME_MEANING,
    )

    insufficient = _STRUCTURAL_OUTCOME_MEANING[
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    ].lower()

    assert "not a finding that they are in different places" in insufficient
    assert "do not report them as separate" in insufficient

    established = _STRUCTURAL_OUTCOME_MEANING[
        StructuralReasoningOutcome.ESTABLISHED
    ].lower()

    assert "does not say they are connected" in established


# --- CASE B: insufficient knowledge ---------------------------------------


def test_a_missing_governed_location_is_insufficient_not_negative(
) -> None:
    reader = (
        _empty()
        .with_asset_in_location(LEFT)
        .with_located_asset_only(RIGHT, document_id=2)
    )

    reasoning = _reasoning(_ask(reader))

    assert reasoning.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert reasoning.structural.derived_relationship is None


def test_the_insufficient_warning_does_not_claim_separation() -> None:
    """
    The wording matters as much as the outcome. A reader told only
    "insufficient" concludes "they are apart"; the warning says
    explicitly that it is not that finding.
    """

    reader = (
        _empty()
        .with_asset_in_location(LEFT)
        .with_located_asset_only(RIGHT, document_id=2)
    )
    result = _ask(reader)
    messages = " ".join(
        warning.message for warning in result.engineering_response.warnings
    )

    assert EngineeringWarningCategory.INSUFFICIENT_EVIDENCE in {
        warning.category
        for warning in result.engineering_response.warnings
    }
    assert "not a finding that they are apart" in messages.lower()
    assert EngineeringWarningCategory.CONFLICTING_KNOWLEDGE not in {
        warning.category
        for warning in result.engineering_response.warnings
    }


def test_two_documents_naming_the_same_location_do_not_establish() -> None:
    """
    Document-scoped identity, end to end. Both assets are written
    ``+E01``, in two documents, so there are two governed locations.
    """

    reader = (
        _empty()
        .with_asset_in_location(LEFT, document_id=1)
        .with_asset_in_location(RIGHT, document_id=2)
    )

    reasoning = _reasoning(_ask(reader))

    assert reasoning.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert reasoning.diagnostic_code is (
        StructuralReasoningDiagnosticCode.DISTINCT_LOCATION_IDENTITIES
    )


# --- CASE C: ambiguous ----------------------------------------------------


def test_a_duplicated_designation_is_reported_ambiguous() -> None:
    reader = (
        _colocated()
        .with_asset_in_location(LEFT, location="+E09", document_id=77)
    )

    reasoning = _reasoning(_ask(reader))

    assert reasoning.outcome is StructuralReasoningOutcome.AMBIGUOUS
    assert reasoning.structural.derived_relationship is None
    assert EngineeringWarningCategory.AMBIGUOUS_KNOWLEDGE in {
        warning.category
        for warning in _ask(reader).engineering_response.warnings
    }


# --- Mutation safety ------------------------------------------------------


def test_a_positive_conclusion_leaves_governed_knowledge_untouched(
) -> None:
    """
    The case a future change is most tempted to persist.

    Snapshotted by deep copy of the whole governed store rather than by
    counting rows: a conclusion written into an existing node's fields
    would keep the counts identical and change the knowledge.
    """

    reader = _colocated()
    nodes_before = deepcopy(reader._nodes)
    edges_before = deepcopy(reader._edges)

    result = _ask(reader)

    assert _reasoning(result).outcome is (
        StructuralReasoningOutcome.ESTABLISHED
    )
    assert reader._nodes == nodes_before
    assert reader._edges == edges_before


def test_no_derived_relationship_becomes_a_governed_edge() -> None:
    reader = _colocated()

    _ask(reader)

    kinds = {edge.kind for edge in reader._edges.values()}

    assert kinds == {GraphEdgeKind.IS_LOCATED_IN}
    assert DerivedRelationshipKind.SHARES_STRUCTURAL_LOCATION_WITH.value not in {
        kind.value for kind in kinds
    }


def test_the_conclusion_is_not_reported_as_governed_knowledge() -> None:
    result = _ask(_colocated())
    reasoning = _reasoning(result)

    assert reasoning.is_governed_knowledge is False
    assert reasoning.structural.is_governed_knowledge is False

    # References carry governed knowledge only - the conclusion is not
    # among them.
    for reference in result.engineering_response.references:
        assert reference.statement_key != reasoning.result_id


# --- Determinism ----------------------------------------------------------


def test_the_same_governed_knowledge_yields_the_same_conclusion_id(
) -> None:
    first = _reasoning(_ask(_colocated()))
    second = _reasoning(_ask(_colocated()))

    assert first.result_id == second.result_id


def test_asking_in_the_other_order_is_the_same_conclusion() -> None:
    forward = _reasoning(_ask(_colocated(), LEFT, RIGHT))
    reverse = _reasoning(_ask(_colocated(), RIGHT, LEFT))

    assert forward.result_id == reverse.result_id
    assert forward.outcome is reverse.outcome
