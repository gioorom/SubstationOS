"""
Deterministic translation of a validated ``StructuredRetrievalRequest``
into a ``RetrievalQueryPlan`` - which Graph Query read operations the
request needs, and in what order its criteria are evaluated. Performs
no I/O and no database access: the plan is inspectable and testable on
its own, before any Graph Query call is made (Milestone 13's "Query
Planning" stage).
"""

from __future__ import annotations

from app.domain.structured_retrieval.structured_retrieval_factory import (
    CRITERION_ORDER,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalCriterionKind,
    RetrievalQueryOperation,
    RetrievalQueryPlan,
    StructuredRetrievalRequest,
)

# Which Graph Query operation(s) each criterion kind requires, in
# isolation. ATTRIBUTE_VALUE is a special case handled in ``plan()``:
# paired with ATTRIBUTE_NAME it only filters that already-planned
# fetch; alone, it requires its own full scan.
_OPERATIONS_FOR_KIND: dict[
    RetrievalCriterionKind, tuple[RetrievalQueryOperation, ...]
] = {
    RetrievalCriterionKind.CANONICAL_ENTITY_ID: (
        RetrievalQueryOperation.ENTITY_BY_ID,
    ),
    RetrievalCriterionKind.ENTITY_TYPE: (
        RetrievalQueryOperation.ENTITIES_BY_TYPE,
    ),
    RetrievalCriterionKind.ATTRIBUTE_NAME: (
        RetrievalQueryOperation.ENTITIES_BY_ATTRIBUTE,
    ),
    RetrievalCriterionKind.ATTRIBUTE_VALUE: (
        RetrievalQueryOperation.ALL_ENTITIES,
    ),
    RetrievalCriterionKind.RELATIONSHIP_TYPE: (
        RetrievalQueryOperation.ALL_RELATIONSHIPS,
    ),
    RetrievalCriterionKind.LEXICAL_TERM: (
        RetrievalQueryOperation.ALL_ENTITIES,
        RetrievalQueryOperation.ALL_RELATIONSHIPS,
    ),
}


class RetrievalQueryPlanner:
    @staticmethod
    def plan(request: StructuredRetrievalRequest) -> RetrievalQueryPlan:
        present_kinds = {criterion.kind for criterion in request.criteria}

        required: list[RetrievalQueryOperation] = []
        criterion_order: list[RetrievalCriterionKind] = []

        for kind in CRITERION_ORDER:
            if kind not in present_kinds:
                continue

            criterion_order.append(kind)

            if (
                kind is RetrievalCriterionKind.ATTRIBUTE_VALUE
                and RetrievalCriterionKind.ATTRIBUTE_NAME in present_kinds
            ):
                # Filters the ENTITIES_BY_ATTRIBUTE fetch ATTRIBUTE_NAME
                # already planned - not a second scan.
                continue

            for operation in _OPERATIONS_FOR_KIND[kind]:
                if operation not in required:
                    required.append(operation)

        optional: tuple[RetrievalQueryOperation, ...] = (
            (RetrievalQueryOperation.NEIGHBORHOOD,)
            if request.include_neighborhood
            else ()
        )

        return RetrievalQueryPlan(
            project_id=request.project_id,
            mode=request.mode,
            required_operations=tuple(required),
            optional_operations=optional,
            expand_neighborhood=request.include_neighborhood,
            neighborhood_depth=request.neighborhood_depth,
            max_candidates=request.limit,
            criterion_order=tuple(criterion_order),
        )
