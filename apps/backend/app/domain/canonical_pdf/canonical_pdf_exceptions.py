"""Typed errors for the canonical PDF context (Milestone 26.1)."""

from __future__ import annotations


class CanonicalPdfError(Exception):
    """Base error for everything this bounded context raises."""


class InvalidCanonicalRepresentationError(CanonicalPdfError):
    """
    A representation was constructed that violates an invariant of the
    model - non-contiguous page numbers, a reversed bounding box, a
    reading order with a hole in it.

    Raised at construction, never later. A malformed representation that
    reached storage would be trusted by every future extractor, and the
    fault would surface as inexplicable extraction results rather than as
    the parser bug it actually is.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
