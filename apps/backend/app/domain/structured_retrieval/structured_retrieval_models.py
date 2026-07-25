"""
Value objects for Structured Retrieval (EPIC 4, Milestone 13). Every
type here is immutable and deterministic: the same graph state and the
same ``StructuredRetrievalRequest`` always produce the same
``StructuredRetrievalResult``, including candidate identity and
ordering. No type in this module performs I/O, calls an AI provider, or
carries free-text intended for natural-language interpretation - every
request is a closed set of structured criteria, never a question.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)


class RetrievalMode(str, Enum):
    """Which shape of search a request performs - always stated
    explicitly by the caller, never inferred from free text."""

    ENTITY_LOOKUP = "entity_lookup"
    ENTITY_TYPE_SEARCH = "entity_type_search"
    ATTRIBUTE_SEARCH = "attribute_search"
    RELATIONSHIP_SEARCH = "relationship_search"
    LEXICAL_SEARCH = "lexical_search"
    COMBINED = "combined"


class RetrievalCriterionKind(str, Enum):
    CANONICAL_ENTITY_ID = "canonical_entity_id"
    ENTITY_TYPE = "entity_type"
    ATTRIBUTE_NAME = "attribute_name"
    ATTRIBUTE_VALUE = "attribute_value"
    RELATIONSHIP_TYPE = "relationship_type"
    LEXICAL_TERM = "lexical_term"


class LexicalMatchMode(str, Enum):
    """How multiple lexical terms combine when a request supplies more
    than one - explicit on the request (never inferred), per
    Milestone 13's "no NL intent detection" rule."""

    ANY = "any"
    ALL = "all"


class RetrievalQueryOperation(str, Enum):
    """Which Graph Query read capability a query plan intends to use -
    a closed, named set mirroring ``GraphQueryKind``, so a
    ``RetrievalQueryPlan`` is inspectable without executing it."""

    ENTITY_BY_ID = "entity_by_id"
    ENTITIES_BY_TYPE = "entities_by_type"
    ENTITIES_BY_ATTRIBUTE = "entities_by_attribute"
    ALL_ENTITIES = "all_entities"
    ALL_RELATIONSHIPS = "all_relationships"
    NEIGHBORHOOD = "neighborhood"


class KnowledgeCandidateKind(str, Enum):
    ENTITY = "entity"
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"
    NEIGHBORHOOD = "neighborhood"


class ScoreComponentCategory(str, Enum):
    EXACT_CANONICAL_ID_MATCH = "exact_canonical_id_match"
    NORMALIZED_IDENTIFIER_MATCH = "normalized_identifier_match"
    RELATIONSHIP_NATURAL_KEY_MATCH = "relationship_natural_key_match"
    RELATIONSHIP_TYPE_MATCH = "relationship_type_match"
    ENTITY_TYPE_MATCH = "entity_type_match"
    ATTRIBUTE_NAME_MATCH = "attribute_name_match"
    ATTRIBUTE_VALUE_MATCH = "attribute_value_match"
    LEXICAL_TOKEN_MATCH = "lexical_token_match"
    NEIGHBORHOOD_SUPPORT = "neighborhood_support"
    MULTI_CRITERION_SUPPORT = "multi_criterion_support"


@dataclass(frozen=True, slots=True)
class RetrievalCriterion:
    """One structured criterion supplied by the caller. ``value`` is
    always a plain string - kind-specific parsing (e.g. splitting a
    canonical entity reference into type/id) happens where a criterion
    is consumed, never here."""

    kind: RetrievalCriterionKind
    value: str


@dataclass(frozen=True, slots=True)
class StructuredRetrievalRequest:
    """
    A fully validated, canonically ordered retrieval request. Never
    constructed directly - always via
    ``StructuredRetrievalRequestFactory.create``, which enforces every
    invariant (non-empty criteria, mode/criterion compatibility, safe
    limits) at construction time.
    """

    project_id: int
    mode: RetrievalMode
    criteria: tuple[RetrievalCriterion, ...]
    limit: int
    include_neighborhood: bool
    neighborhood_depth: int
    lexical_match_mode: LexicalMatchMode


@dataclass(frozen=True, slots=True)
class RetrievalQueryPlan:
    """
    What a ``StructuredRetrievalRequest`` requires of Graph Query,
    decided once, deterministically, before any Graph Query call is
    made - inspectable and unit-testable on its own.
    """

    project_id: int
    mode: RetrievalMode
    required_operations: tuple[RetrievalQueryOperation, ...]
    optional_operations: tuple[RetrievalQueryOperation, ...]
    expand_neighborhood: bool
    neighborhood_depth: int
    max_candidates: int
    criterion_order: tuple[RetrievalCriterionKind, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateReference:
    """A lightweight pointer to one graph entity - Structured
    Retrieval's own reference type, never a reuse of Graph Query's
    ``GraphNodeView`` or Graph Persistence's ``ProjectGraphNode``, same
    "each layer owns its own read-oriented view" pattern those two
    bounded contexts already established."""

    graph_entity_id: GraphEntityId
    entity_type: str
    canonical_id: str


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateAttribute:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateRelationship:
    subject: KnowledgeCandidateReference
    relationship_type: GraphRelationshipType
    object: KnowledgeCandidateReference


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateScoreComponent:
    """One named, weighted contribution to a candidate's total score -
    see ``scoring_policy.py`` for the fixed, documented weight table.
    ``detail`` carries the specific matched value (a token, an
    attribute name, ...) so the component is self-explaining without
    cross-referencing the request."""

    category: ScoreComponentCategory
    weight: float
    detail: str


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateScore:
    """``total`` is always the sum of ``components`` - never set
    independently. Built exclusively by ``candidate_aggregation.py``,
    which owns recomputing it after merging duplicate evidence."""

    total: float
    components: tuple[KnowledgeCandidateScoreComponent, ...]


@dataclass(frozen=True, slots=True)
class RetrievalMatch:
    """Records that one of the request's own criteria contributed to a
    candidate - the "explicit indication of which requested criteria
    matched" Milestone 13 requires."""

    criterion_kind: RetrievalCriterionKind
    criterion_value: str


@dataclass(frozen=True, slots=True)
class RetrievalReason:
    """A human-readable explanation paired with the score category and
    criterion it corresponds to - every score component has exactly one
    matching reason."""

    category: ScoreComponentCategory
    criterion_kind: RetrievalCriterionKind
    description: str


@dataclass(frozen=True, slots=True)
class KnowledgeCandidate:
    """
    One retrieved piece of engineering knowledge - never a copy of a
    ``CanonicalFact``, ``ProposedClaim``, or document aggregate, only
    lightweight references and the evidence that justified retrieving
    it. ``candidate_id`` is deterministic (see ``candidate_identity.py``)
    and ``sort_key`` is precomputed by whichever stage last touched the
    candidate's score, so ranking never has to re-derive it.
    """

    candidate_id: str
    project_id: int
    candidate_kind: KnowledgeCandidateKind
    primary_reference: KnowledgeCandidateReference | None
    matched_attributes: tuple[KnowledgeCandidateAttribute, ...]
    matched_relationships: tuple[KnowledgeCandidateRelationship, ...]
    related_entities: tuple[KnowledgeCandidateReference, ...]
    source_fact_ids: tuple[int, ...]
    graph_node_ids: tuple[str, ...]
    graph_relationship_ids: tuple[str, ...]
    graph_execution_ids: tuple[int, ...]
    score: KnowledgeCandidateScore
    reasons: tuple[RetrievalReason, ...]
    matches: tuple[RetrievalMatch, ...]
    sort_key: tuple[float, int, str, str]


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateCollection:
    candidates: tuple[KnowledgeCandidate, ...]
    total_before_limit: int
    returned_count: int
    applied_limit: int


@dataclass(frozen=True, slots=True)
class RetrievalExecutionMetadata:
    """
    Non-sensitive execution metadata for one retrieval - never part of
    a candidate's or result's deterministic identity.
    ``duration_seconds`` deliberately varies run to run; tests must
    never assert on it (Milestone 13's "do not make duration part of
    deterministic equality tests").
    """

    executed_operations: tuple[RetrievalQueryOperation, ...]
    candidate_count_before_dedup: int
    candidate_count_after_dedup: int
    final_returned_count: int
    scoring_policy_version: str
    lexical_normalization_version: str
    neighborhood_enrichment_applied: bool
    warnings: tuple[str, ...]
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class StructuredRetrievalResult:
    request: StructuredRetrievalRequest
    plan: RetrievalQueryPlan
    candidates: KnowledgeCandidateCollection
    metadata: RetrievalExecutionMetadata
    requested_at: datetime
