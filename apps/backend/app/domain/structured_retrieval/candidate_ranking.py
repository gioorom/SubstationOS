"""
Result Ordering (Milestone 13). Candidates are sorted by
``sort_key`` - ``(-total_score, candidate_kind_priority, natural_key,
candidate_id)``, precomputed by ``candidate_aggregation.py`` - and the
result limit is applied only after full deduplication and ranking,
never before, so the returned page is always the true top-N.
"""

from __future__ import annotations

from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateCollection,
)


class CandidateRanker:
    @staticmethod
    def rank_and_limit(
        candidates: tuple[KnowledgeCandidate, ...],
        *,
        limit: int,
    ) -> KnowledgeCandidateCollection:
        ordered = tuple(sorted(candidates, key=lambda c: c.sort_key))
        limited = ordered[:limit]

        return KnowledgeCandidateCollection(
            candidates=limited,
            total_before_limit=len(ordered),
            returned_count=len(limited),
            applied_limit=limit,
        )
