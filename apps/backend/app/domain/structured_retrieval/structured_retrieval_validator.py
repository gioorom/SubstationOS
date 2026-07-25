from __future__ import annotations

from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    BlankLexicalTermError,
    ExcessiveLexicalTermCountError,
    InvalidNeighborhoodDepthError,
    InvalidProjectIdError,
    InvalidRetrievalLimitError,
    LexicalTermTooLongError,
    MissingRetrievalCriterionError,
    UnsupportedCriterionCombinationError,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalCriterion,
    RetrievalCriterionKind,
    RetrievalMode,
)

MIN_RESULT_LIMIT = 1
MAX_RESULT_LIMIT = 200
MAX_LEXICAL_TERM_COUNT = 8
MAX_LEXICAL_TERM_LENGTH = 64
_SUPPORTED_NEIGHBORHOOD_DEPTH = 1

# Which criterion kind(s) each single-purpose mode requires at least
# one of. Every mode but ATTRIBUTE_SEARCH requires exactly one specific
# kind; ATTRIBUTE_SEARCH accepts either ATTRIBUTE_NAME (attribute
# presence, optionally narrowed by ATTRIBUTE_VALUE) or ATTRIBUTE_VALUE
# alone (any attribute with this value, across all nodes). COMBINED has
# no required kind of its own - any non-empty mix of allowed kinds
# satisfies it.
_REQUIRED_ANY_OF_KINDS_FOR_MODE: dict[
    RetrievalMode, frozenset[RetrievalCriterionKind]
] = {
    RetrievalMode.ENTITY_LOOKUP: frozenset(
        {RetrievalCriterionKind.CANONICAL_ENTITY_ID}
    ),
    RetrievalMode.ENTITY_TYPE_SEARCH: frozenset(
        {RetrievalCriterionKind.ENTITY_TYPE}
    ),
    RetrievalMode.ATTRIBUTE_SEARCH: frozenset(
        {
            RetrievalCriterionKind.ATTRIBUTE_NAME,
            RetrievalCriterionKind.ATTRIBUTE_VALUE,
        }
    ),
    RetrievalMode.RELATIONSHIP_SEARCH: frozenset(
        {RetrievalCriterionKind.RELATIONSHIP_TYPE}
    ),
    RetrievalMode.LEXICAL_SEARCH: frozenset(
        {RetrievalCriterionKind.LEXICAL_TERM}
    ),
}

# Which criterion kinds each mode tolerates at all. A single-purpose
# mode mixed with a criterion kind outside its own set is rejected
# explicitly, rather than silently ignored - "unsupported combinations
# must fail explicitly" (Milestone 13).
_ALLOWED_KINDS_FOR_MODE: dict[
    RetrievalMode, frozenset[RetrievalCriterionKind]
] = {
    RetrievalMode.ENTITY_LOOKUP: frozenset(
        {RetrievalCriterionKind.CANONICAL_ENTITY_ID}
    ),
    RetrievalMode.ENTITY_TYPE_SEARCH: frozenset(
        {RetrievalCriterionKind.ENTITY_TYPE}
    ),
    RetrievalMode.ATTRIBUTE_SEARCH: frozenset(
        {
            RetrievalCriterionKind.ATTRIBUTE_NAME,
            RetrievalCriterionKind.ATTRIBUTE_VALUE,
        }
    ),
    RetrievalMode.RELATIONSHIP_SEARCH: frozenset(
        {RetrievalCriterionKind.RELATIONSHIP_TYPE}
    ),
    RetrievalMode.LEXICAL_SEARCH: frozenset(
        {RetrievalCriterionKind.LEXICAL_TERM}
    ),
    RetrievalMode.COMBINED: frozenset(RetrievalCriterionKind),
}


class StructuredRetrievalValidator:
    """Stateless validation rules for Structured Retrieval, shared by
    ``StructuredRetrievalRequestFactory``."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_limit(limit: int) -> None:
        if not (MIN_RESULT_LIMIT <= limit <= MAX_RESULT_LIMIT):
            raise InvalidRetrievalLimitError(
                limit, MIN_RESULT_LIMIT, MAX_RESULT_LIMIT
            )

    @staticmethod
    def validate_neighborhood(
        include_neighborhood: bool, depth: int
    ) -> None:
        if include_neighborhood:
            if depth != _SUPPORTED_NEIGHBORHOOD_DEPTH:
                raise InvalidNeighborhoodDepthError(depth)
        elif depth != 0:
            raise InvalidNeighborhoodDepthError(depth)

    @staticmethod
    def validate_lexical_terms(terms: tuple[str, ...]) -> None:
        if len(terms) > MAX_LEXICAL_TERM_COUNT:
            raise ExcessiveLexicalTermCountError(
                len(terms), MAX_LEXICAL_TERM_COUNT
            )

        for term in terms:
            if not term or not term.strip():
                raise BlankLexicalTermError()

            if len(term) > MAX_LEXICAL_TERM_LENGTH:
                raise LexicalTermTooLongError(term, MAX_LEXICAL_TERM_LENGTH)

    @staticmethod
    def validate_criteria(
        mode: RetrievalMode,
        criteria: tuple[RetrievalCriterion, ...],
    ) -> None:
        if not criteria:
            raise MissingRetrievalCriterionError()

        allowed = _ALLOWED_KINDS_FOR_MODE[mode]
        present_kinds = {criterion.kind for criterion in criteria}

        offending = tuple(
            sorted(
                (kind for kind in present_kinds if kind not in allowed),
                key=lambda kind: kind.value,
            )
        )
        if offending:
            raise UnsupportedCriterionCombinationError(mode, offending)

        required_any_of = _REQUIRED_ANY_OF_KINDS_FOR_MODE.get(mode)
        if required_any_of is not None and not (
            required_any_of & present_kinds
        ):
            raise UnsupportedCriterionCombinationError(
                mode,
                tuple(
                    sorted(required_any_of, key=lambda kind: kind.value)
                ),
            )
