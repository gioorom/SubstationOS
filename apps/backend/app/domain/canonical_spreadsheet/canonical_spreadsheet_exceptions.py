"""Typed errors for the canonical spreadsheet context (ADR-0034)."""

from __future__ import annotations


class CanonicalSpreadsheetError(Exception):
    """Base error for everything this bounded context raises."""


class InvalidCanonicalWorkbookError(CanonicalSpreadsheetError):
    """
    A representation was constructed that violates an invariant of the
    model - a cell carrying both a literal and a formula, a row number
    below one, coordinates out of ascending order, a value whose typed
    slot does not match its declared kind, a used range that does not
    match the cells present, or a read result that is neither a workbook
    nor a stated reason for there being none.

    Raised at construction, never later. A malformed representation that
    reached storage would be trusted by every future consumer, and the
    fault would surface as inexplicable extraction results rather than
    as the reader bug it actually is.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
