from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateKind,
    LexicalMatchMode,
    RetrievalCriterionKind,
    RetrievalMode,
    RetrievalQueryOperation,
    ScoreComponentCategory,
)
from app.schemas.graph_builder import GraphEntityIdRead, GraphRelationshipTypeRead


class StructuredRetrievalSearchRequest(BaseModel):
    """
    A structured retrieval request body. ``project_id`` is deliberately
    absent - the path's own ``{project_id}`` is authoritative (Milestone
    13's API requirement). Every optional field below maps to at most
    one ``RetrievalCriterion``; ``lexical_terms`` is the only field that
    may produce more than one.
    """

    mode: RetrievalMode
    limit: int = Field(default=20, ge=1, le=200)
    include_neighborhood: bool = False
    neighborhood_depth: int = 0
    lexical_match_mode: LexicalMatchMode = LexicalMatchMode.ANY

    canonical_entity_id: str | None = None
    entity_type: str | None = None
    attribute_name: str | None = None
    attribute_value: str | None = None
    relationship_type: str | None = None
    lexical_terms: list[str] = Field(default_factory=list)


class KnowledgeCandidateReferenceRead(BaseModel):
    graph_entity_id: GraphEntityIdRead
    entity_type: str
    canonical_id: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateAttributeRead(BaseModel):
    name: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateRelationshipRead(BaseModel):
    subject: KnowledgeCandidateReferenceRead
    relationship_type: GraphRelationshipTypeRead
    object: KnowledgeCandidateReferenceRead

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateScoreComponentRead(BaseModel):
    category: ScoreComponentCategory
    weight: float
    detail: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateScoreRead(BaseModel):
    total: float
    components: list[KnowledgeCandidateScoreComponentRead]

    model_config = ConfigDict(from_attributes=True)


class RetrievalMatchRead(BaseModel):
    criterion_kind: RetrievalCriterionKind
    criterion_value: str

    model_config = ConfigDict(from_attributes=True)


class RetrievalReasonRead(BaseModel):
    category: ScoreComponentCategory
    criterion_kind: RetrievalCriterionKind
    description: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateRead(BaseModel):
    """
    Deliberately does not expose ``sort_key`` - an internal ranking
    aid, not meaningful to an API consumer (ordering is already
    reflected by the candidate's position in ``candidates``).
    """

    candidate_id: str
    project_id: int
    candidate_kind: KnowledgeCandidateKind
    primary_reference: KnowledgeCandidateReferenceRead | None
    matched_attributes: list[KnowledgeCandidateAttributeRead]
    matched_relationships: list[KnowledgeCandidateRelationshipRead]
    related_entities: list[KnowledgeCandidateReferenceRead]
    source_fact_ids: list[int]
    graph_node_ids: list[str]
    graph_relationship_ids: list[str]
    graph_execution_ids: list[int]
    score: KnowledgeCandidateScoreRead
    reasons: list[RetrievalReasonRead]
    matches: list[RetrievalMatchRead]

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCandidateCollectionRead(BaseModel):
    candidates: list[KnowledgeCandidateRead]
    total_before_limit: int
    returned_count: int
    applied_limit: int

    model_config = ConfigDict(from_attributes=True)


class RetrievalCriterionRead(BaseModel):
    kind: RetrievalCriterionKind
    value: str

    model_config = ConfigDict(from_attributes=True)


class StructuredRetrievalRequestRead(BaseModel):
    """The normalized request actually executed - echoes back the
    canonically ordered criteria the factory derived from the raw
    request body."""

    project_id: int
    mode: RetrievalMode
    criteria: list[RetrievalCriterionRead]
    limit: int
    include_neighborhood: bool
    neighborhood_depth: int
    lexical_match_mode: LexicalMatchMode

    model_config = ConfigDict(from_attributes=True)


class RetrievalQueryPlanRead(BaseModel):
    project_id: int
    mode: RetrievalMode
    required_operations: list[RetrievalQueryOperation]
    optional_operations: list[RetrievalQueryOperation]
    expand_neighborhood: bool
    neighborhood_depth: int
    max_candidates: int
    criterion_order: list[RetrievalCriterionKind]

    model_config = ConfigDict(from_attributes=True)


class RetrievalExecutionMetadataRead(BaseModel):
    executed_operations: list[RetrievalQueryOperation]
    candidate_count_before_dedup: int
    candidate_count_after_dedup: int
    final_returned_count: int
    scoring_policy_version: str
    lexical_normalization_version: str
    neighborhood_enrichment_applied: bool
    warnings: list[str]
    duration_seconds: float | None = None

    model_config = ConfigDict(from_attributes=True)


class StructuredRetrievalResultRead(BaseModel):
    request: StructuredRetrievalRequestRead
    plan: RetrievalQueryPlanRead
    candidates: KnowledgeCandidateCollectionRead
    metadata: RetrievalExecutionMetadataRead
    requested_at: datetime

    model_config = ConfigDict(from_attributes=True)
