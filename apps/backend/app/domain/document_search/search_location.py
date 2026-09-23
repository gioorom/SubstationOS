"""
Where a hit is, expressed the way the source expresses it.

A PDF says *page*. A workbook says *sheet* and *cell*. This module
turns the recorded coordinates into the reference an engineer would use
to find the same place by hand - ``B12`` on sheet ``Cavi``, page ``3``.

**A location is never invented.** If the coordinates that would make a
reference are absent, ``describe`` returns a descriptor that is not
``determined`` and carries nothing else. A wrong page number in this
domain sends somebody to the wrong drawing, which is worse than an
admission that the position is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.document_search.search_models import (
    SegmentKind,
    SegmentLocation,
)

_ALPHABET_SIZE = 26
_LETTER_A = ord("A")


@dataclass(frozen=True, slots=True)
class LocationDescriptor:
    """
    The coordinates of a hit, resolved for display.

    ``determined`` is the field a caller must read first. When it is
    false every other field is empty, and that is a fact about the
    source rather than a failure to look.
    """

    determined: bool
    page_number: int | None = None
    worksheet_name: str | None = None
    row_number: int | None = None
    cell_reference: str | None = None


def column_letter(column_number: int) -> str | None:
    """
    The spreadsheet letter for a one-based column: 1 -> ``A``,
    27 -> ``AA``. ``None`` below 1, because there is no column zero to
    name.
    """

    if column_number < 1:
        return None

    letters = ""
    remaining = column_number

    while remaining > 0:
        remaining, position = divmod(remaining - 1, _ALPHABET_SIZE)
        letters = chr(_LETTER_A + position) + letters

    return letters


def cell_reference(
    row_number: int | None, column_number: int | None
) -> str | None:
    """
    ``B12`` from row 12 and column 2, or ``None`` if either coordinate
    is missing. Half a reference is not a reference.
    """

    if row_number is None or column_number is None or row_number < 1:
        return None

    letters = column_letter(column_number)

    return None if letters is None else f"{letters}{row_number}"


def column_at_offset(
    cell_offsets: tuple[tuple[int, int], ...], offset: int
) -> int | None:
    """
    The column whose cell contains ``offset`` in a row's text.

    The last cell that starts at or before the offset owns it, since
    the cells were laid out in column order. ``None`` when the
    boundaries are unknown or the offset precedes the first cell -
    there is no column to name, and naming one anyway would point an
    engineer at a cell they did not match.
    """

    owner: int | None = None

    for column_number, start in cell_offsets:
        if start > offset:
            break
        owner = column_number

    return owner


def describe(
    kind: SegmentKind,
    location: SegmentLocation,
    *,
    match_offset: int | None = None,
) -> LocationDescriptor:
    """
    ``location`` resolved into what to show for a hit of this ``kind``.

    Each kind is asked only for the coordinates it can have: a page for
    a line of a PDF, a sheet and a cell for a workbook. A segment
    missing them is reported undetermined rather than described with
    the fields of the other kind.

    ``match_offset`` is where the match starts in a spreadsheet row's
    text. Given it, the descriptor names the exact cell; without it, or
    when the row's cell boundaries were not recorded, it names the row
    and stops there. It never narrows to a cell it cannot justify.
    """

    if kind is SegmentKind.PDF_LINE:
        if location.page_number is None:
            return LocationDescriptor(determined=False)

        return LocationDescriptor(
            determined=True, page_number=location.page_number
        )

    if kind is SegmentKind.SPREADSHEET_ROW:
        return _describe_row(location, match_offset)

    return LocationDescriptor(determined=False)


def _describe_row(
    location: SegmentLocation, match_offset: int | None
) -> LocationDescriptor:
    """A spreadsheet row, narrowed to a cell when the match allows."""

    column_number = location.column_number

    if column_number is None and match_offset is not None:
        column_number = column_at_offset(
            location.cell_offsets, match_offset
        )

    reference = cell_reference(location.row_number, column_number)

    if reference is None and location.worksheet_name is None:
        return LocationDescriptor(determined=False)

    return LocationDescriptor(
        determined=True,
        worksheet_name=location.worksheet_name,
        row_number=location.row_number,
        cell_reference=reference,
    )
