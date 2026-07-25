"""
Application service for Structured Retrieval (EPIC 4, Milestone 13).
Orchestrates the domain pipeline - Query Planning -> Graph Query ->
Candidate Construction -> Deterministic Scoring ->
``KnowledgeCandidateCollection`` - through the existing
``GraphQueryRepository`` port and ``graph_query_service`` module,
never through ``GraphStore``, never through the legacy
``app.services.knowledge_graph`` path. No mutation is performed and no
persistence of retrieval results occurs in this milestone.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_repository import (
    GraphQueryRepository,
)
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
from app.domain.structured_retrieval.candidate_ranking import (
    CandidateRanker,
)
from app.domain.structured_retrieval.lexical_matching import (
    LEXICAL_NORMALIZATION_VERSION,
)
from app.domain.structured_retrieval.retrieval_query_planner import (
    RetrievalQueryPlanner,
)
from app.domain.structured_retrieval.scoring_policy import (
    SCORING_POLICY_VERSION,
)
from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    InvalidCanonicalEntityReferenceError,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    parse_canonical_entity_reference,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateCollection,
    KnowledgeCandidateKind,
    KnowledgeCandidateReference,
    RetrievalCriterion,
    RetrievalCriterionKind,
    RetrievalExecutionMetadata,
    RetrievalQueryOperation,
    RetrievalQueryPlan,
    RetrievalReason,
    StructuredRetrievalRequest,
    StructuredRetrievalResult,
)


def plan_retrieval(
    request: StructuredRetrievalRequest,
) -> RetrievalQueryPlan:
    """Query planning only - no Graph Query call. Lets a caller inspect
    what a request would do before executing it (the
    ``.../structured-retrieval/plan`` endpoint)."""

    return RetrievalQueryPlanner.plan(request)


def retrieve(
    repository: GraphQueryRepository,
    request: StructuredRetrievalRequest,
    *,
    now: datetime,
) -> StructuredRetrievalResult:
    start = time.perf_counter()
    plan = RetrievalQueryPlanner.plan(request)

    warnings: list[str] = []
    executed_operations: list[RetrievalQueryOperation] = []
    raw_candidates: list[KnowledgeCandidate] = []

    criteria_by_kind: dict[
        RetrievalCriterionKind, list[RetrievalCriterion]
    ] = {}
    for criterion in request.criteria:
        criteria_by_kind.setdefault(criterion.kind, []).append(criterion)

    cached_nodes: list | None = None
    cached_relationships: list | None = None

    def _all_nodes() -> list:
        nonlocal cached_nodes
        if cached_nodes is None:
            cached_nodes = repository.list_nodes(request.project_id)
            executed_operations.append(
                RetrievalQueryOperation.ALL_ENTITIES
            )
        return cached_nodes

    def _all_relationships() -> list:
        nonlocal cached_relationships
        if cached_relationships is None:
            cached_relationships = repository.list_relationships(
                request.project_id
            )
            executed_operations.append(
                RetrievalQueryOperation.ALL_RELATIONSHIPS
            )
        return cached_relationships

    for kind in plan.criterion_order:
        if kind is RetrievalCriterionKind.CANONICAL_ENTITY_ID:
            for criterion in criteria_by_kind[kind]:
                try:
                    entity_type, canonical_id = (
                        parse_canonical_entity_reference(criterion.value)
                    )
                except InvalidCanonicalEntityReferenceError:
                    warnings.append(
                        "Skipped malformed canonical entity reference: "
                        f"'{criterion.value}'."
                    )
                    continue

                graph_entity_id = GraphEntityId(
                    project_id=request.project_id,
                    entity_type=entity_type,
                    canonical_id=canonical_id,
                )
                node = repository.get_node(
                    request.project_id, graph_entity_id
                )
                executed_operations.append(
                    RetrievalQueryOperation.ENTITY_BY_ID
                )
                raw_candidates.extend(
                    match_entity_by_id(request.project_id, criterion, node)
                )

        elif kind is RetrievalCriterionKind.ENTITY_TYPE:
            for criterion in criteria_by_kind[kind]:
                nodes = repository.list_nodes_by_type(
                    request.project_id, criterion.value
                )
                executed_operations.append(
                    RetrievalQueryOperation.ENTITIES_BY_TYPE
                )
                raw_candidates.extend(
                    match_entities_by_type(
                        request.project_id, criterion, nodes
                    )
                )

        elif kind is RetrievalCriterionKind.RELATIONSHIP_TYPE:
            for criterion in criteria_by_kind[kind]:
                relationships = _all_relationships()
                raw_candidates.extend(
                    match_relationships_by_type(
                        request.project_id, criterion, relationships
                    )
                )

        elif kind is RetrievalCriterionKind.ATTRIBUTE_NAME:
            name_criterion = criteria_by_kind[kind][0]
            value_criteria = criteria_by_kind.get(
                RetrievalCriterionKind.ATTRIBUTE_VALUE, []
            )
            value_criterion = value_criteria[0] if value_criteria else None

            nodes = repository.list_nodes_with_attribute(
                request.project_id, name_criterion.value
            )
            executed_operations.append(
                RetrievalQueryOperation.ENTITIES_BY_ATTRIBUTE
            )
            raw_candidates.extend(
                match_entities_by_attribute(
                    request.project_id,
                    name_criterion,
                    value_criterion,
                    nodes,
                )
            )

        elif kind is RetrievalCriterionKind.ATTRIBUTE_VALUE:
            if RetrievalCriterionKind.ATTRIBUTE_NAME in criteria_by_kind:
                # Already handled together with ATTRIBUTE_NAME above.
                continue

            for criterion in criteria_by_kind[kind]:
                nodes = _all_nodes()
                raw_candidates.extend(
                    match_entities_by_attribute(
                        request.project_id, None, criterion, nodes
                    )
                )

        elif kind is RetrievalCriterionKind.LEXICAL_TERM:
            terms = criteria_by_kind[kind]
            nodes = _all_nodes()
            relationships = _all_relationships()
            raw_candidates.extend(
                match_lexical(
                    request.project_id,
                    terms,
                    request.lexical_match_mode,
                    nodes,
                    relationships,
                )
            )

    candidate_count_before_dedup = len(raw_candidates)
    merged = CandidateAggregator.merge(raw_candidates)
    candidate_count_after_dedup = len(merged)

    collection = CandidateRanker.rank_and_limit(
        merged, limit=request.limit
    )

    neighborhood_applied = False
    if request.include_neighborhood and collection.candidates:
        collection = _enrich_with_neighborhood(
            repository, request, collection
        )
        neighborhood_applied = True
        executed_operations.append(RetrievalQueryOperation.NEIGHBORHOOD)

    duration = time.perf_counter() - start

    metadata = RetrievalExecutionMetadata(
        executed_operations=tuple(dict.fromkeys(executed_operations)),
        candidate_count_before_dedup=candidate_count_before_dedup,
        candidate_count_after_dedup=candidate_count_after_dedup,
        final_returned_count=collection.returned_count,
        scoring_policy_version=SCORING_POLICY_VERSION,
        lexical_normalization_version=LEXICAL_NORMALIZATION_VERSION,
        neighborhood_enrichment_applied=neighborhood_applied,
        warnings=tuple(warnings),
        duration_seconds=duration,
    )

    return StructuredRetrievalResult(
        request=request,
        plan=plan,
        candidates=collection,
        metadata=metadata,
        requested_at=now,
    )


def _enrich_with_neighborhood(
    repository: GraphQueryRepository,
    request: StructuredRetrievalRequest,
    collection: KnowledgeCandidateCollection,
) -> KnowledgeCandidateCollection:
    """
    Enriches only the already-limited, final page of candidates - never
    the full pre-limit candidate pool - bounding neighborhood expansion
    to at most ``request.limit`` extra Graph Query round-trips
    (Milestone 13's Operational Safety: no unrestricted project-wide
    expansion). Each ``ENTITY``-kind candidate in the returned page
    gets its direct (1-hop) neighbors attached as ``related_entities``.
    """

    enriched: list[KnowledgeCandidate] = []

    for candidate in collection.candidates:
        if (
            candidate.candidate_kind is not KnowledgeCandidateKind.ENTITY
            or candidate.primary_reference is None
        ):
            enriched.append(candidate)
            continue

        graph_entity_id = candidate.primary_reference.graph_entity_id
        outgoing = repository.list_outgoing_relationships(
            request.project_id, graph_entity_id
        )
        incoming = repository.list_incoming_relationships(
            request.project_id, graph_entity_id
        )

        neighbor_ids: dict[str, GraphEntityId] = {}
        for relationship in outgoing:
            neighbor_ids[relationship.target_entity_id.value] = (
                relationship.target_entity_id
            )
        for relationship in incoming:
            neighbor_ids[relationship.source_entity_id.value] = (
                relationship.source_entity_id
            )

        neighbors: list[KnowledgeCandidateReference] = []
        for entity_id in neighbor_ids.values():
            node = repository.get_node(request.project_id, entity_id)
            if node is not None:
                neighbors.append(
                    KnowledgeCandidateReference(
                        graph_entity_id=node.graph_entity_id,
                        entity_type=node.entity_type,
                        canonical_id=node.canonical_id,
                    )
                )

        neighbors.sort(key=lambda reference: reference.graph_entity_id.value)

        enriched.append(replace(candidate, related_entities=tuple(neighbors)))

    return replace(collection, candidates=tuple(enriched))


def get_candidate(
    result: StructuredRetrievalResult, candidate_id: str
) -> KnowledgeCandidate | None:
    for candidate in result.candidates.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate

    return None


def explain_result(
    result: StructuredRetrievalResult,
) -> dict[str, tuple[RetrievalReason, ...]]:
    """A structured explanation view: for every returned candidate, the
    reasons that justified retrieving it."""

    return {
        candidate.candidate_id: candidate.reasons
        for candidate in result.candidates.candidates
    }
