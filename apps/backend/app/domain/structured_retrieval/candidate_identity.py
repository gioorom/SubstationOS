"""
Deterministic candidate identity (Milestone 13). No random UUID
generation: a candidate's ``candidate_id`` is always derived from the
semantic identity of the project, candidate kind, and the primary
entity/relationship/attribute it represents - so the same graph state
and the same request always produce the same identifiers.
"""

from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateKind,
)


def entity_candidate_id(
    project_id: int, graph_entity_id: GraphEntityId
) -> str:
    return (
        f"{project_id}:{KnowledgeCandidateKind.ENTITY.value}:"
        f"{graph_entity_id.value}"
    )


def attribute_candidate_id(
    project_id: int,
    graph_entity_id: GraphEntityId,
    attribute_name: str,
) -> str:
    return (
        f"{project_id}:{KnowledgeCandidateKind.ATTRIBUTE.value}:"
        f"{graph_entity_id.value}:{attribute_name}"
    )


def relationship_natural_key(
    subject_id: GraphEntityId,
    relationship_type: GraphRelationshipType,
    object_id: GraphEntityId,
) -> str:
    return f"{subject_id.value}|{relationship_type.value}|{object_id.value}"


def relationship_candidate_id(
    project_id: int,
    subject_id: GraphEntityId,
    relationship_type: GraphRelationshipType,
    object_id: GraphEntityId,
) -> str:
    natural_key = relationship_natural_key(
        subject_id, relationship_type, object_id
    )

    return (
        f"{project_id}:{KnowledgeCandidateKind.RELATIONSHIP.value}:"
        f"{natural_key}"
    )


def neighborhood_candidate_id(
    project_id: int, graph_entity_id: GraphEntityId
) -> str:
    return (
        f"{project_id}:{KnowledgeCandidateKind.NEIGHBORHOOD.value}:"
        f"{graph_entity_id.value}"
    )
