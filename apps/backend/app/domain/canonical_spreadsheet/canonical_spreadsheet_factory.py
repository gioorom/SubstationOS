"""
Construction of canonical workbook value objects, with the invariants
enforced at the moment of construction (ADR-0034).

The reader adapter calls this factory rather than instantiating the value
objects directly, so there is exactly one place a malformed
representation can be caught - and it is *before* the representation
exists, not after it reached storage and started being trusted.

The factory takes explicit, typed arguments. It never accepts a
dictionary: a library's raw output shape is the adapter's problem, and
letting it through to here would make the domain depend on that
library's layout.

**It adds nothing.** No sorting, no merging, no de-duplication, no
whitespace repair, no header guessing, no formula evaluation. It checks
that what it was given is internally coherent and refuses it otherwise -
that is the whole job.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.canonical_spreadsheet.canonical_spreadsheet_exceptions import (
    InvalidCanonicalWorkbookError,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalCellFormula,
    CanonicalCellType,
    CanonicalRow,
    CanonicalWorkbook,
    CanonicalWorksheet,
    CellValue,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (
    MAX_NUMERIC_INTEGER_DIGITS,
)

#: Which typed slot each kind of value must fill, and by omission which
#: slots it must leave empty. A table rather than a chain of conditions:
#: adding a kind of value means adding one entry here, and a kind with no
#: entry cannot be built at all - which is what stops a new member of the
#: enum from quietly accepting anything.
_TYPED_SLOT: dict[CanonicalCellType, str | None] = {
    CanonicalCellType.TEXT: None,
    CanonicalCellType.NUMBER: "number",
    CanonicalCellType.BOOLEAN: "boolean",
    CanonicalCellType.DATE_TIME: "instant",
    CanonicalCellType.TIME: "instant",
    CanonicalCellType.DURATION: "duration",
    CanonicalCellType.ERROR: "error_code",
}

_TYPED_SLOTS: tuple[str, ...] = (
    "number",
    "boolean",
    "instant",
    "duration",
    "error_code",
)


def build_cell_value(
    *,
    value_type: CanonicalCellType,
    text: str,
    number: Decimal | None = None,
    boolean: bool | None = None,
    instant: str | None = None,
    duration: str | None = None,
    error_code: str | None = None,
) -> CellValue:
    """
    One value whose declared kind and filled slot agree.

    A value declaring itself a number while carrying a date, or a date
    carrying nothing at all, would be believed by every consumer that
    switches on ``value_type`` - and would be found, if ever, as an
    inexplicable extraction rather than as the reader fault it is.
    """

    if value_type not in _TYPED_SLOT:
        raise InvalidCanonicalWorkbookError(
            f"Cell value kind {value_type!r} declares no typed slot."
        )

    supplied = {
        "number": number,
        "boolean": boolean,
        "instant": instant,
        "duration": duration,
        "error_code": error_code,
    }
    expected = _TYPED_SLOT[value_type]
    filled = tuple(
        name for name in _TYPED_SLOTS if supplied[name] is not None
    )

    if expected is None and filled:
        raise InvalidCanonicalWorkbookError(
            f"Value kind '{value_type.value}' carries no typed "
            f"slot, but {filled} was supplied."
        )

    if expected is not None and filled != (expected,):
        raise InvalidCanonicalWorkbookError(
            f"Value kind '{value_type.value}' must fill exactly "
            f"('{expected}',); {filled} was supplied."
        )

    if number is not None and not number.is_finite():
        # An infinity or a NaN is not a number a register can state, and
        # it is not storable either: it survives the write and then
        # raises on the way back, leaving a representation that can be
        # persisted and never read - the one thing a canonical artefact
        # must never be.
        #
        # Refused here rather than at any single producer because this
        # factory is also the way a stored row is rebuilt, so the same
        # rule protects the read path without a second copy of it.
        raise InvalidCanonicalWorkbookError(
            f"Value kind '{value_type.value}' carries {number!r}, "
            "which is not a finite number."
        )

    if number is not None and number.adjusted() >= MAX_NUMERIC_INTEGER_DIGITS:
        # Finite, and still not storable. A magnitude past the column's
        # width becomes an infinity on the way in and raises on the way
        # out, which is the same broken invariant as a non-finite value
        # reached by a different route.
        raise InvalidCanonicalWorkbookError(
            f"Value kind '{value_type.value}' carries a magnitude of "
            f"{number.adjusted() + 1} digits, beyond the "
            f"{MAX_NUMERIC_INTEGER_DIGITS} a recorded number may hold."
        )

    return CellValue(
        value_type=value_type,
        text=text,
        number=number,
        boolean=boolean,
        instant=instant,
        duration=duration,
        error_code=error_code,
    )


def build_formula(
    *, expression: str, cached_result: CellValue | None = None
) -> CanonicalCellFormula:
    """
    A formula must state its expression. A blank expression would record
    "this cell computes something, and the file did not say what" as if
    it were a formula, and no consumer could tell it from one.
    """

    if not expression.strip():
        raise InvalidCanonicalWorkbookError(
            "A formula must carry the expression the file states."
        )

    return CanonicalCellFormula(
        expression=expression, cached_result=cached_result
    )


def build_cell(
    *,
    row_number: int,
    column_number: int,
    number_format: str | None = None,
    literal: CellValue | None = None,
    formula: CanonicalCellFormula | None = None,
) -> CanonicalCell:
    """
    A cell carries **either** a literal **or** a formula, never both and
    never neither.

    Both would leave every consumer free to pick whichever suited it, and
    the choice between what an engineer typed and what an application
    computed would then vary by consumer. Neither would be a cell that
    was materialised despite nothing having been observed in it, which is
    precisely what "absence is the record" forbids.
    """

    _require_positive(row_number, "Row number")
    _require_positive(column_number, "Column number")

    if literal is not None and formula is not None:
        raise InvalidCanonicalWorkbookError(
            f"Cell (row {row_number}, column {column_number}) carries "
            "both a literal and a formula."
        )

    if literal is None and formula is None:
        raise InvalidCanonicalWorkbookError(
            f"Cell (row {row_number}, column {column_number}) carries "
            "neither a literal nor a formula; an unobserved cell is not "
            "materialised."
        )

    return CanonicalCell(
        row_number=row_number,
        column_number=column_number,
        number_format=number_format,
        literal=literal,
        formula=formula,
    )


def build_row(
    *, row_number: int, cells: tuple[CanonicalCell, ...]
) -> CanonicalRow:
    """
    A row of cells, all of them its own, in strictly ascending column
    order.

    Ascending order is required rather than imposed: sorting here would
    hide a reader that emitted a grid out of order, and the resulting
    representation would look correct while proving nothing about what
    was actually read.
    """

    _require_positive(row_number, "Row number")

    if not cells:
        raise InvalidCanonicalWorkbookError(
            f"Row {row_number} materialises no cell; an empty row is "
            "not recorded."
        )

    for cell in cells:
        if cell.row_number != row_number:
            raise InvalidCanonicalWorkbookError(
                f"Cell {cell.a1_reference} was given to row "
                f"{row_number}."
            )

    _require_strictly_ascending(
        tuple(cell.column_number for cell in cells),
        f"Columns in row {row_number}",
    )

    return CanonicalRow(row_number=row_number, cells=cells)


def build_used_range(
    *, first_row: int, last_row: int, first_column: int, last_column: int
) -> UsedRange:
    _require_positive(first_row, "First row")
    _require_positive(first_column, "First column")

    if last_row < first_row or last_column < first_column:
        raise InvalidCanonicalWorkbookError(
            f"Used range (rows {first_row}-{last_row}, columns "
            f"{first_column}-{last_column}) has a bound reversed."
        )

    return UsedRange(
        first_row=first_row,
        last_row=last_row,
        first_column=first_column,
        last_column=last_column,
    )


def build_worksheet(
    *,
    worksheet_index: int,
    name: str,
    visibility: WorksheetVisibility,
    rows: tuple[CanonicalRow, ...] = (),
    used_range: UsedRange | None = None,
) -> CanonicalWorksheet:
    """
    A worksheet whose used range is exactly the extent of the cells it
    actually carries, or ``None`` when it carries none.

    The range is checked against the content rather than trusted,
    because the whole reason this model derives it is that a workbook's
    own declared extent is routinely absent or wrong. A derived value
    that could itself drift would be no better than the declared one.
    """

    if worksheet_index < 0:
        raise InvalidCanonicalWorkbookError(
            f"Worksheet index {worksheet_index} is not 0-based."
        )

    _require_strictly_ascending(
        tuple(row.row_number for row in rows),
        f"Rows in worksheet {worksheet_index}",
    )

    observed = _observed_extent(rows)

    if observed != used_range:
        raise InvalidCanonicalWorkbookError(
            f"Worksheet {worksheet_index} declares used range "
            f"{used_range}; its cells occupy {observed}."
        )

    return CanonicalWorksheet(
        worksheet_index=worksheet_index,
        name=name,
        visibility=visibility,
        rows=rows,
        used_range=used_range,
    )


def build_workbook(
    *,
    document_id: int,
    content_checksum: str,
    checksum_algorithm: str,
    representation_version: str,
    reader_name: str,
    reader_version: str,
    date_system: WorkbookDateSystem,
    has_vba_project: bool,
    has_external_links: bool,
    worksheets: tuple[CanonicalWorksheet, ...] = (),
) -> CanonicalWorkbook:
    """
    Worksheets must be 0..n, in order, with no gaps. A representation
    missing worksheet 2 would be indistinguishable from a workbook that
    never had one, and every position recorded below it would be wrong
    from there on.
    """

    expected = tuple(range(len(worksheets)))
    actual = tuple(sheet.worksheet_index for sheet in worksheets)

    if actual != expected:
        raise InvalidCanonicalWorkbookError(
            f"Worksheet positions are {actual}; expected a contiguous "
            f"0-based sequence {expected}."
        )

    if not content_checksum.strip():
        raise InvalidCanonicalWorkbookError(
            "A representation must record the checksum of the bytes it "
            "was built from; without it, nothing ties it to a document "
            "version."
        )

    return CanonicalWorkbook(
        document_id=document_id,
        content_checksum=content_checksum,
        checksum_algorithm=checksum_algorithm,
        representation_version=representation_version,
        reader_name=reader_name,
        reader_version=reader_version,
        date_system=date_system,
        has_vba_project=has_vba_project,
        has_external_links=has_external_links,
        worksheets=worksheets,
    )


def _observed_extent(rows: tuple[CanonicalRow, ...]) -> UsedRange | None:
    if not rows:
        return None

    columns = tuple(
        cell.column_number for row in rows for cell in row.cells
    )

    return UsedRange(
        first_row=rows[0].row_number,
        last_row=rows[-1].row_number,
        first_column=min(columns),
        last_column=max(columns),
    )


def _require_positive(number: int, what: str) -> None:
    if number < 1:
        raise InvalidCanonicalWorkbookError(
            f"{what} {number} is not 1-based."
        )


def _require_strictly_ascending(
    numbers: tuple[int, ...], what: str
) -> None:
    """The reader's own traversal, preserved without repetition or
    reversal. A repeated coordinate would mean one cell overwrote
    another in the record; a reversal would mean the grid was read in an
    order the file does not have."""

    if any(
        later <= earlier
        for earlier, later in zip(numbers, numbers[1:])
    ):
        raise InvalidCanonicalWorkbookError(
            f"{what} are {numbers}; expected strictly ascending."
        )
