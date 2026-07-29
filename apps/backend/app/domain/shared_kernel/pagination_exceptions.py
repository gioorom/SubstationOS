"""Typed failures for an invalid page request. Separate module so
``pagination`` itself imports nothing from the rest of the domain."""

from __future__ import annotations


class PaginationError(Exception):
    """Base class for every pagination failure."""


class InvalidPageError(PaginationError):
    """A page number below 1. Pages are 1-based."""

    def __init__(self, page: int) -> None:
        self.page = page

        super().__init__(f"Page must be 1 or greater; received {page}.")


class InvalidPageSizeError(PaginationError):
    """
    A page size outside the permitted range.

    Refused rather than clamped: a caller who asked for 10 000 and
    silently received 100 would believe it had read the whole registry.
    """

    def __init__(self, page_size: int, maximum: int) -> None:
        self.page_size = page_size
        self.maximum = maximum

        super().__init__(
            f"Page size must be between 1 and {maximum}; "
            f"received {page_size}."
        )
