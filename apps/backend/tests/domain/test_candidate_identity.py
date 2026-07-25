from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.structured_retrieval.candidate_identity import (
    attribute_candidate_id,
    entity_candidate_id,
    neighborhood_candidate_id,
    relationship_candidate_id,
    relationship_natural_key,
)

PROJECT_ID = 7
CABLE = GraphEntityId(project_id=PROJECT_ID, entity_type="CABLE", canonical_id="C-295")
TRANSFORMER = GraphEntityId(project_id=PROJECT_ID, entity_type="TRANSFORMER", canonical_id="TR-02")
FEEDS = GraphRelationshipType(value="FEEDS")


def test_entity_candidate_id_is_deterministic():
    assert entity_candidate_id(PROJECT_ID, CABLE) == entity_candidate_id(
        PROJECT_ID, CABLE
    )


def test_entity_candidate_id_differs_by_entity():
    assert entity_candidate_id(PROJECT_ID, CABLE) != entity_candidate_id(
        PROJECT_ID, TRANSFORMER
    )


def test_entity_candidate_id_differs_by_project():
    other_project_cable = GraphEntityId(
        project_id=PROJECT_ID + 1, entity_type="CABLE", canonical_id="C-295"
    )
    assert entity_candidate_id(
        PROJECT_ID, CABLE
    ) != entity_candidate_id(PROJECT_ID + 1, other_project_cable)


def test_attribute_candidate_id_differs_by_attribute_name():
    first = attribute_candidate_id(PROJECT_ID, CABLE, "rated_voltage")
    second = attribute_candidate_id(PROJECT_ID, CABLE, "length")
    assert first != second


def test_relationship_candidate_id_is_deterministic_and_directional():
    forward = relationship_candidate_id(PROJECT_ID, CABLE, FEEDS, TRANSFORMER)
    reverse = relationship_candidate_id(PROJECT_ID, TRANSFORMER, FEEDS, CABLE)
    assert forward == relationship_candidate_id(
        PROJECT_ID, CABLE, FEEDS, TRANSFORMER
    )
    assert forward != reverse


def test_relationship_natural_key_matches_candidate_id_suffix():
    natural_key = relationship_natural_key(CABLE, FEEDS, TRANSFORMER)
    candidate_id = relationship_candidate_id(PROJECT_ID, CABLE, FEEDS, TRANSFORMER)
    assert candidate_id.endswith(natural_key)


def test_neighborhood_candidate_id_is_distinct_from_entity_candidate_id():
    assert neighborhood_candidate_id(PROJECT_ID, CABLE) != entity_candidate_id(
        PROJECT_ID, CABLE
    )
