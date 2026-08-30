"""
The Governed Knowledge Graph domain, tested as pure values.

No database, no request, no clock. The centrepiece is the promotion-rule
section: it specifies, one case at a time, exactly what may become
governed knowledge - which is the gate the whole context exists to hold.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.governed_knowledge_graph.graph_events import (
    FAILURE_REFUSALS,
    GraphEventType,
)
from app.domain.governed_knowledge_graph.graph_exceptions import (
    InvalidGraphIdentityError,
    InvalidGraphProvenanceError,
)
from app.domain.governed_knowledge_graph.graph_identity import (
    edge_id_for,
    node_id_for,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirement,
    GraphRetirementReason,
    is_queryable,
    state_for_promotion,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_provenance import (
    GraphProvenance,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    EDGE_ENDPOINT_KINDS,
    EDGE_KIND_FOR_STATEMENT_TYPE,
    NODE_KIND_FOR_ENTITY_TYPE,
    GraphEdgeKind,
    GraphNodeKind,
    edge_kind_for_statement_type,
    endpoints_valid,
    node_kind_for_entity_type,
)
from app.domain.governed_knowledge_graph.promotion_rules import (
    APPLIES_APPLICABILITY,
    APPROVED_DECISION,
    RETIRING_REFUSALS,
    PromotionCandidate,
    PromotionRefusal,
    evaluate,
)

NOW = datetime(2026, 7, 30, 9, 0, 0)


def _candidate(**overrides) -> PromotionCandidate:
    defaults = dict(
        statement_key="s" * 64,
        statement_type="has_rated_power",
        subject_entity_key="entity-tr1",
        subject_entity_type="equipment_designation",
        object_entity_key="entity-630kva",
        object_entity_type="engineering_quantity",
        decision=APPROVED_DECISION,
        applicability=APPLIES_APPLICABILITY,
    )
    defaults.update(overrides)

    return PromotionCandidate(**defaults)


def _provenance(**overrides) -> GraphProvenance:
    defaults = dict(
        statement_key="s" * 64,
        document_id=10,
        content_checksum="c" * 64,
        review_id=1,
        reviewer_user_id=7,
        reviewer_display_name="Ada Lovelace",
        reviewed_at=NOW,
        semantic_rule_id="rated_power_from_associated_power_quantity",
        semantic_rule_version="1.0",
        semantic_contract_version="1.0",
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint="f" * 64,
        project_id=1,
    )
    defaults.update(overrides)

    return GraphProvenance(**defaults)


# --- The vocabulary is exactly what governed semantics produces ---------


def test_the_graph_holds_only_what_semantics_produces() -> None:
    """
    Three node kinds and two edge kinds - because the pipeline produces
    three entity types and two statement types. A Voltage, Protection,
    Connection or Function kind would be inventing engineering ontology,
    which the EPIC forbids and which the semantics context already
    refuses upstream.

    ``structural_location``/``is_located_in`` (EPIC 32.P1) are here
    because ``location_from_compound_reference_designation`` produces the
    statement they come from - the same standard every other member had
    to meet.
    """

    assert {kind.value for kind in GraphNodeKind} == {
        "engineering_asset",
        "engineering_quantity",
        "structural_location",
    }
    assert {kind.value for kind in GraphEdgeKind} == {
        "has_rated_power",
        "is_located_in",
    }


def test_every_governed_entity_type_maps_to_a_node_kind() -> None:
    assert (
        node_kind_for_entity_type("equipment_designation")
        is GraphNodeKind.ENGINEERING_ASSET
    )
    assert (
        node_kind_for_entity_type("engineering_quantity")
        is GraphNodeKind.ENGINEERING_QUANTITY
    )


def test_an_entity_type_the_graph_does_not_govern_maps_to_nothing() -> None:
    """
    The mapping is the **only** way a node comes into existence, so an
    absent entry is a promotion that cannot happen rather than a default
    that quietly does.
    """

    assert node_kind_for_entity_type("transformer") is None
    assert edge_kind_for_statement_type("has_rated_voltage") is None


def test_every_edge_kind_declares_its_endpoint_kinds() -> None:
    assert set(EDGE_ENDPOINT_KINDS) == set(GraphEdgeKind)


def test_a_rated_power_relates_an_asset_to_a_quantity_in_that_order() -> None:
    """
    The reverse would let the graph answer "what is the rated power of
    630 kVA?".
    """

    assert endpoints_valid(
        GraphEdgeKind.HAS_RATED_POWER,
        GraphNodeKind.ENGINEERING_ASSET,
        GraphNodeKind.ENGINEERING_QUANTITY,
    )
    assert not endpoints_valid(
        GraphEdgeKind.HAS_RATED_POWER,
        GraphNodeKind.ENGINEERING_QUANTITY,
        GraphNodeKind.ENGINEERING_ASSET,
    )


def test_the_mappings_cover_every_declared_kind() -> None:
    """A kind nothing maps to would be a node the graph can never hold."""

    assert set(NODE_KIND_FOR_ENTITY_TYPE.values()) == set(GraphNodeKind)
    assert set(EDGE_KIND_FOR_STATEMENT_TYPE.values()) == set(GraphEdgeKind)


# --- Promotion rules -----------------------------------------------------


def test_approved_and_applicable_is_promoted() -> None:
    decision = evaluate(_candidate())

    assert decision.promote
    assert decision.edge_kind is GraphEdgeKind.HAS_RATED_POWER
    assert decision.subject_kind is GraphNodeKind.ENGINEERING_ASSET
    assert decision.object_kind is GraphNodeKind.ENGINEERING_QUANTITY


def test_an_unreviewed_statement_is_not_knowledge() -> None:
    """
    Pipeline output, not governed knowledge. Admitting it would make the
    graph exactly what ADR-0004 forbids.
    """

    decision = evaluate(_candidate(decision=None, applicability=None))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.NOT_REVIEWED


def test_a_rejected_statement_never_becomes_a_node() -> None:
    decision = evaluate(_candidate(decision="rejected"))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.REVIEW_REJECTED


def test_needs_investigation_is_not_a_weak_approval() -> None:
    decision = evaluate(_candidate(decision="needs_investigation"))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.REVIEW_INCONCLUSIVE


def test_requires_revalidation_never_becomes_graph_knowledge() -> None:
    """
    The judgement was passed on a statement derived under different rules
    or bytes. Promoting on the strength of it would publish knowledge
    nobody approved.
    """

    decision = evaluate(
        _candidate(applicability="requires_revalidation")
    )

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.REVIEW_STALE


def test_an_orphaned_review_never_becomes_graph_knowledge() -> None:
    decision = evaluate(_candidate(applicability="orphaned"))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.REVIEW_ORPHANED


def test_an_ungoverned_statement_type_is_refused() -> None:
    decision = evaluate(_candidate(statement_type="has_rated_voltage"))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.UNGOVERNED_STATEMENT_TYPE


def test_an_ungoverned_entity_type_is_refused() -> None:
    decision = evaluate(_candidate(subject_entity_type="transformer"))

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.UNGOVERNED_ENTITY_TYPE


def test_reversed_endpoints_are_refused() -> None:
    decision = evaluate(
        _candidate(
            subject_entity_type="engineering_quantity",
            object_entity_type="equipment_designation",
        )
    )

    assert not decision.promote
    assert decision.refusal is PromotionRefusal.INVALID_ENDPOINTS


def test_governance_is_checked_before_vocabulary() -> None:
    """
    A rejected statement of an ungovernable type is reported as rejected:
    the reviewer's judgement is the fact that matters, and the vocabulary
    gap is this platform's problem rather than theirs.
    """

    decision = evaluate(
        _candidate(decision="rejected", statement_type="has_rated_voltage")
    )

    assert decision.refusal is PromotionRefusal.REVIEW_REJECTED


def test_an_unrecognised_decision_is_refused_rather_than_promoted() -> None:
    """
    A new decision value upstream must be a deliberate change here, never
    a silent promotion.
    """

    decision = evaluate(_candidate(decision="provisionally_fine"))

    assert not decision.promote


def test_a_decision_is_never_partially_made() -> None:
    for candidate in (_candidate(), _candidate(decision="rejected")):
        decision = evaluate(candidate)

        assert decision.promote != (decision.refusal is not None)


def test_only_review_refusals_retire_existing_knowledge() -> None:
    """
    A vocabulary gap describes a candidate that never entered the graph,
    so there is nothing to retire.
    """

    assert PromotionRefusal.REVIEW_REJECTED in RETIRING_REFUSALS
    assert PromotionRefusal.UNGOVERNED_ENTITY_TYPE not in RETIRING_REFUSALS
    assert RETIRING_REFUSALS.isdisjoint(FAILURE_REFUSALS)


# --- Identity ------------------------------------------------------------


def test_node_identity_is_deterministic() -> None:
    """
    The same kind and key always produce the same id - on any machine, in
    any process, forever. That is what makes a rebuild reproduce the
    graph rather than merely re-populate it.
    """

    first = node_id_for(GraphNodeKind.ENGINEERING_ASSET, "entity-tr1")
    second = node_id_for(GraphNodeKind.ENGINEERING_ASSET, "entity-tr1")

    assert first.value == second.value


def test_node_identity_does_not_come_from_the_label() -> None:
    """
    Two entities that happen to render `TR1` are two nodes. Identity from
    a label would silently merge two transformers in two drawings.
    """

    first = node_id_for(GraphNodeKind.ENGINEERING_ASSET, "entity-tr1-doc-a")
    second = node_id_for(GraphNodeKind.ENGINEERING_ASSET, "entity-tr1-doc-b")

    assert first.value != second.value


def test_the_same_key_under_two_kinds_is_two_identities() -> None:
    assert (
        node_id_for(GraphNodeKind.ENGINEERING_ASSET, "k").value
        != node_id_for(GraphNodeKind.ENGINEERING_QUANTITY, "k").value
    )


def test_edge_identity_derives_from_the_statement_key() -> None:
    edge = edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "statement-1")

    assert edge.statement_key == "statement-1"
    assert (
        edge.value
        == edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "statement-1").value
    )


def test_a_statement_re_derived_under_a_new_rule_is_a_new_edge() -> None:
    """
    `statement_key` hashes the rule versions upstream, so knowledge from
    two rule versions can never silently merge into one edge.
    """

    assert (
        edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "statement-v1").value
        != edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "statement-v2").value
    )


@pytest.mark.parametrize("key", ["", "   "])
def test_an_identity_that_names_no_artefact_is_refused(key: str) -> None:
    with pytest.raises(InvalidGraphIdentityError):
        node_id_for(GraphNodeKind.ENGINEERING_ASSET, key)

    with pytest.raises(InvalidGraphIdentityError):
        edge_id_for(GraphEdgeKind.HAS_RATED_POWER, key)


def test_identity_is_namespaced_and_versioned() -> None:
    """
    A future change to how identity is composed must be a visible
    re-identification, not a silent one.
    """

    from app.domain.governed_knowledge_graph import graph_identity

    assert graph_identity.NODE_IDENTITY_NAMESPACE.endswith("/v1")
    assert graph_identity.EDGE_IDENTITY_NAMESPACE.endswith("/v1")


# --- Provenance is mandatory --------------------------------------------


@pytest.mark.parametrize(
    "missing",
    [
        "statement_key",
        "content_checksum",
        "semantic_rule_id",
        "semantic_rule_version",
        "semantic_contract_version",
        "resolution_policy_version",
        "fact_policy_version",
        "semantic_policy_version",
        "support_fingerprint",
        "reviewer_display_name",
    ],
)
def test_knowledge_without_provenance_cannot_be_constructed(
    missing: str,
) -> None:
    """
    A graph object nobody can trace is worse than a missing one: the
    missing one is visibly missing.
    """

    with pytest.raises(InvalidGraphProvenanceError):
        _provenance(**{missing: ""})


def test_provenance_must_name_its_document_and_review() -> None:
    with pytest.raises(InvalidGraphProvenanceError):
        _provenance(document_id=0)

    with pytest.raises(InvalidGraphProvenanceError):
        _provenance(review_id=0)


def test_provenance_carries_no_artefact() -> None:
    """
    Identity, never content. A copy of the statement here would be a
    second account of what the document says.
    """

    fields = set(GraphProvenance.__dataclass_fields__)

    for forbidden in (
        "statement_type",
        "subject_entity_key",
        "object_entity_key",
        "value",
        "unit",
        "observed_text",
        "comment",
    ):
        assert forbidden not in fields


def test_provenance_names_every_version_the_epic_required() -> None:
    provenance = _provenance()

    assert provenance.rule_identity == (
        "rated_power_from_associated_power_quantity@1.0"
    )
    assert provenance.pipeline_identity == ("c" * 64, "1.0", "1.0", "1.0")
    assert provenance.support_fingerprint


# --- Lifecycle -----------------------------------------------------------


def test_newly_promoted_knowledge_is_current() -> None:
    assert state_for_promotion() is GraphObjectState.ACTIVE


def test_only_active_knowledge_answers_queries() -> None:
    assert is_queryable(GraphObjectState.ACTIVE)
    assert not is_queryable(GraphObjectState.HISTORICAL)
    assert not is_queryable(GraphObjectState.REMOVED)


def test_created_is_an_event_and_not_a_state() -> None:
    """
    A `created` state would be a value nothing transitions out of and no
    query excludes.
    """

    assert "created" not in {state.value for state in GraphObjectState}


def test_retiring_an_edge_keeps_its_provenance() -> None:
    """
    *Why the graph once believed this* does not change when it stops
    being current.
    """

    edge = GraphEdge(
        edge_id=edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "s"),
        kind=GraphEdgeKind.HAS_RATED_POWER,
        subject_node_id="a",
        object_node_id="b",
        state=GraphObjectState.ACTIVE,
        provenance=_provenance(),
        created_at=NOW,
    )

    retired = edge.retired(
        GraphRetirement(
            reason=GraphRetirementReason.REQUIRES_REVALIDATION,
            retired_at=NOW,
        )
    )

    assert retired.state is GraphObjectState.HISTORICAL
    assert retired.provenance == edge.provenance
    assert retired.created_at == edge.created_at
    assert retired.retirement is not None
    # The original is untouched: these are values, not mutations.
    assert edge.state is GraphObjectState.ACTIVE


def test_reactivating_an_edge_preserves_its_identity() -> None:
    """
    A later review approving it reactivates the edge rather than creating
    a second one, so every reference to it survives the round trip.
    """

    edge = GraphEdge(
        edge_id=edge_id_for(GraphEdgeKind.HAS_RATED_POWER, "s"),
        kind=GraphEdgeKind.HAS_RATED_POWER,
        subject_node_id="a",
        object_node_id="b",
        state=GraphObjectState.HISTORICAL,
        provenance=_provenance(),
        created_at=NOW,
        retirement=GraphRetirement(
            reason=GraphRetirementReason.REVIEW_REVERSED, retired_at=NOW
        ),
    )

    revived = edge.reactivated()

    assert revived.edge_id.value == edge.edge_id.value
    assert revived.state is GraphObjectState.ACTIVE
    assert revived.retirement is None


def test_every_retirement_states_a_reason() -> None:
    """
    "The graph shrank" is not actionable; "a rule change retired forty
    edges pending revalidation" is.
    """

    assert {reason.value for reason in GraphRetirementReason} == {
        "review_reversed",
        "requires_revalidation",
        "orphaned",
        "rebuild_reconciliation",
        "no_remaining_relationships",
    }


def test_a_node_carries_a_unit_only_where_one_is_meaningful() -> None:
    node = GraphNode(
        node_id=node_id_for(GraphNodeKind.ENGINEERING_ASSET, "e"),
        kind=GraphNodeKind.ENGINEERING_ASSET,
        label="TR1",
        normalized_value="TR1",
        unit=None,
        state=GraphObjectState.ACTIVE,
        provenance=_provenance(),
        created_at=NOW,
    )

    assert node.unit is None
    assert node.is_current


# --- Events --------------------------------------------------------------


def test_the_event_catalogue_is_closed() -> None:
    assert {event.value for event in GraphEventType} == {
        "knowledge_promoted",
        "knowledge_historical",
        "knowledge_removed",
        "knowledge_revalidated",
        "graph_rebuilt",
        "promotion_failed",
    }


def test_only_integrity_problems_are_promotion_failures() -> None:
    """
    A statement nobody approved is not a failure. An event per unreviewed
    statement would bury the ones that matter.
    """

    assert PromotionRefusal.NOT_REVIEWED not in FAILURE_REFUSALS
    assert PromotionRefusal.REVIEW_REJECTED not in FAILURE_REFUSALS
    assert PromotionRefusal.INVALID_ENDPOINTS in FAILURE_REFUSALS
