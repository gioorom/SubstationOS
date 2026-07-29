"""
The one pagination contract in SubstationOS.

Page-based rather than offset-based: every list this API serves is read
by a human paging through a registry, and ``page``/``page_size`` is the
vocabulary that conversation actually uses. One convention, used
everywhere, so a caller never has to remember which endpoint speaks
which dialect.

A ``PageRequest`` is validated at construction (CLAUDE.md §15, fail fast,
fail typed): an out-of-range page size cannot exist as an object, so no
repository has to defend against one. The maximum is a hard ceiling, not
a suggestion - an unbounded list read is a denial-of-service against a
registry with a hundred thousand documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from app.domain.shared_kernel.pagination_exceptions import (
    InvalidPageError,
    InvalidPageSizeError,
)

#: The page size used when a caller expresses no preference. Chosen to
#: fill one screen of a registry table without a second request.
DEFAULT_PAGE_SIZE = 25

#: The hard ceiling. A caller asking for more is refused, never quietly
#: served a smaller page - silently ignoring the request would make the
#: client believe it had read the whole registry.
MAX_PAGE_SIZE = 100

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class PageRequest:
    """One request for a slice of a list. Pages are 1-based."""

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise InvalidPageError(self.page)

        if self.page_size < 1 or self.page_size > MAX_PAGE_SIZE:
            raise InvalidPageSizeError(self.page_size, MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        """The number of rows to skip. The only place the page-based
        contract is translated into the offset a query needs."""

        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


@dataclass(frozen=True, slots=True)
class Page(Generic[ItemT]):
    """
    One slice of a list, with everything a caller needs to page through
    the rest of it.

    ``total`` is the number of items matching the query, **not** the
    number returned - a client cannot tell whether it has seen
    everything without it. It is counted by the query layer, never by
    measuring a list that was loaded into memory first.
    """

    items: tuple[ItemT, ...]
    total: int
    page: int
    page_size: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0

        return -(-self.total // self.page_size)

    @classmethod
    def of(
        cls,
        items: tuple[ItemT, ...],
        *,
        total: int,
        request: PageRequest,
    ) -> "Page[ItemT]":
        return cls(
            items=items,
            total=total,
            page=request.page,
            page_size=request.page_size,
        )


class SortDirection(str, Enum):
    """Ascending or descending. There is no third option, and no
    free-text direction string reaches a query."""

    ASCENDING = "asc"
    DESCENDING = "desc"
