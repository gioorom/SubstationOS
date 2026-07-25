from __future__ import annotations

from datetime import datetime

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphRelationshipView,
)
from app.domain.structured_retrieval import scoring_policy
from app.domain.structured_retrieval.candidate_aggregation import (
    CandidateAggregator,
)
from app.domain.structured_retrieval.candidate_matching import (
    match_entities_by_attribute,
    match_entities_by_type,
    match_entity_by_id,
    match_lexical,
    match_relationships_by_type,
)
from app.domain.structured_retrieval.candidate_ranking import CandidateRanker
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateKind,
    LexicalMatchMode,
    RetrievalCriterion,
    RetrievalCriterionKind,
    ScoreComponentCategory,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
PROJECT_ID = 5


def _entity(entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=PROJECT_ID, entity_type=entity_type, canonical_id=canonical_id
    )


def _node(entity_type: str, canonical_id: str, properties=None) -> GraphNodeView:
    return GraphNodeView(
        project_id=PROJECT_ID,
        graph_entity_id=_entity(entity_type, canonical_id),
        entity_type=entity_type,
        canonical_id=canonical_id,
        properties=properties or {},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _relationship(source, rel_type, target) -> GraphRelationshipView:
    return GraphRelationshipView(
        project_id=PROJECT_ID,
        source_entity_id=source,
        relationship_type=GraphRelationshipType(value=rel_type),
        target_entity_id=target,
        properties={},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


# --- Candidate Construction ----------------------------------------


def test_match_entity_by_id_produces_one_candidate_with_the_top_weight():
    node = _node("CABLE", "C-295")
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.CANONICAL_ENTITY_ID, value="CABLE:C-295"
    )
    candidates = match_entity_by_id(PROJECT_ID, criterion, node)
    assert len(candidates) == 1
    assert candidates[0].score.total == scoring_policy.WEIGHT_EXACT_CANONICAL_ID_MATCH
    assert candidates[0].candidate_kind is KnowledgeCandidateKind.ENTITY


def test_match_entity_by_id_returns_nothing_for_a_missing_node():
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.CANONICAL_ENTITY_ID, value="CABLE:MISSING"
    )
    assert match_entity_by_id(PROJECT_ID, criterion, None) == []


def test_match_entities_by_attribute_name_only_matches_presence():
    node = _node("CABLE", "C-295", properties={"rated_voltage": "132kV"})
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ATTRIBUTE_NAME, value="rated_voltage"
    )
    candidates = match_entities_by_attribute(PROJECT_ID, criterion, None, [node])
    assert len(candidates) == 1
    assert candidates[0].matched_attributes[0].value == "132kV"


def test_match_entities_by_attribute_name_and_value_produce_two_candidates():
    node = _node("CABLE", "C-295", properties={"rated_voltage": "132kV"})
    name_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ATTRIBUTE_NAME, value="rated_voltage"
    )
    value_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ATTRIBUTE_VALUE, value="132kV"
    )
    candidates = match_entities_by_attribute(
        PROJECT_ID, name_criterion, value_criterion, [node]
    )
    assert len(candidates) == 2
    categories = {c.score.components[0].category for c in candidates}
    assert categories == {
        ScoreComponentCategory.ATTRIBUTE_NAME_MATCH,
        ScoreComponentCategory.ATTRIBUTE_VALUE_MATCH,
    }


def test_match_entities_by_attribute_value_only_scans_every_property():
    node = _node(
        "CABLE", "C-295", properties={"rated_voltage": "132kV", "status": "132kV"}
    )
    value_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ATTRIBUTE_VALUE, value="132kV"
    )
    candidates = match_entities_by_attribute(
        PROJECT_ID, None, value_criterion, [node]
    )
    assert len(candidates) == 2
    matched_names = {c.matched_attributes[0].name for c in candidates}
    assert matched_names == {"rated_voltage", "status"}


def test_match_relationships_by_type_filters_by_exact_type():
    cable = _entity("CABLE", "C-295")
    transformer = _entity("TRANSFORMER", "TR-02")
    feeds = _relationship(cable, "FEEDS", transformer)
    protects = _relationship(cable, "PROTECTS", transformer)
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.RELATIONSHIP_TYPE, value="FEEDS"
    )
    candidates = match_relationships_by_type(
        PROJECT_ID, criterion, [feeds, protects]
    )
    assert len(candidates) == 1
    assert candidates[0].candidate_kind is KnowledgeCandidateKind.RELATIONSHIP


def test_lexical_search_any_mode_matches_on_a_single_term():
    node = _node("CABLE", "C-295")
    criteria = [
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="cable"),
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="nomatch"),
    ]
    candidates = match_lexical(
        PROJECT_ID, criteria, LexicalMatchMode.ANY, [node], []
    )
    assert len(candidates) == 1


def test_lexical_search_all_mode_requires_every_term_on_the_same_node():
    node = _node("CABLE", "C-295")
    criteria = [
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="cable"),
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="nomatch"),
    ]
    candidates = match_lexical(
        PROJECT_ID, criteria, LexicalMatchMode.ALL, [node], []
    )
    assert candidates == []


# --- Deduplication and Aggregation -----------------------------------


def test_aggregator_merges_the_same_candidate_from_two_criteria():
    node = _node("CABLE", "C-295", properties={"rated_voltage": "132kV"})
    type_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )
    lexical_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.LEXICAL_TERM, value="cable"
    )

    raw = match_entities_by_type(PROJECT_ID, type_criterion, [node])
    raw += match_lexical(
        PROJECT_ID, [lexical_criterion], LexicalMatchMode.ANY, [node], []
    )

    merged = CandidateAggregator.merge(raw)
    assert len(merged) == 1

    candidate = merged[0]
    assert len(candidate.matches) == 2
    categories = {c.category for c in candidate.score.components}
    assert ScoreComponentCategory.ENTITY_TYPE_MATCH in categories
    assert ScoreComponentCategory.LEXICAL_TOKEN_MATCH in categories
    # Convergent evidence from two distinct criterion kinds earns the
    # multi-criterion bonus exactly once.
    assert ScoreComponentCategory.MULTI_CRITERION_SUPPORT in categories
    expected_total = (
        scoring_policy.WEIGHT_ENTITY_TYPE_MATCH
        + scoring_policy.WEIGHT_LEXICAL_TOKEN_MATCH
        + scoring_policy.WEIGHT_MULTI_CRITERION_SUPPORT
    )
    assert candidate.score.total == expected_total


def test_aggregator_does_not_double_count_the_same_evidence_seen_twice():
    node = _node("CABLE", "C-295")
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )
    # Simulate the same criterion being evaluated twice (e.g. a
    # duplicate criterion) - the same (category, detail) evidence must
    # collapse into a single score component, not two.
    raw = match_entities_by_type(PROJECT_ID, criterion, [node]) * 2

    merged = CandidateAggregator.merge(raw)
    assert len(merged) == 1
    assert len(merged[0].score.components) == 1
    assert merged[0].score.total == scoring_policy.WEIGHT_ENTITY_TYPE_MATCH


def test_aggregator_keeps_distinct_lexical_tokens_as_separate_components():
    node = _node("CABLE", "C-295")
    criteria = [
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="cable"),
        RetrievalCriterion(kind=RetrievalCriterionKind.LEXICAL_TERM, value="c-295"),
    ]
    raw = match_lexical(
        PROJECT_ID, criteria, LexicalMatchMode.ANY, [node], []
    )
    merged = CandidateAggregator.merge(raw)
    assert len(merged) == 1
    lexical_components = [
        c
        for c in merged[0].score.components
        if c.category is ScoreComponentCategory.LEXICAL_TOKEN_MATCH
    ]
    assert len(lexical_components) == 2


def test_aggregator_preserves_candidates_that_do_not_share_an_id():
    node_a = _node("CABLE", "C-295")
    node_b = _node("TRANSFORMER", "TR-02")
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.LEXICAL_TERM, value="cable"
    )
    raw = match_lexical(
        PROJECT_ID, [criterion], LexicalMatchMode.ANY, [node_a], []
    )
    other_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.LEXICAL_TERM, value="transformer"
    )
    raw += match_lexical(
        PROJECT_ID, [other_criterion], LexicalMatchMode.ANY, [node_b], []
    )

    merged = CandidateAggregator.merge(raw)
    assert len(merged) == 2


# --- Result Ordering ---------------------------------------------------


def test_ranking_orders_by_score_descending():
    high = _node("CABLE", "C-295")
    low = _node("CABLE", "C-100")

    exact_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.CANONICAL_ENTITY_ID, value="CABLE:C-295"
    )
    type_criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )

    raw = match_entity_by_id(PROJECT_ID, exact_criterion, high)
    raw += match_entities_by_type(PROJECT_ID, type_criterion, [low])

    merged = CandidateAggregator.merge(raw)
    collection = CandidateRanker.rank_and_limit(merged, limit=10)

    assert [c.candidate_id for c in collection.candidates] == [
        merged_candidate.candidate_id
        for merged_candidate in sorted(merged, key=lambda c: c.sort_key)
    ]
    assert collection.candidates[0].score.total >= collection.candidates[1].score.total


def test_ranking_breaks_ties_by_kind_priority_then_natural_key():
    cable_a = _node("CABLE", "AAA")
    cable_b = _node("CABLE", "BBB")
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )
    raw = match_entities_by_type(PROJECT_ID, criterion, [cable_b, cable_a])
    merged = CandidateAggregator.merge(raw)
    collection = CandidateRanker.rank_and_limit(merged, limit=10)

    # Same score (tied) -> same kind priority -> natural key breaks the
    # tie deterministically, alphabetically by canonical_id.
    assert [c.primary_reference.canonical_id for c in collection.candidates] == [
        "AAA",
        "BBB",
    ]


def test_ranking_applies_the_limit_only_after_ranking():
    nodes = [_node("CABLE", f"C-{i:03d}") for i in range(5)]
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )
    raw = match_entities_by_type(PROJECT_ID, criterion, nodes)
    merged = CandidateAggregator.merge(raw)

    collection = CandidateRanker.rank_and_limit(merged, limit=2)
    assert collection.total_before_limit == 5
    assert collection.returned_count == 2
    assert collection.applied_limit == 2
    assert len(collection.candidates) == 2


def test_ranking_is_deterministic_across_repeated_runs():
    nodes = [_node("CABLE", f"C-{i:03d}") for i in range(10)]
    criterion = RetrievalCriterion(
        kind=RetrievalCriterionKind.ENTITY_TYPE, value="CABLE"
    )

    def _rank():
        raw = match_entities_by_type(PROJECT_ID, criterion, nodes)
        merged = CandidateAggregator.merge(raw)
        return [
            c.candidate_id
            for c in CandidateRanker.rank_and_limit(merged, limit=10).candidates
        ]

    assert _rank() == _rank()
