from __future__ import annotations

from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalCriterionKind,
    RetrievalMode,
)


class StructuredRetrievalError(Exception):
    """Base class for every exception raised by the Structured
    Retrieval bounded context."""


class InvalidProjectIdError(StructuredRetrievalError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class MissingRetrievalCriterionError(StructuredRetrievalError):
    def __init__(self) -> None:
        super().__init__(
            "At least one meaningful retrieval criterion is required."
        )


class UnsupportedCriterionCombinationError(StructuredRetrievalError):
    """A request's criteria do not match what its ``RetrievalMode``
    supports - either an extra criterion kind the mode does not allow,
    or the mode's own required criterion kind is missing."""

    def __init__(
        self,
        mode: RetrievalMode,
        offending_kinds: tuple[RetrievalCriterionKind, ...],
    ) -> None:
        self.mode = mode
        self.offending_kinds = offending_kinds

        joined = ", ".join(kind.value for kind in offending_kinds)

        super().__init__(
            f"Retrieval mode '{mode.value}' does not support: {joined}."
        )


class InvalidRetrievalLimitError(StructuredRetrievalError):
    def __init__(self, limit: int, minimum: int, maximum: int) -> None:
        self.limit = limit

        super().__init__(
            f"Result limit {limit} is out of the supported range "
            f"[{minimum}, {maximum}]."
        )


class InvalidNeighborhoodDepthError(StructuredRetrievalError):
    def __init__(self, depth: int) -> None:
        self.depth = depth

        super().__init__(
            f"Unsupported neighborhood depth: {depth}. Depth must be 0, "
            "or 1 when include_neighborhood is true."
        )


class BlankLexicalTermError(StructuredRetrievalError):
    def __init__(self) -> None:
        super().__init__("A lexical term must not be blank.")


class ExcessiveLexicalTermCountError(StructuredRetrievalError):
    def __init__(self, count: int, maximum: int) -> None:
        self.count = count

        super().__init__(
            f"{count} lexical terms were requested, exceeding the "
            f"maximum of {maximum}."
        )


class LexicalTermTooLongError(StructuredRetrievalError):
    def __init__(self, term: str, maximum: int) -> None:
        self.term = term

        super().__init__(
            f"Lexical term '{term}' exceeds the maximum length of "
            f"{maximum} characters."
        )


class InvalidCanonicalEntityReferenceError(StructuredRetrievalError):
    def __init__(self, raw: str) -> None:
        self.raw = raw

        super().__init__(
            f"Invalid canonical entity reference: '{raw}'. Expected "
            "the form 'entity_type:canonical_id'."
        )
