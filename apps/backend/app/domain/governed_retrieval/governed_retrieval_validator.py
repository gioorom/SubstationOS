"""
The bounds every governed retrieval query obeys.

Checked at construction (``governed_retrieval_factory``), so an invalid
query cannot exist rather than being caught later by whoever happens to
read it. Each rule raises its own typed error carrying the offending
value, which is what lets the API answer ``422`` with a message an
engineer can act on instead of a stack trace.
"""

from __future__ import annotations

from app.domain.governed_retrieval.governed_normalization import (
    MAX_DESIGNATION_LENGTH,
    is_blank,
)
from app.domain.governed_retrieval.governed_retrieval_exceptions import (
    AmbiguousGovernedIdentityError,
    BlankDesignationError,
    BlankGovernedIdentityError,
    DesignationTooLongError,
    InvalidDocumentScopeError,
    InvalidProjectScopeError,
    InvalidResultLimitError,
    UnresolvableAssetSubjectError,
)

#: The same bounds Structured Retrieval used, kept deliberately: they
#: were chosen for operational safety rather than for the legacy graph's
#: shape, and changing them in a migration milestone would confuse a
#: behaviour change with a substrate change.
MIN_RESULT_LIMIT = 1
MAX_RESULT_LIMIT = 200
DEFAULT_RESULT_LIMIT = 20


def validate_limit(limit: int) -> None:
    if not MIN_RESULT_LIMIT <= limit <= MAX_RESULT_LIMIT:
        raise InvalidResultLimitError(
            limit, MIN_RESULT_LIMIT, MAX_RESULT_LIMIT
        )


def validate_designation(designation: str) -> None:
    if is_blank(designation):
        raise BlankDesignationError()

    if len(designation) > MAX_DESIGNATION_LENGTH:
        raise DesignationTooLongError(
            len(designation), MAX_DESIGNATION_LENGTH
        )


def validate_project_scope(project_id: int | None) -> None:
    if project_id is not None and project_id <= 0:
        raise InvalidProjectScopeError(project_id)


def validate_document_scope(document_id: int | None) -> None:
    if document_id is not None and document_id <= 0:
        raise InvalidDocumentScopeError(document_id)


def validate_required_document_scope(document_id: int) -> None:
    if document_id <= 0:
        raise InvalidDocumentScopeError(document_id)


def validate_governed_identity(
    node_id: str | None, edge_id: str | None
) -> None:
    """Exactly one governed object per identity query - never both, and
    never neither."""

    named = [
        value for value in (node_id, edge_id) if value and value.strip()
    ]

    if not named:
        raise BlankGovernedIdentityError()

    if node_id and node_id.strip() and edge_id and edge_id.strip():
        raise AmbiguousGovernedIdentityError()


def validate_asset_subject(
    designation: str | None, subject_node_id: str | None
) -> None:
    """
    A quantity query names its asset one way or the other.

    Both together is rejected rather than resolved: a designation and an
    id that disagreed would leave retrieval choosing which one the
    engineer meant, and that is not a choice retrieval may make.
    """

    by_designation = bool(designation and designation.strip())
    by_identity = bool(subject_node_id and subject_node_id.strip())

    if by_designation == by_identity:
        raise UnresolvableAssetSubjectError()

    if by_designation:
        validate_designation(designation or "")
