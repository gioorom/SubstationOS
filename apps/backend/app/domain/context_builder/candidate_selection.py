"""
Selection (Milestone 14's pipeline stage of the same name). Ranks the
incoming ``KnowledgeCandidate`` tuple deterministically - highest score,
then candidate kind priority, then entity/natural identity, then
candidate identity, exactly the ordering
``docs/architecture/structured_retrieval.md``'s "Result Ordering"
documents for ``KnowledgeCandidate.sort_key`` - and admits candidates
into the package up to the configured ``BudgetPolicy`` limits (an
overall candidate cap, plus a per-kind cap for entities, relationships,
and attributes; ``NEIGHBORHOOD``-kind candidates are bounded only by
the overall cap, since Milestone 14 defines no dedicated neighborhood
budget dimension).

Deliberately does not trust ``KnowledgeCandidate.sort_key`` itself: that
field is Structured Retrieval's own internal ranking aid, is never
exposed on the wire by ``KnowledgeCandidateRead`` (Context Builder's own
API input shape), and re-deriving the documented ordering from public
fields here is Context Builder's own Selection responsibility, not a
re-scoring of anything Structured Retrieval already decided.

No I/O. Linear scan after one O(n log n) sort - see module-level
``select_candidates`` docstring for the full complexity statement.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    BudgetPolicy,
    DiscardedCandidate,
    SelectionOutcome,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateKind,
)

# Lower sorts first - mirrors Structured Retrieval's own documented
# candidate-kind priority (structured_retrieval.md, "Result Ordering").
_KIND_PRIORITY: dict[KnowledgeCandidateKind, int] = {
    KnowledgeCandidateKind.ENTITY: 0,
    KnowledgeCandidateKind.RELATIONSHIP: 1,
    KnowledgeCandidateKind.ATTRIBUTE: 2,
    KnowledgeCandidateKind.NEIGHBORHOOD: 3,
}

# Only these three kinds have a dedicated per-kind budget dimension
# (Milestone 14's "maximum entities/relationships/attributes"); a
# NEIGHBORHOOD-kind candidate is bounded only by max_candidates.
_BUDGET_CATEGORY_FOR_KIND: dict[KnowledgeCandidateKind, BudgetCategory] = {
    KnowledgeCandidateKind.ENTITY: BudgetCategory.ENTITIES,
    KnowledgeCandidateKind.RELATIONSHIP: BudgetCategory.RELATIONSHIPS,
    KnowledgeCandidateKind.ATTRIBUTE: BudgetCategory.ATTRIBUTES,
}


def _natural_key(candidate: KnowledgeCandidate) -> str:
    if candidate.primary_reference is not None:
        return candidate.primary_reference.canonical_id

    if candidate.graph_relationship_ids:
        return candidate.graph_relationship_ids[0]

    return candidate.candidate_id


def _selection_key(
    candidate: KnowledgeCandidate,
) -> tuple[float, int, str, str]:
    return (
        -candidate.score.total,
        _KIND_PRIORITY[candidate.candidate_kind],
        _natural_key(candidate),
        candidate.candidate_id,
    )


def _consumption(
    category: BudgetCategory, *, requested: int, accepted: int, limit: int
) -> BudgetConsumption:
    return BudgetConsumption(
        category=category,
        requested=requested,
        accepted=accepted,
        discarded=requested - accepted,
        limit=limit,
        utilization=0.0 if limit == 0 else accepted / limit,
    )


def select_candidates(
    candidates: tuple[KnowledgeCandidate, ...],
    budget_policy: BudgetPolicy,
) -> SelectionOutcome:
    """
    O(n log n) in ``len(candidates)`` (the ranking sort); every other
    step is a single O(n) linear pass. A candidate whose own kind has
    already reached its per-kind cap is skipped without consuming the
    overall budget, so a lower-ranked candidate of a still-open kind
    further down the ranked list can still be admitted - one linear
    scan, no backtracking, fully deterministic for a given input tuple
    and policy.
    """

    ranked = sorted(candidates, key=_selection_key)

    kind_limits: dict[KnowledgeCandidateKind, int | None] = {
        KnowledgeCandidateKind.ENTITY: budget_policy.max_entities,
        KnowledgeCandidateKind.RELATIONSHIP: budget_policy.max_relationships,
        KnowledgeCandidateKind.ATTRIBUTE: budget_policy.max_attributes,
        KnowledgeCandidateKind.NEIGHBORHOOD: None,
    }
    kind_requested: dict[KnowledgeCandidateKind, int] = {
        kind: 0 for kind in KnowledgeCandidateKind
    }
    kind_accepted: dict[KnowledgeCandidateKind, int] = {
        kind: 0 for kind in KnowledgeCandidateKind
    }

    selected: list[KnowledgeCandidate] = []
    discarded: list[DiscardedCandidate] = []

    for candidate in ranked:
        kind_requested[candidate.candidate_kind] += 1

        if len(selected) >= budget_policy.max_candidates:
            discarded.append(
                DiscardedCandidate(
                    candidate=candidate, reason=BudgetCategory.CANDIDATES
                )
            )
            continue

        kind_limit = kind_limits[candidate.candidate_kind]
        if (
            kind_limit is not None
            and kind_accepted[candidate.candidate_kind] >= kind_limit
        ):
            discarded.append(
                DiscardedCandidate(
                    candidate=candidate,
                    reason=_BUDGET_CATEGORY_FOR_KIND[candidate.candidate_kind],
                )
            )
            continue

        selected.append(candidate)
        kind_accepted[candidate.candidate_kind] += 1

    consumption = (
        _consumption(
            BudgetCategory.CANDIDATES,
            requested=len(ranked),
            accepted=len(selected),
            limit=budget_policy.max_candidates,
        ),
        _consumption(
            BudgetCategory.ENTITIES,
            requested=kind_requested[KnowledgeCandidateKind.ENTITY],
            accepted=kind_accepted[KnowledgeCandidateKind.ENTITY],
            limit=budget_policy.max_entities,
        ),
        _consumption(
            BudgetCategory.RELATIONSHIPS,
            requested=kind_requested[KnowledgeCandidateKind.RELATIONSHIP],
            accepted=kind_accepted[KnowledgeCandidateKind.RELATIONSHIP],
            limit=budget_policy.max_relationships,
        ),
        _consumption(
            BudgetCategory.ATTRIBUTES,
            requested=kind_requested[KnowledgeCandidateKind.ATTRIBUTE],
            accepted=kind_accepted[KnowledgeCandidateKind.ATTRIBUTE],
            limit=budget_policy.max_attributes,
        ),
    )

    return SelectionOutcome(
        selected=tuple(selected),
        discarded=tuple(discarded),
        consumption=consumption,
    )
