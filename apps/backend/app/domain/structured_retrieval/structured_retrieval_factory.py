"""
Builds an immutable ``StructuredRetrievalRequest`` from the raw,
optional fields an API caller supplies (CLAUDE.md §4.2 - a factory
enforces invariants at construction time), and the small,
Structured-Retrieval-local parser for the ``"entity_type:canonical_id"``
criterion value format.
"""

from __future__ import annotations

from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    InvalidCanonicalEntityReferenceError,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    LexicalMatchMode,
    RetrievalCriterion,
    RetrievalCriterionKind,
    RetrievalMode,
    StructuredRetrievalRequest,
)
from app.domain.structured_retrieval.structured_retrieval_validator import (
    StructuredRetrievalValidator,
)

# Fixed, documented evaluation order - independent of the order an API
# caller happened to supply fields in, so query planning and candidate
# construction are deterministic (Milestone 13's "Query Planning" and
# "Result Ordering" requirements).
CRITERION_ORDER: tuple[RetrievalCriterionKind, ...] = (
    RetrievalCriterionKind.CANONICAL_ENTITY_ID,
    RetrievalCriterionKind.ENTITY_TYPE,
    RetrievalCriterionKind.RELATIONSHIP_TYPE,
    RetrievalCriterionKind.ATTRIBUTE_NAME,
    RetrievalCriterionKind.ATTRIBUTE_VALUE,
    RetrievalCriterionKind.LEXICAL_TERM,
)


class StructuredRetrievalRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        mode: RetrievalMode,
        limit: int,
        include_neighborhood: bool,
        neighborhood_depth: int,
        lexical_match_mode: LexicalMatchMode = LexicalMatchMode.ANY,
        canonical_entity_id: str | None = None,
        entity_type: str | None = None,
        attribute_name: str | None = None,
        attribute_value: str | None = None,
        relationship_type: str | None = None,
        lexical_terms: tuple[str, ...] = (),
    ) -> StructuredRetrievalRequest:
        StructuredRetrievalValidator.validate_project_id(project_id)
        StructuredRetrievalValidator.validate_limit(limit)
        StructuredRetrievalValidator.validate_neighborhood(
            include_neighborhood, neighborhood_depth
        )
        StructuredRetrievalValidator.validate_lexical_terms(lexical_terms)

        criteria: list[RetrievalCriterion] = []

        if canonical_entity_id is not None and canonical_entity_id.strip():
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.CANONICAL_ENTITY_ID,
                    value=canonical_entity_id.strip(),
                )
            )

        if entity_type is not None and entity_type.strip():
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.ENTITY_TYPE,
                    value=entity_type.strip(),
                )
            )

        if relationship_type is not None and relationship_type.strip():
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.RELATIONSHIP_TYPE,
                    value=relationship_type.strip(),
                )
            )

        if attribute_name is not None and attribute_name.strip():
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.ATTRIBUTE_NAME,
                    value=attribute_name.strip(),
                )
            )

        if attribute_value is not None and attribute_value.strip():
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.ATTRIBUTE_VALUE,
                    value=attribute_value.strip(),
                )
            )

        for term in lexical_terms:
            criteria.append(
                RetrievalCriterion(
                    kind=RetrievalCriterionKind.LEXICAL_TERM,
                    value=term.strip(),
                )
            )

        ordered_criteria = tuple(
            sorted(
                criteria,
                key=lambda criterion: (
                    CRITERION_ORDER.index(criterion.kind),
                    criterion.value,
                ),
            )
        )

        StructuredRetrievalValidator.validate_criteria(
            mode, ordered_criteria
        )

        return StructuredRetrievalRequest(
            project_id=project_id,
            mode=mode,
            criteria=ordered_criteria,
            limit=limit,
            include_neighborhood=include_neighborhood,
            neighborhood_depth=neighborhood_depth,
            lexical_match_mode=lexical_match_mode,
        )


def parse_canonical_entity_reference(raw: str) -> tuple[str, str]:
    """
    Splits a ``"entity_type:canonical_id"`` criterion value into its two
    parts. Deliberately local to Structured Retrieval rather than
    reusing ``project_knowledge_graph.graph_entity_id_codec`` - the
    format is trivial string parsing, not shared domain logic, and
    keeping it local avoids a dependency on Project Knowledge Graph that
    Structured Retrieval otherwise has no reason to take (it must not
    depend on Project Knowledge Graph's write ports; not depending on
    the bounded context at all is the more conservative choice).
    """

    entity_type, separator, canonical_id = raw.partition(":")

    if not separator or not entity_type or not canonical_id:
        raise InvalidCanonicalEntityReferenceError(raw)

    return entity_type, canonical_id
