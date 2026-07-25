"""
Deduplication and Aggregation (Milestone 13's pipeline stage of the
same name). The same logical entity/relationship/attribute may be
discovered through more than one criterion - this module merges those
raw, single-component candidates (sharing the same ``candidate_id``)
into one candidate per logical result, unioning evidence rather than
duplicating it, and computes the final, deterministic score and sort
key. Never fetches data and never re-derives a match on its own -
purely a merge over already-constructed ``KnowledgeCandidate`` objects.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.structured_retrieval import scoring_policy
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateKind,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    ScoreComponentCategory,
)

# Lower sorts first - documented in docs/architecture/structured_retrieval.md
# "Result Ordering": a candidate that IS the matched entity ranks above
# one that only relates to it, which ranks above a bare attribute
# match, which ranks above neighborhood-only context.
_KIND_PRIORITY: dict[KnowledgeCandidateKind, int] = {
    KnowledgeCandidateKind.ENTITY: 0,
    KnowledgeCandidateKind.RELATIONSHIP: 1,
    KnowledgeCandidateKind.ATTRIBUTE: 2,
    KnowledgeCandidateKind.NEIGHBORHOOD: 3,
}


def _natural_key(candidate: KnowledgeCandidate) -> str:
    if candidate.primary_reference is not None:
        return candidate.primary_reference.canonical_id

    if candidate.graph_relationship_ids:
        return candidate.graph_relationship_ids[0]

    return candidate.candidate_id


class CandidateAggregator:
    @staticmethod
    def merge(
        raw_candidates: list[KnowledgeCandidate],
    ) -> tuple[KnowledgeCandidate, ...]:
        groups: dict[str, list[KnowledgeCandidate]] = {}
        order: list[str] = []

        for candidate in raw_candidates:
            if candidate.candidate_id not in groups:
                groups[candidate.candidate_id] = []
                order.append(candidate.candidate_id)
            groups[candidate.candidate_id].append(candidate)

        return tuple(
            CandidateAggregator._merge_group(groups[candidate_id])
            for candidate_id in order
        )

    @staticmethod
    def _merge_group(
        group: list[KnowledgeCandidate],
    ) -> KnowledgeCandidate:
        first = group[0]

        components: dict[
            tuple[ScoreComponentCategory, str], KnowledgeCandidateScoreComponent
        ] = {}
        reasons: dict[tuple, object] = {}
        matches: dict[tuple, object] = {}
        matched_attributes: dict[tuple, object] = {}
        matched_relationships: dict[tuple, object] = {}
        related_entities: dict[str, object] = {}
        graph_node_ids: list[str] = []
        graph_relationship_ids: list[str] = []
        graph_execution_ids: set[int] = set()
        source_fact_ids: set[int] = set()
        seen_criterion_kinds: set = set()

        for candidate in group:
            for component in candidate.score.components:
                key = (component.category, component.detail)
                components.setdefault(key, component)

            for reason in candidate.reasons:
                key = (
                    reason.category,
                    reason.criterion_kind,
                    reason.description,
                )
                reasons.setdefault(key, reason)

            for match in candidate.matches:
                key = (match.criterion_kind, match.criterion_value)
                matches.setdefault(key, match)
                seen_criterion_kinds.add(match.criterion_kind)

            for attribute in candidate.matched_attributes:
                matched_attributes.setdefault(
                    (attribute.name, attribute.value), attribute
                )

            for relationship in candidate.matched_relationships:
                key = (
                    relationship.subject.graph_entity_id.value,
                    relationship.relationship_type.value,
                    relationship.object.graph_entity_id.value,
                )
                matched_relationships.setdefault(key, relationship)

            for reference in candidate.related_entities:
                related_entities.setdefault(
                    reference.graph_entity_id.value, reference
                )

            for node_id in candidate.graph_node_ids:
                if node_id not in graph_node_ids:
                    graph_node_ids.append(node_id)

            for relationship_id in candidate.graph_relationship_ids:
                if relationship_id not in graph_relationship_ids:
                    graph_relationship_ids.append(relationship_id)

            graph_execution_ids.update(candidate.graph_execution_ids)
            source_fact_ids.update(candidate.source_fact_ids)

        distinct_criterion_kinds = len(seen_criterion_kinds)
        if distinct_criterion_kinds > 1:
            bonus_weight = scoring_policy.WEIGHT_MULTI_CRITERION_SUPPORT * (
                distinct_criterion_kinds - 1
            )
            bonus_key = (
                ScoreComponentCategory.MULTI_CRITERION_SUPPORT,
                str(distinct_criterion_kinds),
            )
            components[bonus_key] = KnowledgeCandidateScoreComponent(
                category=ScoreComponentCategory.MULTI_CRITERION_SUPPORT,
                weight=bonus_weight,
                detail=f"{distinct_criterion_kinds} distinct criteria matched",
            )

        final_components = tuple(
            sorted(
                components.values(),
                key=lambda component: (component.category.value, component.detail),
            )
        )
        total = sum(component.weight for component in final_components)

        score = KnowledgeCandidateScore(
            total=total, components=final_components
        )

        natural_key = _natural_key(first)
        sort_key = (
            -total,
            _KIND_PRIORITY[first.candidate_kind],
            natural_key,
            first.candidate_id,
        )

        return replace(
            first,
            matched_attributes=tuple(
                sorted(
                    matched_attributes.values(),
                    key=lambda attribute: (attribute.name, attribute.value),
                )
            ),
            matched_relationships=tuple(
                sorted(
                    matched_relationships.values(),
                    key=lambda relationship: (
                        relationship.subject.graph_entity_id.value,
                        relationship.relationship_type.value,
                        relationship.object.graph_entity_id.value,
                    ),
                )
            ),
            related_entities=tuple(
                sorted(
                    related_entities.values(),
                    key=lambda reference: reference.graph_entity_id.value,
                )
            ),
            source_fact_ids=tuple(sorted(source_fact_ids)),
            graph_node_ids=tuple(sorted(graph_node_ids)),
            graph_relationship_ids=tuple(sorted(graph_relationship_ids)),
            graph_execution_ids=tuple(sorted(graph_execution_ids)),
            score=score,
            reasons=tuple(
                sorted(
                    reasons.values(),
                    key=lambda reason: (
                        reason.category.value,
                        reason.criterion_kind.value,
                        reason.description,
                    ),
                )
            ),
            matches=tuple(
                sorted(
                    matches.values(),
                    key=lambda match: (
                        match.criterion_kind.value,
                        match.criterion_value,
                    ),
                )
            ),
            sort_key=sort_key,
        )
