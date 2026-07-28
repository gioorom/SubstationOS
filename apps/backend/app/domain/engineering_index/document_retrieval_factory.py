"""
Builds an immutable ``DocumentRetrievalRequest`` from the raw identifiers
and limit a caller supplies (CLAUDE.md §4.2 - a factory enforces
invariants at construction time).

Identifiers are trimmed, deduplicated case-insensitively (the Engineering
Index repository already matches case-insensitively, so "T2" and "t2"
would otherwise search twice for the same thing) and ordered
deterministically, so the same set of identifiers always produces the
same request regardless of the order a caller happened to supply them in.
"""

from __future__ import annotations

from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalRequest,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    BlankDocumentRetrievalRequestError,
    DocumentRetrievalIdentifierTooLongError,
    ExcessiveDocumentRetrievalIdentifierCountError,
    InvalidDocumentRetrievalLimitError,
    InvalidDocumentRetrievalProjectError,
)

MIN_DOCUMENT_RESULT_LIMIT = 1
MAX_DOCUMENT_RESULT_LIMIT = 200
MAX_DOCUMENT_IDENTIFIER_COUNT = 8
MAX_DOCUMENT_IDENTIFIER_LENGTH = 64


class DocumentRetrievalRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        identifiers: tuple[str, ...],
        limit: int,
    ) -> DocumentRetrievalRequest:
        if project_id <= 0:
            raise InvalidDocumentRetrievalProjectError(project_id)

        if not (
            MIN_DOCUMENT_RESULT_LIMIT <= limit <= MAX_DOCUMENT_RESULT_LIMIT
        ):
            raise InvalidDocumentRetrievalLimitError(
                limit, MIN_DOCUMENT_RESULT_LIMIT, MAX_DOCUMENT_RESULT_LIMIT
            )

        normalized = _normalize_identifiers(identifiers)

        if not normalized:
            raise BlankDocumentRetrievalRequestError()

        if len(normalized) > MAX_DOCUMENT_IDENTIFIER_COUNT:
            raise ExcessiveDocumentRetrievalIdentifierCountError(
                len(normalized), MAX_DOCUMENT_IDENTIFIER_COUNT
            )

        for identifier in normalized:
            if len(identifier) > MAX_DOCUMENT_IDENTIFIER_LENGTH:
                raise DocumentRetrievalIdentifierTooLongError(
                    identifier, MAX_DOCUMENT_IDENTIFIER_LENGTH
                )

        return DocumentRetrievalRequest(
            project_id=project_id,
            identifiers=normalized,
            limit=limit,
        )


def _normalize_identifiers(identifiers: tuple[str, ...]) -> tuple[str, ...]:
    """Trimmed, blank-free, case-insensitively deduplicated and sorted.
    The first spelling of a duplicated identifier is the one kept, so the
    identifier an engineer actually typed is what a reference reports as
    matched."""

    kept: dict[str, str] = {}

    for identifier in identifiers:
        trimmed = identifier.strip()

        if not trimmed:
            continue

        kept.setdefault(trimmed.casefold(), trimmed)

    return tuple(kept[key] for key in sorted(kept))
