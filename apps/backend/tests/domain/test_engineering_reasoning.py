"""
The deterministic engineering reasoning baseline (EPIC 32.1).

Fifteen scenarios over **real governed domain objects** - genuine
`GovernedRetrievalResult`s assembled by the real Context Assembly - so
nothing here can pass against a shape the production path could not
produce.

The four outcomes are asserted as **distinct**, because the whole value
of the vocabulary is that `INCONSISTENT`, `INSUFFICIENT_KNOWLEDGE` and
`AMBIGUOUS` are three different engineering situations with three
different fixes.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.domain.engineering_reasoning.quantity_consistency_rule import (
    QUANTITY_CONSISTENCY_RULE,
    evaluate,
)
from app.domain.engineering_reasoning.reasoning_models import (
    QuantityConsistencyQuery,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.services import context_builder_service
from tests._governed_context import (
    asset_item,
    designation_result,
    quantity_item,
    quantity_result,
)

PROJECT_ID = 3
NOW = datetime(2026, 6, 1, 9, 0, 0)

RATED_POWER = GraphEdgeKind.HAS_RATED_POWER


def _query(designation: str = "TR1") -> QuantityConsistencyQuery:
    return QuantityConsistencyQuery(
        subject_designation=designation,
        quantity_kind=RATED_POWER,
        project_id=PROJECT_ID,
    )


def _context(*results):
    return context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=tuple(results), now=NOW
    ).package


def _quantity(
    label: str,
    *,
    unit: str = "kVA",
    node: str = "node-q1",
    edge: str = "edge-1",
    statement: str = "statement-q1",
    document_id: int = 11,
):
    return quantity_item(
        subject_node_id="node-tr1",
        subject_label="TR1",
        quantity_node_id=node,
        quantity_label=label,
        unit=unit,
        edge_id=edge,
        statement_key=statement,
        document_id=document_id,
        project_id=PROJECT_ID,
    )


def _subject(*, matches: int = 1):
    """A designation query resolving to ``matches`` governed assets."""

    items = tuple(
        asset_item(
            f"node-tr1-{index}",
            "TR1",
            statement_key=f"statement-a{index}",
            document_id=11 + index,
            project_id=PROJECT_ID,
        )
        for index in range(matches)
    )

    return designation_result("TR1", items, project_id=PROJECT_ID)


def _evaluate(*results, query: QuantityConsistencyQuery | None = None):
    return evaluate(
        _context(*results), query or _query(), evaluated_at=NOW
    )


# --- 1-3. The three knowledge situations --------------------------------


def test_a_single_governed_value_is_consistent() -> None:
    """
    One approved value cannot disagree with itself.

    The diagnostic is `SINGLE_VALUE` rather than `VALUES_EQUAL`, so a
    reader can tell "one value, nothing to compare" from "several values
    that agree" - the outcome is the same, the engineering situation is
    not.
    """

    result = _evaluate(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )

    assert result.outcome is ReasoningOutcome.CONSISTENT
    assert result.diagnostics.code is ReasoningDiagnosticCode.SINGLE_VALUE
    assert result.diagnostics.distinct_value_count == 1


def test_two_equal_governed_values_are_consistent() -> None:
    result = _evaluate(
        _subject(),
        quantity_result(
            "TR1",
            (
                _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
                _quantity("630 kVA", node="node-b", edge="edge-b", statement="s-b"),
            ),
        ),
    )

    assert result.outcome is ReasoningOutcome.CONSISTENT
    assert result.diagnostics.code is ReasoningDiagnosticCode.VALUES_EQUAL
    assert len(result.contributors) == 2


def test_two_unequal_governed_values_are_inconsistent() -> None:
    """
    **The finding this milestone exists to make.** Two engineers approved
    two statements that cannot both describe the same transformer, and
    until now nothing said so.
    """

    result = _evaluate(
        _subject(),
        quantity_result(
            "TR1",
            (
                _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
                _quantity("800 kVA", node="node-b", edge="edge-b", statement="s-b"),
            ),
        ),
    )

    assert result.outcome is ReasoningOutcome.INCONSISTENT
    assert result.diagnostics.code is ReasoningDiagnosticCode.VALUES_CONFLICT
    assert result.diagnostics.distinct_value_count == 2


# --- 4-5. Absence and ambiguity are not falsity -------------------------


def test_no_governed_quantity_is_insufficient_knowledge_not_consistent() -> (
    None
):
    """
    **Absence is never consistency.** An empty graph must not be able to
    certify a substation by finding no contradiction in it.
    """

    result = _evaluate(_subject())

    assert result.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    assert result.outcome is not ReasoningOutcome.CONSISTENT
    assert (
        result.diagnostics.code
        is ReasoningDiagnosticCode.NO_REQUIRED_QUANTITY
    )


def test_an_ambiguous_subject_is_ambiguous_not_inconsistent() -> None:
    """
    Two governed assets share the designation `TR1`. Reasoning refuses
    both available shortcuts: it does not pick one, and it does not
    compare across them and report a conflict between two different
    transformers.
    """

    result = _evaluate(
        _subject(matches=2),
        quantity_result(
            "TR1",
            (
                _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
                _quantity("800 kVA", node="node-b", edge="edge-b", statement="s-b"),
            ),
        ),
    )

    assert result.outcome is ReasoningOutcome.AMBIGUOUS
    assert result.outcome is not ReasoningOutcome.INCONSISTENT
    assert result.diagnostics.code is ReasoningDiagnosticCode.AMBIGUOUS_SUBJECT
    assert result.diagnostics.candidate_subject_count == 2


def test_no_governed_subject_is_insufficient_knowledge() -> None:
    result = _evaluate(designation_result("TR1", (), project_id=PROJECT_ID))

    assert result.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    assert result.diagnostics.code is ReasoningDiagnosticCode.NO_SUBJECT


# --- 6. Cross-document identity is never merged -------------------------


def test_the_same_designation_in_two_documents_is_not_silently_merged() -> (
    None
):
    """
    Two documents each designating `TR1` produce two governed assets, and
    the question becomes ambiguous rather than being answered about a
    merged one. Cross-document entity resolution remains out of scope.
    """

    result = _evaluate(_subject(matches=2))

    assert result.outcome is ReasoningOutcome.AMBIGUOUS
    assert result.contributors == ()


# --- 7-8. Provenance survives on both material outcomes -----------------


def test_a_consistent_result_carries_complete_governed_provenance() -> None:
    result = _evaluate(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )

    contributor = result.contributors[0]

    assert contributor.statement_key
    assert contributor.review_id > 0
    assert contributor.reviewer_display_name
    assert contributor.support_fingerprint
    assert contributor.document_id > 0
    assert contributor.content_checksum
    assert contributor.semantic_rule_id
    assert contributor.node_id and contributor.edge_id


def test_an_inconsistent_result_attributes_every_conflicting_value() -> None:
    """
    Both sides of the conflict remain attributable. Reducing this to one
    "primary" statement would make the disagreement unexplainable - the
    reader could see that something conflicted but not what with.
    """

    result = _evaluate(
        _subject(),
        quantity_result(
            "TR1",
            (
                _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
                _quantity("800 kVA", node="node-b", edge="edge-b", statement="s-b"),
            ),
        ),
    )

    assert result.outcome is ReasoningOutcome.INCONSISTENT
    assert len(result.contributors) == 2
    assert {c.statement_key for c in result.contributors} == {"s-a", "s-b"}
    assert {c.value for c in result.contributors} == {
        Decimal("630"),
        Decimal("800"),
    }
    assert all(c.review_id > 0 for c in result.contributors)


# --- 9-10. Determinism ---------------------------------------------------


def test_the_result_identity_is_deterministic() -> None:
    results = (
        _subject(),
        quantity_result("TR1", (_quantity("630 kVA"),)),
    )

    first = _evaluate(*results)
    second = _evaluate(*results)

    assert first.result_id == second.result_id
    assert first.outcome is second.outcome
    assert first.diagnostics.code is second.diagnostics.code


def test_the_identity_ignores_the_evaluation_clock() -> None:
    """Two evaluations of unchanged governed knowledge are the same
    conclusion; a timestamp would make them look like two."""

    context = _context(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )

    early = evaluate(context, _query(), evaluated_at=NOW)
    late = evaluate(
        context, _query(), evaluated_at=datetime(2027, 1, 1, 0, 0, 0)
    )

    assert early.result_id == late.result_id
    assert early.evaluated_at != late.evaluated_at


def test_contributor_ordering_is_deterministic_and_total() -> None:
    quantities = (
        _quantity("800 kVA", node="node-b", edge="edge-b", statement="s-b"),
        _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
    )

    forwards = _evaluate(_subject(), quantity_result("TR1", quantities))
    backwards = _evaluate(
        _subject(), quantity_result("TR1", tuple(reversed(quantities)))
    )

    assert [c.item_id for c in forwards.contributors] == [
        c.item_id for c in backwards.contributors
    ]
    assert forwards.result_id == backwards.result_id


def test_a_different_question_produces_a_different_identity() -> None:
    results = (_subject(), quantity_result("TR1", (_quantity("630 kVA"),)))

    first = _evaluate(*results)
    second = _evaluate(*results, query=_query("TR2"))

    assert first.result_id != second.result_id


# --- 11. Unsupported comparison is reported, never guessed --------------


def test_different_units_are_not_converted_but_reported() -> None:
    """
    Governed knowledge carries the declared value and unit and no base
    conversion. Converting kVA to VA here would be a units engine built
    on data the graph does not hold, so the rule says so and concludes
    `INSUFFICIENT_KNOWLEDGE` - a smaller answer than a guess, and a true
    one.
    """

    result = _evaluate(
        _subject(),
        quantity_result(
            "TR1",
            (
                _quantity("630 kVA", node="node-a", edge="edge-a", statement="s-a"),
                _quantity(
                    "630000 VA",
                    unit="VA",
                    node="node-b",
                    edge="edge-b",
                    statement="s-b",
                ),
            ),
        ),
    )

    assert result.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    assert (
        result.diagnostics.code
        is ReasoningDiagnosticCode.UNSUPPORTED_COMPARISON
    )
    assert result.diagnostics.distinct_unit_count == 2
    # The governed inputs it examined are still attributed.
    assert len(result.contributors) == 2


# --- 12-14. Reasoning changes nothing upstream --------------------------


def test_reasoning_leaves_the_context_package_untouched() -> None:
    """
    The rule is pure: it selects from the context it was handed and
    mutates nothing. Asserted on equality of the whole package, which is
    frozen throughout.
    """

    context = _context(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )
    before = context

    evaluate(context, _query(), evaluated_at=NOW)

    assert context == before
    assert context.selected_items == before.selected_items


def test_the_rule_reads_only_the_context_it_was_given() -> None:
    """
    Knowledge outside the context is not fetched; it is simply absent,
    and the rule says `INSUFFICIENT_KNOWLEDGE`. That is what keeps the
    upstream scope and authorization from being widened here.
    """

    # The asset resolves, but its quantity was never assembled into the
    # context - the rule must not go looking for it.
    result = _evaluate(_subject())

    assert result.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE


def test_every_result_names_its_rule_and_versions() -> None:
    result = _evaluate(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )

    assert result.rule == QUANTITY_CONSISTENCY_RULE
    assert result.rule.identity == "governed_quantity_consistency@1.0"
    assert result.reasoning_policy_version == "1.0"
    assert result.context_assembly_version == "2.0"


# --- 15. The vocabulary is closed ---------------------------------------


def test_the_four_outcomes_are_distinct_and_closed() -> None:
    """
    Four members, and no fifth. A `PROBABLY_CONSISTENT` is how a
    deterministic conclusion would become a probabilistic one without
    anybody deciding to make it so.
    """

    assert [outcome.name for outcome in ReasoningOutcome] == [
        "CONSISTENT",
        "INCONSISTENT",
        "INSUFFICIENT_KNOWLEDGE",
        "AMBIGUOUS",
    ]


def test_no_result_carries_a_score_or_confidence() -> None:
    result = _evaluate(
        _subject(), quantity_result("TR1", (_quantity("630 kVA"),))
    )

    for forbidden in ("score", "confidence", "probability", "weight"):
        assert not hasattr(result, forbidden)
        assert not hasattr(result.diagnostics, forbidden)
        assert not hasattr(result.contributors[0], forbidden)
