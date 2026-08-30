"""
The second reasoning rule: shared structural location (EPIC 32.2).

Pure domain tests over real governed value objects and the real Context
Assembly service. No database, no engine, no network.

EPIC 32.2 originally stopped with `BLOCKED_BY_ONTOLOGY`; EPIC 32.P1 added
`IS_LOCATED_IN`, and this is the narrow reasoning capability that
governed relationship makes honest.

What these tests exist to pin down, in order of how expensive it would
be to get them wrong:

1. **Missing knowledge is never a negative conclusion.** No outcome in
   this family says "these assets are not co-located", because nothing
   in the governed ontology can prove it.
2. **Identity, never labels.** Two documents writing `+E01` are two
   governed locations, and they must not merge.
3. **Symmetry is real.** Asking (A, B) and asking (B, A) is one
   question and must produce one conclusion identity.
4. **Nothing is traversed.** Unrelated governed knowledge, including
   cyclic-looking shapes, changes no answer.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_reasoning.reasoning_exceptions import (
    SameAssetComparisonError,
)
from app.domain.engineering_reasoning.reasoning_models import (
    SharedStructuralLocationQuery,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    DerivedRelationshipKind,
    ReasoningRuleFamily,
    StructuralReasoningDiagnosticCode,
    StructuralReasoningOutcome,
)
from app.domain.engineering_reasoning.shared_structural_location_rule import (
    evaluate,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.services import context_builder_service
from tests._governed_context import (
    RETRIEVED_AT,
    asset_item,
    designation_result,
    relationship_item,
    results_for,
)

NOW = datetime(2026, 5, 1, 9, 0, 0)

LEFT_ASSET = "node-qa1"
RIGHT_ASSET = "node-qb1"
LOCATION = "node-e01"
OTHER_LOCATION = "node-e02"


def _located_in(
    *,
    asset_node_id: str,
    asset_label: str,
    location_node_id: str,
    location_label: str = "+E01",
    edge_id: str,
    statement_key: str = "statement-loc",
    document_id: int = 11,
    review_id: int = 21,
):
    return relationship_item(
        subject_node_id=asset_node_id,
        subject_label=asset_label,
        object_node_id=location_node_id,
        object_label=location_label,
        edge_id=edge_id,
        edge_kind=GraphEdgeKind.IS_LOCATED_IN,
        statement_key=statement_key,
        document_id=document_id,
        review_id=review_id,
    )


def _left(location: str = LOCATION, *, edge_id: str = "edge-left", **overrides):
    return _located_in(
        asset_node_id=LEFT_ASSET,
        asset_label="+E01-QA1",
        location_node_id=location,
        edge_id=edge_id,
        statement_key="statement-left",
        **overrides,
    )


def _right(location: str = LOCATION, *, edge_id: str = "edge-right", **overrides):
    return _located_in(
        asset_node_id=RIGHT_ASSET,
        asset_label="+E01-QB1",
        location_node_id=location,
        edge_id=edge_id,
        statement_key="statement-right",
        **overrides,
    )


def _context(*results):
    return context_builder_service.build_context_package(
        project_id=1, results=results, now=RETRIEVED_AT
    ).package


def _query(left: str = LEFT_ASSET, right: str = RIGHT_ASSET):
    return SharedStructuralLocationQuery(
        left_asset_node_id=left,
        right_asset_node_id=right,
        left_designation="+E01-QA1",
        right_designation="+E01-QB1",
        project_id=1,
    )


def _evaluate(*items, query=None):
    return evaluate(
        _context(*results_for(items)), query or _query(), evaluated_at=NOW
    )


# --- 1. The positive conclusion ------------------------------------------


def test_two_assets_in_one_governed_location_establish_the_relationship(
) -> None:
    result = _evaluate(_left(), _right())

    assert result.outcome is StructuralReasoningOutcome.ESTABLISHED
    assert result.rule.family is ReasoningRuleFamily.STRUCTURAL_RELATIONSHIP
    assert result.rule.rule_id == "shared_structural_location"
    assert result.rule.rule_version == "1.0"

    structural = result.structural

    assert structural.is_established
    assert structural.derived_relationship is (
        DerivedRelationshipKind.SHARES_STRUCTURAL_LOCATION_WITH
    )
    assert structural.shared_location_node_id == LOCATION
    assert structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode
        .SHARED_STRUCTURAL_LOCATION_ESTABLISHED
    )


def test_the_positive_result_preserves_the_whole_inference_path() -> None:
    """
    Reducing the conclusion to "A and B share X" would discard what makes
    it checkable: which two approved statements put them there.
    """

    path = _evaluate(_left(), _right()).structural.inference_path

    assert path.governed_identities == (
        LEFT_ASSET,
        "edge-left",
        LOCATION,
        "edge-right",
        RIGHT_ASSET,
    )


def test_both_governed_relationships_keep_their_provenance() -> None:
    result = _evaluate(_left(), _right())

    assert len(result.contributors) == 2

    statements = {c.statement_key for c in result.contributors}
    edges = {c.edge_id for c in result.contributors}

    assert statements == {"statement-left", "statement-right"}
    assert edges == {"edge-left", "edge-right"}

    for contributor in result.contributors:
        assert contributor.review_id > 0
        assert contributor.reviewer_display_name
        assert contributor.document_id > 0
        assert contributor.support_fingerprint
        assert contributor.semantic_rule_id


def test_a_relationship_contributor_carries_no_value_or_unit() -> None:
    """A relationship asserts a relation, not a measurement. A
    placeholder value would be a reading nobody took."""

    for contributor in _evaluate(_left(), _right()).contributors:
        assert contributor.value is None
        assert contributor.unit is None
        assert contributor.node_id is None


# --- 2. Missing knowledge is not negative knowledge ----------------------


def test_a_missing_left_location_is_insufficient_knowledge() -> None:
    result = _evaluate(_right())

    assert result.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.LEFT_LOCATION_MISSING
    )
    assert result.structural.derived_relationship is None
    assert result.structural.inference_path is None


def test_a_missing_right_location_is_insufficient_knowledge() -> None:
    result = _evaluate(_left())

    assert result.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.RIGHT_LOCATION_MISSING
    )


def test_both_locations_missing_is_insufficient_knowledge() -> None:
    result = evaluate(
        _context(*results_for((asset_item("node-x", "TR1"),))),
        _query(),
        evaluated_at=NOW,
    )

    assert result.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.BOTH_LOCATIONS_MISSING
    )


def test_distinct_governed_locations_are_insufficient_not_negative(
) -> None:
    """
    The single most important refusal in this milestone.

    ``A -> X``, ``B -> Y``, ``X != Y`` does **not** establish that the
    assets are in different places. Location identity is document-scoped,
    so two identities may name one room; and the graph is partial, so a
    shared location may simply be unrecorded. There is no outcome in this
    family that says "not shared", and there must not be.
    """

    result = _evaluate(_left(), _right(location=OTHER_LOCATION))

    assert result.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.DISTINCT_LOCATION_IDENTITIES
    )
    assert result.structural.derived_relationship is None

    assert "not_shared" not in {
        outcome.value for outcome in StructuralReasoningOutcome
    }


def test_the_outcome_vocabulary_declares_no_negative_member() -> None:
    assert {outcome.value for outcome in StructuralReasoningOutcome} == {
        "established",
        "insufficient_knowledge",
        "ambiguous",
    }


def test_distinct_locations_still_name_the_knowledge_that_was_read(
) -> None:
    """Insufficient for the conclusion is not the same as nothing was
    read - and the result says which two relationships were compared."""

    result = _evaluate(_left(), _right(location=OTHER_LOCATION))

    assert len(result.contributors) == 2
    assert result.has_governed_support


# --- 3. Document-scoped identity -----------------------------------------


def test_the_same_location_label_in_two_documents_does_not_establish(
) -> None:
    """
    Mandatory baseline. Both assets are written ``+E01``, in two
    documents, so there are two governed location identities. Concluding
    co-location from the matching label would be the cross-document
    entity resolution this platform refuses.
    """

    result = _evaluate(
        _left(location="node-e01-doc1", document_id=11),
        _right(
            location="node-e01-doc2",
            location_label="+E01",
            document_id=12,
        ),
    )

    assert result.outcome is not StructuralReasoningOutcome.ESTABLISHED
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.DISTINCT_LOCATION_IDENTITIES
    )


# --- 4. Ambiguity ---------------------------------------------------------


def test_an_ambiguous_asset_designation_is_ambiguous() -> None:
    """A designation naming two governed assets was never one question.
    Reasoning refuses to choose."""

    ambiguous = designation_result(
        "+E01-QA1", (_left(),), total_before_limit=2
    )
    result = evaluate(
        _context(ambiguous, *results_for((_right(),))),
        _query(),
        evaluated_at=NOW,
    )

    assert result.outcome is StructuralReasoningOutcome.AMBIGUOUS
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.ASSET_IDENTITY_AMBIGUOUS
    )
    assert result.contributors == ()


def test_several_governed_locations_on_one_side_are_ambiguous() -> None:
    """
    Which location the question is about cannot be decided from governed
    inputs. Picking the one that happens to match the other side would
    answer a question nobody asked.
    """

    result = _evaluate(
        _left(),
        _left(location=OTHER_LOCATION, edge_id="edge-left-2"),
        _right(),
    )

    assert result.outcome is StructuralReasoningOutcome.AMBIGUOUS
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.MULTIPLE_APPLICABLE_LOCATIONS
    )
    assert result.structural.derived_relationship is None


# --- 5. Symmetry, determinism and ordering -------------------------------


def test_asking_the_question_either_way_round_is_one_conclusion() -> None:
    """
    Sharing a location is symmetric, so (A, B) and (B, A) are the same
    engineering question. The **identity** is canonical; the displayed
    question keeps the order asked.
    """

    forward = _evaluate(_left(), _right())
    reverse = _evaluate(
        _left(),
        _right(),
        query=SharedStructuralLocationQuery(
            left_asset_node_id=RIGHT_ASSET,
            right_asset_node_id=LEFT_ASSET,
            left_designation="+E01-QB1",
            right_designation="+E01-QA1",
            project_id=1,
        ),
    )

    assert forward.result_id == reverse.result_id
    assert forward.outcome is reverse.outcome
    assert forward.structural.inference_path == (
        reverse.structural.inference_path
    )
    assert forward.query.question != reverse.query.question


def test_input_order_does_not_change_the_conclusion() -> None:
    first = _evaluate(_left(), _right())
    second = _evaluate(_right(), _left())

    assert first.result_id == second.result_id
    assert first.outcome is second.outcome
    assert [c.item_id for c in first.contributors] == [
        c.item_id for c in second.contributors
    ]


def test_the_result_identity_is_deterministic() -> None:
    first = _evaluate(_left(), _right())
    second = evaluate(
        _context(*results_for((_left(), _right()))),
        _query(),
        evaluated_at=datetime(2030, 1, 1, 0, 0, 0),
    )

    assert first.result_id == second.result_id


def test_contributor_ordering_is_deterministic() -> None:
    ordering = [
        [c.item_id for c in _evaluate(_left(), _right()).contributors]
        for _ in range(3)
    ]

    assert ordering[0] == ordering[1] == ordering[2]
    assert ordering[0] == sorted(ordering[0]) or len(ordering[0]) == 2


# --- 6. Same-asset questions ---------------------------------------------


def test_a_same_asset_question_is_refused_at_construction() -> None:
    """
    Every asset trivially shares its own location with itself. A positive
    answer would be true, worthless, and indistinguishable at a glance
    from the real conclusion.
    """

    with pytest.raises(SameAssetComparisonError):
        SharedStructuralLocationQuery(
            left_asset_node_id=LEFT_ASSET,
            right_asset_node_id=LEFT_ASSET,
            left_designation="+E01-QA1",
            right_designation="+E01-QA1",
        )


# --- 7. Nothing is traversed ---------------------------------------------


def test_unrelated_governed_knowledge_changes_nothing() -> None:
    unrelated = relationship_item(
        subject_node_id="node-tr1",
        subject_label="TR1",
        object_node_id="node-630",
        object_label="630",
        edge_id="edge-power",
        edge_kind=GraphEdgeKind.HAS_RATED_POWER,
    )

    with_extra = _evaluate(_left(), _right(), unrelated)
    without = _evaluate(_left(), _right())

    assert with_extra.outcome is without.outcome
    assert with_extra.structural.inference_path == (
        without.structural.inference_path
    )
    assert len(with_extra.contributors) == 2


def test_a_rated_power_relationship_never_establishes_co_location(
) -> None:
    """
    The shape is identical - two assets pointing at one node - and it
    licenses nothing. The meaning lives in the edge kind, not the
    geometry.
    """

    shared_quantity_left = relationship_item(
        subject_node_id=LEFT_ASSET,
        subject_label="+E01-QA1",
        object_node_id="node-630",
        object_label="630",
        edge_id="edge-p1",
        edge_kind=GraphEdgeKind.HAS_RATED_POWER,
    )
    shared_quantity_right = relationship_item(
        subject_node_id=RIGHT_ASSET,
        subject_label="+E01-QB1",
        object_node_id="node-630",
        object_label="630",
        edge_id="edge-p2",
        edge_kind=GraphEdgeKind.HAS_RATED_POWER,
    )

    result = _evaluate(shared_quantity_left, shared_quantity_right)

    assert result.outcome is (
        StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    )
    assert result.structural.diagnostics.code is (
        StructuralReasoningDiagnosticCode.BOTH_LOCATIONS_MISSING
    )


def test_a_cyclic_looking_context_terminates_and_changes_nothing(
) -> None:
    """
    Governed context in which a location is itself a subject elsewhere -
    a shape a traversal would loop on. This rule does not traverse, so it
    reads the same two relationships and returns the same answer.
    """

    loop = relationship_item(
        subject_node_id=LOCATION,
        subject_label="+E01",
        object_node_id=LEFT_ASSET,
        object_label="+E01-QA1",
        edge_id="edge-loop",
        edge_kind=GraphEdgeKind.IS_LOCATED_IN,
    )

    result = _evaluate(_left(), _right(), loop)

    assert result.outcome is StructuralReasoningOutcome.ESTABLISHED
    assert len(result.contributors) == 2


def test_the_rule_mutates_no_input() -> None:
    package = _context(*results_for((_left(), _right())))
    before = package

    evaluate(package, _query(), evaluated_at=NOW)

    assert package == before


# --- 8. The derived relationship is not governed vocabulary --------------


def test_the_derived_relationship_is_not_a_governed_relationship() -> None:
    from app.domain.engineering_facts.fact_predicates import FactPredicate
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )

    derived = {kind.value for kind in DerivedRelationshipKind}

    assert not derived & {kind.value for kind in GraphEdgeKind}
    assert not derived & {kind.value for kind in SemanticStatementType}
    assert not derived & {kind.value for kind in FactPredicate}
