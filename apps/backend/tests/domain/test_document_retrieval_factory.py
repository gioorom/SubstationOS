"""Domain tests for ``DocumentRetrievalRequestFactory`` (Milestone
23B.1). Pure and fast: no I/O, no database, no AI provider."""

from __future__ import annotations

import pytest

from app.domain.engineering_index.document_retrieval_factory import (
    MAX_DOCUMENT_IDENTIFIER_COUNT,
    MAX_DOCUMENT_IDENTIFIER_LENGTH,
    MAX_DOCUMENT_RESULT_LIMIT,
    DocumentRetrievalRequestFactory,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    BlankDocumentRetrievalRequestError,
    DocumentRetrievalIdentifierTooLongError,
    ExcessiveDocumentRetrievalIdentifierCountError,
    InvalidDocumentRetrievalLimitError,
    InvalidDocumentRetrievalProjectError,
)


def _create(**overrides):
    defaults = dict(project_id=1, identifiers=("T2",), limit=20)
    defaults.update(overrides)

    return DocumentRetrievalRequestFactory.create(**defaults)


def test_a_valid_request_is_built() -> None:
    request = _create(identifiers=("T2", "87T"), limit=5)

    assert request.project_id == 1
    assert request.limit == 5
    assert set(request.identifiers) == {"T2", "87T"}


def test_identifiers_are_trimmed() -> None:
    request = _create(identifiers=("  T2  ",))

    assert request.identifiers == ("T2",)


def test_blank_identifiers_are_dropped() -> None:
    request = _create(identifiers=("", "   ", "T2"))

    assert request.identifiers == ("T2",)


def test_identifiers_differing_only_in_case_are_deduplicated() -> None:
    """The Engineering Index already matches case-insensitively, so
    searching both spellings would search twice for the same thing - and
    would double-count the same document's evidence."""

    request = _create(identifiers=("T2", "t2", "T2"))

    assert request.identifiers == ("T2",)


def test_identifier_order_is_deterministic_regardless_of_caller_order() -> None:
    first = _create(identifiers=("87T", "T2", "L3"))
    second = _create(identifiers=("L3", "87T", "T2"))

    assert first.identifiers == second.identifiers


def test_the_spelling_the_engineer_typed_is_the_one_kept() -> None:
    request = _create(identifiers=("87t", "87T"))

    assert request.identifiers == ("87t",)


def test_a_request_naming_no_identifier_is_rejected() -> None:
    with pytest.raises(BlankDocumentRetrievalRequestError):
        _create(identifiers=())


def test_a_request_naming_only_blanks_is_rejected() -> None:
    with pytest.raises(BlankDocumentRetrievalRequestError):
        _create(identifiers=("", "  "))


def test_a_non_positive_project_id_is_rejected() -> None:
    with pytest.raises(InvalidDocumentRetrievalProjectError):
        _create(project_id=0)


@pytest.mark.parametrize("limit", [0, -1, MAX_DOCUMENT_RESULT_LIMIT + 1])
def test_an_out_of_range_limit_is_rejected(limit: int) -> None:
    with pytest.raises(InvalidDocumentRetrievalLimitError):
        _create(limit=limit)


def test_too_many_identifiers_are_rejected() -> None:
    identifiers = tuple(
        f"T{index}" for index in range(MAX_DOCUMENT_IDENTIFIER_COUNT + 1)
    )

    with pytest.raises(ExcessiveDocumentRetrievalIdentifierCountError):
        _create(identifiers=identifiers)


def test_an_overlong_identifier_is_rejected() -> None:
    with pytest.raises(DocumentRetrievalIdentifierTooLongError):
        _create(identifiers=("T" * (MAX_DOCUMENT_IDENTIFIER_LENGTH + 1),))
