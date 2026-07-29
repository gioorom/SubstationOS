"""
The Shared Kernel's pagination contract.

Pure value-object tests: no database, no HTTP. The point of validating at
construction is that these are the *only* rules, enforced once, so no
repository has to defend against a bad page.
"""

from __future__ import annotations

import pytest

from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
    PageRequest,
    SortDirection,
)
from app.domain.shared_kernel.pagination_exceptions import (
    InvalidPageError,
    InvalidPageSizeError,
)


def test_a_default_request_asks_for_the_first_page() -> None:
    request = PageRequest()

    assert request.page == 1
    assert request.page_size == DEFAULT_PAGE_SIZE
    assert request.offset == 0


def test_the_offset_is_derived_from_the_page() -> None:
    """The one place the page-based contract becomes the offset a query
    needs."""

    assert PageRequest(page=1, page_size=25).offset == 0
    assert PageRequest(page=2, page_size=25).offset == 25
    assert PageRequest(page=4, page_size=10).offset == 30


@pytest.mark.parametrize("page", [0, -1, -100])
def test_a_page_below_one_is_refused(page: int) -> None:
    with pytest.raises(InvalidPageError):
        PageRequest(page=page)


@pytest.mark.parametrize(
    "page_size", [0, -1, MAX_PAGE_SIZE + 1, 10_000]
)
def test_a_page_size_outside_the_range_is_refused(page_size: int) -> None:
    """Refused, never clamped: a caller who asked for 10 000 and silently
    received 100 would believe it had read the whole registry."""

    with pytest.raises(InvalidPageSizeError):
        PageRequest(page_size=page_size)


def test_the_maximum_page_size_is_itself_accepted() -> None:
    assert PageRequest(page_size=MAX_PAGE_SIZE).page_size == MAX_PAGE_SIZE


def test_the_refusal_names_the_maximum() -> None:
    """An error a caller can act on says what the limit is."""

    with pytest.raises(InvalidPageSizeError) as failure:
        PageRequest(page_size=MAX_PAGE_SIZE + 1)

    assert str(MAX_PAGE_SIZE) in str(failure.value)
    assert failure.value.maximum == MAX_PAGE_SIZE


# --- Page metadata --------------------------------------------------------


def _page(total: int, page: int, page_size: int) -> Page[int]:
    return Page.of(
        tuple(range(page_size)),
        total=total,
        request=PageRequest(page=page, page_size=page_size),
    )


def test_a_full_first_page_has_a_next_and_no_previous() -> None:
    result = _page(total=30, page=1, page_size=10)

    assert result.has_next is True
    assert result.has_previous is False


def test_the_last_page_has_a_previous_and_no_next() -> None:
    result = _page(total=30, page=3, page_size=10)

    assert result.has_next is False
    assert result.has_previous is True


def test_a_single_page_has_neither() -> None:
    result = _page(total=4, page=1, page_size=10)

    assert result.has_next is False
    assert result.has_previous is False


def test_total_pages_rounds_up() -> None:
    assert _page(total=31, page=1, page_size=10).total_pages == 4
    assert _page(total=30, page=1, page_size=10).total_pages == 3
    assert _page(total=0, page=1, page_size=10).total_pages == 0


def test_an_empty_result_is_a_valid_page() -> None:
    result = Page.of((), total=0, request=PageRequest())

    assert result.items == ()
    assert result.total == 0
    assert result.has_next is False


def test_the_total_is_the_result_set_not_the_page() -> None:
    """A client cannot tell whether it has seen everything without
    this."""

    result = Page.of(
        (1, 2, 3), total=57, request=PageRequest(page=1, page_size=3)
    )

    assert len(result.items) == 3
    assert result.total == 57


def test_there_are_exactly_two_sort_directions() -> None:
    assert {member.value for member in SortDirection} == {"asc", "desc"}
