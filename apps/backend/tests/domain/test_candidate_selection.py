from __future__ import annotations

from app.domain.context_builder.candidate_selection import select_candidates
from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetPolicy,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateAttribute,
    KnowledgeCandidateKind,
    KnowledgeCandidateReference,
    KnowledgeCandidateRelationship,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    ScoreComponentCategory,
)

PROJECT_ID = 1


def _entity_id(entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=PROJECT_ID, entity_type=entity_type, canonical_id=canonical_id
    )


def _score(total: float) -> KnowledgeCandidateScore:
    return KnowledgeCandidateScore(
        total=total,
        components=(
            KnowledgeCandidateScoreComponent(
                category=ScoreComponentCategory.ENTITY_TYPE_MATCH,
                weight=total,
                detail="CABLE",
            ),
        ),
    )


def _entity_candidate(
    canonical_id: str, score: float, entity_type: str = "CABLE"
) -> KnowledgeCandidate:
    reference = KnowledgeCandidateReference(
        graph_entity_id=_entity_id(entity_type, canonical_id),
        entity_type=entity_type,
        canonical_id=canonical_id,
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:entity:{reference.graph_entity_id.value}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.ENTITY,
        primary_reference=reference,
        matched_attributes=(),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(reference.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=(1,),
        score=_score(score),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _attribute_candidate(
    canonical_id: str, attribute_name: str, score: float
) -> KnowledgeCandidate:
    reference = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("CABLE", canonical_id),
        entity_type="CABLE",
        canonical_id=canonical_id,
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:attribute:{reference.graph_entity_id.value}:{attribute_name}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.ATTRIBUTE,
        primary_reference=reference,
        matched_attributes=(
            KnowledgeCandidateAttribute(name=attribute_name, value="132kV"),
        ),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(reference.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=(1,),
        score=_score(score),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _relationship_candidate(
    subject_id: str, object_id: str, score: float
) -> KnowledgeCandidate:
    subject = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("CABLE", subject_id),
        entity_type="CABLE",
        canonical_id=subject_id,
    )
    obj = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("TRANSFORMER", object_id),
        entity_type="TRANSFORMER",
        canonical_id=object_id,
    )
    natural_key = (
        f"{subject.graph_entity_id.value}|FEEDS|{obj.graph_entity_id.value}"
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:relationship:{natural_key}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.RELATIONSHIP,
        primary_reference=subject,
        matched_attributes=(),
        matched_relationships=(
            KnowledgeCandidateRelationship(
                subject=subject,
                relationship_type=GraphRelationshipType(value="FEEDS"),
                object=obj,
            ),
        ),
        related_entities=(obj,),
        source_fact_ids=(),
        graph_node_ids=(subject.graph_entity_id.value, obj.graph_entity_id.value),
        graph_relationship_ids=(natural_key,),
        graph_execution_ids=(1,),
        score=_score(score),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _Policy(
    max_candidates=100,
    max_entities=100,
    max_relationships=100,
    max_attributes=100,
) -> BudgetPolicy:
    return BudgetPolicy(
        version="1.0",
        max_candidates=max_candidates,
        max_entities=max_entities,
        max_relationships=max_relationships,
        max_attributes=max_attributes,
        max_metadata_entries=20,
        max_warnings=50,
    )


def test_selection_orders_candidates_by_descending_score():
    candidates = (
        _entity_candidate("C-001", 10.0),
        _entity_candidate("C-002", 90.0),
        _entity_candidate("C-003", 50.0),
    )
    outcome = select_candidates(candidates, _Policy())
    assert [c.primary_reference.canonical_id for c in outcome.selected] == [
        "C-002",
        "C-003",
        "C-001",
    ]


def test_selection_is_deterministic_for_tied_scores():
    candidates = (
        _entity_candidate("C-003", 50.0),
        _entity_candidate("C-001", 50.0),
        _entity_candidate("C-002", 50.0),
    )
    first = select_candidates(candidates, _Policy())
    second = select_candidates(tuple(reversed(candidates)), _Policy())
    first_ids = [c.candidate_id for c in first.selected]
    second_ids = [c.candidate_id for c in second.selected]
    assert first_ids == second_ids
    # Tied scores fall back to ascending natural key (canonical id).
    assert [c.primary_reference.canonical_id for c in first.selected] == [
        "C-001",
        "C-002",
        "C-003",
    ]


def test_entity_candidates_rank_above_relationship_and_attribute_at_equal_score():
    candidates = (
        _attribute_candidate("C-001", "rated_voltage", 50.0),
        _relationship_candidate("C-001", "TR-01", 50.0),
        _entity_candidate("C-001", 50.0),
    )
    outcome = select_candidates(candidates, _Policy())
    kinds = [c.candidate_kind for c in outcome.selected]
    assert kinds == [
        KnowledgeCandidateKind.ENTITY,
        KnowledgeCandidateKind.RELATIONSHIP,
        KnowledgeCandidateKind.ATTRIBUTE,
    ]


def test_global_candidate_budget_is_enforced():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(5)
    )
    outcome = select_candidates(candidates, _Policy(max_candidates=2))
    assert len(outcome.selected) == 2
    assert len(outcome.discarded) == 3
    assert all(
        d.reason is BudgetCategory.CANDIDATES for d in outcome.discarded
    )


def test_per_kind_budget_is_enforced_independently_of_global_budget():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(5)
    )
    outcome = select_candidates(
        candidates, _Policy(max_candidates=10, max_entities=2)
    )
    assert len(outcome.selected) == 2
    assert all(d.reason is BudgetCategory.ENTITIES for d in outcome.discarded)


def test_a_full_kind_does_not_block_lower_ranked_candidates_of_other_kinds():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _entity_candidate("C-002", 90.0),
        _attribute_candidate("C-003", "rated_voltage", 50.0),
    )
    outcome = select_candidates(
        candidates, _Policy(max_candidates=10, max_entities=1)
    )
    kinds = {c.candidate_kind for c in outcome.selected}
    assert kinds == {
        KnowledgeCandidateKind.ENTITY,
        KnowledgeCandidateKind.ATTRIBUTE,
    }
    assert len(outcome.selected) == 2


def test_consumption_reports_requested_accepted_discarded_and_utilization():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(4)
    )
    outcome = select_candidates(candidates, _Policy(max_candidates=4, max_entities=3))
    entities_consumption = next(
        c for c in outcome.consumption if c.category is BudgetCategory.ENTITIES
    )
    assert entities_consumption.requested == 4
    assert entities_consumption.accepted == 3
    assert entities_consumption.discarded == 1
    assert entities_consumption.limit == 3
    assert entities_consumption.utilization == 1.0


def test_empty_candidate_tuple_produces_an_empty_outcome():
    outcome = select_candidates((), _Policy())
    assert outcome.selected == ()
    assert outcome.discarded == ()
    candidates_consumption = next(
        c for c in outcome.consumption if c.category is BudgetCategory.CANDIDATES
    )
    assert candidates_consumption.requested == 0
    assert candidates_consumption.accepted == 0
