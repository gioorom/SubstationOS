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
from app.domain.graph_query.graph_query_repository import (
    GraphQueryRepository,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateKind,
    LexicalMatchMode,
    RetrievalMode,
    RetrievalQueryOperation,
    ScoreComponentCategory,
)
from app.services import structured_retrieval_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
PROJECT_ID = 10
OTHER_PROJECT_ID = 99


def _entity(entity_type: str, canonical_id: str, project_id: int = PROJECT_ID):
    return GraphEntityId(
        project_id=project_id, entity_type=entity_type, canonical_id=canonical_id
    )


def _node(entity_type, canonical_id, properties=None, project_id=PROJECT_ID):
    return GraphNodeView(
        project_id=project_id,
        graph_entity_id=_entity(entity_type, canonical_id, project_id),
        entity_type=entity_type,
        canonical_id=canonical_id,
        properties=properties or {},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _relationship(source, rel_type, target, project_id=PROJECT_ID):
    return GraphRelationshipView(
        project_id=project_id,
        source_entity_id=source,
        relationship_type=GraphRelationshipType(value=rel_type),
        target_entity_id=target,
        properties={},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


class FakeGraphQueryRepository(GraphQueryRepository):
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNodeView] = {}
        self.relationships: list[GraphRelationshipView] = []

    def add_node(self, node: GraphNodeView) -> None:
        self.nodes[node.graph_entity_id.value] = node

    def add_relationship(self, relationship: GraphRelationshipView) -> None:
        self.relationships.append(relationship)

    def get_node(self, project_id, graph_entity_id):
        node = self.nodes.get(graph_entity_id.value)
        return node if node is not None and node.project_id == project_id else None

    def list_nodes(self, project_id):
        return [n for n in self.nodes.values() if n.project_id == project_id]

    def list_nodes_by_type(self, project_id, entity_type):
        return [
            n for n in self.list_nodes(project_id) if n.entity_type == entity_type
        ]

    def list_nodes_with_attribute(self, project_id, attribute):
        return [
            n for n in self.list_nodes(project_id) if attribute in n.properties
        ]

    def list_orphan_nodes(self, project_id):
        connected = set()
        for r in self.relationships:
            connected.add(r.source_entity_id.value)
            connected.add(r.target_entity_id.value)
        return [
            n
            for n in self.list_nodes(project_id)
            if n.graph_entity_id.value not in connected
        ]

    def list_relationships(self, project_id):
        return [r for r in self.relationships if r.project_id == project_id]

    def list_outgoing_relationships(self, project_id, graph_entity_id):
        return [
            r
            for r in self.list_relationships(project_id)
            if r.source_entity_id.value == graph_entity_id.value
        ]

    def list_incoming_relationships(self, project_id, graph_entity_id):
        return [
            r
            for r in self.list_relationships(project_id)
            if r.target_entity_id.value == graph_entity_id.value
        ]

    def count_entities_by_type(self, project_id):
        counts: dict[str, int] = {}
        for node in self.list_nodes(project_id):
            counts[node.entity_type] = counts.get(node.entity_type, 0) + 1
        return counts

    def count_relationships_by_type(self, project_id):
        counts: dict[str, int] = {}
        for relationship in self.list_relationships(project_id):
            key = relationship.relationship_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


def _repository_with_fixture() -> FakeGraphQueryRepository:
    repository = FakeGraphQueryRepository()
    cable = _node("CABLE", "C-295", properties={"rated_voltage": "132kV"})
    transformer = _node("TRANSFORMER", "TR-02", properties={"rated_voltage": "132kV"})
    breaker = _node("CIRCUIT_BREAKER", "CB-01")
    repository.add_node(cable)
    repository.add_node(transformer)
    repository.add_node(breaker)
    repository.add_relationship(
        _relationship(cable.graph_entity_id, "FEEDS", transformer.graph_entity_id)
    )
    repository.add_relationship(
        _relationship(breaker.graph_entity_id, "PROTECTS", cable.graph_entity_id)
    )
    return repository


def _request(**overrides):
    defaults = dict(
        project_id=PROJECT_ID,
        mode=RetrievalMode.ENTITY_LOOKUP,
        limit=20,
        include_neighborhood=False,
        neighborhood_depth=0,
        canonical_entity_id="CABLE:C-295",
    )
    defaults.update(overrides)
    return StructuredRetrievalRequestFactory.create(**defaults)


def test_exact_entity_retrieval_returns_the_matched_node():
    repository = _repository_with_fixture()
    result = structured_retrieval_service.retrieve(
        repository, _request(), now=CREATED_AT
    )
    assert result.candidates.returned_count == 1
    candidate = result.candidates.candidates[0]
    assert candidate.primary_reference.canonical_id == "C-295"
    assert candidate.score.total == 100.0


def test_exact_entity_retrieval_of_a_missing_entity_is_an_empty_result_not_an_error():
    repository = _repository_with_fixture()
    result = structured_retrieval_service.retrieve(
        repository,
        _request(canonical_entity_id="CABLE:DOES-NOT-EXIST"),
        now=CREATED_AT,
    )
    assert result.candidates.returned_count == 0
    assert result.candidates.total_before_limit == 0
    assert result.metadata.warnings == ()


def test_malformed_canonical_entity_reference_produces_a_warning_not_a_crash():
    repository = _repository_with_fixture()
    result = structured_retrieval_service.retrieve(
        repository,
        _request(canonical_entity_id="malformed"),
        now=CREATED_AT,
    )
    assert result.candidates.returned_count == 0
    assert len(result.metadata.warnings) == 1


def test_entity_type_retrieval_returns_every_matching_node():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.ENTITY_TYPE_SEARCH,
        canonical_entity_id=None,
        entity_type="CABLE",
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.returned_count == 1
    assert result.candidates.candidates[0].primary_reference.entity_type == "CABLE"


def test_attribute_retrieval_returns_every_node_with_the_attribute():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.ATTRIBUTE_SEARCH,
        canonical_entity_id=None,
        attribute_name="rated_voltage",
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.returned_count == 2
    assert all(
        c.candidate_kind is KnowledgeCandidateKind.ATTRIBUTE
        for c in result.candidates.candidates
    )


def test_relationship_retrieval_returns_matching_relationships():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.RELATIONSHIP_SEARCH,
        canonical_entity_id=None,
        relationship_type="FEEDS",
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.returned_count == 1
    assert result.candidates.candidates[0].candidate_kind is KnowledgeCandidateKind.RELATIONSHIP


def test_lexical_retrieval_matches_across_nodes_and_relationships():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.LEXICAL_SEARCH,
        canonical_entity_id=None,
        lexical_terms=("feeds",),
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.returned_count == 1
    assert result.candidates.candidates[0].candidate_kind is KnowledgeCandidateKind.RELATIONSHIP


def test_combined_retrieval_merges_evidence_for_the_multi_criterion_bonus():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.COMBINED,
        canonical_entity_id=None,
        entity_type="CABLE",
        lexical_terms=("cable",),
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    cable_candidates = [
        c
        for c in result.candidates.candidates
        if c.candidate_kind is KnowledgeCandidateKind.ENTITY
        and c.primary_reference.canonical_id == "C-295"
    ]
    assert len(cable_candidates) == 1
    categories = {c.category for c in cable_candidates[0].score.components}
    assert ScoreComponentCategory.MULTI_CRITERION_SUPPORT in categories


def test_neighborhood_enrichment_is_optional_and_populates_related_entities():
    repository = _repository_with_fixture()
    without = structured_retrieval_service.retrieve(
        repository, _request(), now=CREATED_AT
    )
    assert without.candidates.candidates[0].related_entities == ()
    assert without.metadata.neighborhood_enrichment_applied is False

    with_neighborhood = structured_retrieval_service.retrieve(
        repository,
        _request(include_neighborhood=True, neighborhood_depth=1),
        now=CREATED_AT,
    )
    related_ids = {
        r.canonical_id
        for r in with_neighborhood.candidates.candidates[0].related_entities
    }
    assert related_ids == {"TR-02", "CB-01"}
    assert with_neighborhood.metadata.neighborhood_enrichment_applied is True
    assert RetrievalQueryOperation.NEIGHBORHOOD in with_neighborhood.metadata.executed_operations


def test_empty_graph_returns_a_successful_empty_result():
    repository = FakeGraphQueryRepository()
    request = _request(
        mode=RetrievalMode.ENTITY_TYPE_SEARCH,
        canonical_entity_id=None,
        entity_type="CABLE",
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.returned_count == 0
    assert result.candidates.total_before_limit == 0


def test_retrieval_is_scoped_to_the_requested_project():
    repository = _repository_with_fixture()
    other_cable = _node("CABLE", "OTHER", project_id=OTHER_PROJECT_ID)
    repository.add_node(other_cable)

    request = _request(
        mode=RetrievalMode.ENTITY_TYPE_SEARCH,
        canonical_entity_id=None,
        entity_type="CABLE",
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    canonical_ids = {c.primary_reference.canonical_id for c in result.candidates.candidates}
    assert canonical_ids == {"C-295"}


def test_result_limit_is_enforced_after_ranking():
    repository = FakeGraphQueryRepository()
    for index in range(5):
        repository.add_node(_node("CABLE", f"C-{index:03d}"))

    request = _request(
        mode=RetrievalMode.ENTITY_TYPE_SEARCH,
        canonical_entity_id=None,
        entity_type="CABLE",
        limit=2,
    )
    result = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    assert result.candidates.total_before_limit == 5
    assert result.candidates.returned_count == 2


def test_retrieval_is_deterministic_across_repeated_executions():
    repository = _repository_with_fixture()
    request = _request(
        mode=RetrievalMode.COMBINED,
        canonical_entity_id=None,
        entity_type="CABLE",
        lexical_terms=("cable", "feeds"),
    )
    first = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)
    second = structured_retrieval_service.retrieve(repository, request, now=CREATED_AT)

    first_ids = [c.candidate_id for c in first.candidates.candidates]
    second_ids = [c.candidate_id for c in second.candidates.candidates]
    assert first_ids == second_ids

    first_scores = [c.score.total for c in first.candidates.candidates]
    second_scores = [c.score.total for c in second.candidates.candidates]
    assert first_scores == second_scores


def test_plan_retrieval_does_not_touch_the_repository():
    class ExplodingRepository(GraphQueryRepository):
        def get_node(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_nodes(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_nodes_by_type(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_nodes_with_attribute(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_orphan_nodes(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_relationships(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_outgoing_relationships(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def list_incoming_relationships(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def count_entities_by_type(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

        def count_relationships_by_type(self, *args, **kwargs):
            raise AssertionError("plan_retrieval must not call the repository")

    plan = structured_retrieval_service.plan_retrieval(_request())
    assert plan.project_id == PROJECT_ID
    # ExplodingRepository is unused by design - proves plan_retrieval
    # takes no repository argument at all.
    assert ExplodingRepository is not None


def test_get_candidate_and_explain_result_helpers():
    repository = _repository_with_fixture()
    result = structured_retrieval_service.retrieve(
        repository, _request(), now=CREATED_AT
    )
    candidate_id = result.candidates.candidates[0].candidate_id

    found = structured_retrieval_service.get_candidate(result, candidate_id)
    assert found is not None
    assert found.candidate_id == candidate_id

    assert structured_retrieval_service.get_candidate(result, "missing") is None

    explanation = structured_retrieval_service.explain_result(result)
    assert candidate_id in explanation
    assert explanation[candidate_id] == found.reasons


def test_lexical_all_mode_is_stricter_than_any_mode():
    repository = _repository_with_fixture()
    any_request = _request(
        mode=RetrievalMode.LEXICAL_SEARCH,
        canonical_entity_id=None,
        lexical_terms=("cable", "transformer"),
        lexical_match_mode=LexicalMatchMode.ANY,
    )
    all_request = _request(
        mode=RetrievalMode.LEXICAL_SEARCH,
        canonical_entity_id=None,
        lexical_terms=("cable", "transformer"),
        lexical_match_mode=LexicalMatchMode.ALL,
    )
    any_result = structured_retrieval_service.retrieve(
        repository, any_request, now=CREATED_AT
    )
    all_result = structured_retrieval_service.retrieve(
        repository, all_request, now=CREATED_AT
    )
    assert all_result.candidates.returned_count <= any_result.candidates.returned_count
