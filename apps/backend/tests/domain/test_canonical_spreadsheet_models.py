"""
Tests for the canonical workbook value objects and their factory
(ADR-0034).

Pure domain tests: no file, no library, no database. They specify the
invariants that decide whether a stored representation can be trusted,
because a malformed one reaching storage is believed by every consumer
below it - and the fault then surfaces as an inexplicable extraction
rather than as the reader defect it actually is.

The recurring theme is that the factory **checks and refuses**; it never
repairs. Sorting a grid, closing a gap or picking one of two values would
each produce a representation that looks correct while proving nothing
about what was read.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.canonical_spreadsheet import canonical_spreadsheet_factory
from app.domain.canonical_spreadsheet.canonical_spreadsheet_exceptions import (
    InvalidCanonicalWorkbookError,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalCellType,
    CanonicalRow,
    CanonicalWorkbook,
    CanonicalWorksheet,
    CellReference,
    CellValue,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
    column_label_of,
)


def _text(text: str) -> CellValue:
    return canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.TEXT, text=text
    )


def _cell(row: int, column: int, text: str = "x") -> CanonicalCell:
    return canonical_spreadsheet_factory.build_cell(
        row_number=row, column_number=column, literal=_text(text)
    )


def _row(row_number: int, *columns: int) -> CanonicalRow:
    return canonical_spreadsheet_factory.build_row(
        row_number=row_number,
        cells=tuple(_cell(row_number, column) for column in columns),
    )


def _used_range(rows: tuple[CanonicalRow, ...]) -> UsedRange | None:
    if not rows:
        return None

    columns = tuple(cell.column_number for row in rows for cell in row.cells)

    return canonical_spreadsheet_factory.build_used_range(
        first_row=rows[0].row_number,
        last_row=rows[-1].row_number,
        first_column=min(columns),
        last_column=max(columns),
    )


def _worksheet(
    index: int = 0, *rows: CanonicalRow, name: str = "Register"
) -> CanonicalWorksheet:
    return canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=index,
        name=name,
        visibility=WorksheetVisibility.VISIBLE,
        rows=rows,
        used_range=_used_range(rows),
    )


def _workbook(*worksheets: CanonicalWorksheet) -> CanonicalWorkbook:
    return canonical_spreadsheet_factory.build_workbook(
        document_id=7,
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        representation_version="1.0",
        reader_name="openpyxl",
        reader_version="3.1.5",
        date_system=WorkbookDateSystem.EPOCH_1900,
        has_vba_project=False,
        has_external_links=False,
        worksheets=worksheets,
    )


# --- A cell states one thing ---------------------------------------------


def test_a_cell_carrying_a_literal_records_it() -> None:
    cell = _cell(2, 1, "CBL-001")

    assert cell.literal.text == "CBL-001"
    assert cell.formula is None


def test_a_cell_carrying_a_formula_records_it() -> None:
    cell = canonical_spreadsheet_factory.build_cell(
        row_number=2,
        column_number=3,
        formula=canonical_spreadsheet_factory.build_formula(
            expression="=A2*B2"
        ),
    )

    assert cell.formula.expression == "=A2*B2"
    assert cell.literal is None


def test_a_cell_carrying_both_a_literal_and_a_formula_is_refused() -> None:
    """Both populated would let every consumer pick whichever suited it,
    and the choice between what an engineer typed and what an application
    computed would then vary by consumer."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell(
            row_number=2,
            column_number=1,
            literal=_text("4"),
            formula=canonical_spreadsheet_factory.build_formula(
                expression="=A1"
            ),
        )


def test_a_cell_carrying_neither_is_refused() -> None:
    """An unobserved cell is not materialised: a workbook declares a grid
    of a billion cells and nothing is not an observation."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell(
            row_number=2, column_number=1
        )


def test_a_cell_offers_no_value_that_hides_where_it_came_from() -> None:
    """A ``value`` returning literal-or-cached would let every consumer
    forget, silently and by default, whether it was reading what the
    engineer typed or what some other application computed."""

    cell = _cell(1, 1, "630")

    assert not hasattr(cell, "value")
    assert "value" not in CanonicalCell.__slots__


def test_a_formula_must_state_the_expression_the_file_carries() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_formula(expression="   ")


def test_a_formula_without_a_cached_result_says_so() -> None:
    formula = canonical_spreadsheet_factory.build_formula(
        expression="=A2*B2"
    )

    assert formula.cached_result is None
    assert formula.has_cached_result is False


def test_a_formula_keeps_its_cached_result_apart_from_the_expression(
) -> None:
    formula = canonical_spreadsheet_factory.build_formula(
        expression="=A2*B2",
        cached_result=canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.NUMBER,
            text="10",
            number=Decimal("10"),
        ),
    )

    assert formula.has_cached_result is True
    assert formula.cached_result.number == Decimal("10")


# --- A value's declared kind and its filled slot agree --------------------


def test_a_number_fills_the_number_slot_and_no_other() -> None:
    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.NUMBER,
        text="630",
        number=Decimal("630"),
    )

    assert value.number == Decimal("630")
    assert (value.boolean, value.instant, value.duration) == (
        None,
        None,
        None,
    )


def test_a_boolean_fills_the_boolean_slot() -> None:
    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.BOOLEAN, text="TRUE", boolean=True
    )

    assert value.boolean is True


def test_a_date_time_fills_the_instant_slot() -> None:
    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.DATE_TIME,
        text="2026-03-14T09:30:00",
        instant="2026-03-14T09:30:00",
    )

    assert value.instant == "2026-03-14T09:30:00"


def test_a_time_fills_the_instant_slot_as_well() -> None:
    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.TIME,
        text="09:30:00",
        instant="09:30:00",
    )

    assert value.instant == "09:30:00"


def test_a_duration_fills_the_duration_slot() -> None:
    """An elapsed time is not an instant the workbook named, so it is
    recorded in its own slot."""

    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.DURATION,
        text="PT2H30M0S",
        duration="PT2H30M0S",
    )

    assert value.duration == "PT2H30M0S"
    assert value.instant is None


def test_an_error_the_file_carries_fills_the_error_slot() -> None:
    """``#DIV/0!`` is a value the workbook genuinely holds, not a failure
    to read the cell; dropping it would make a broken register look
    complete."""

    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.ERROR,
        text="#DIV/0!",
        error_code="#DIV/0!",
    )

    assert value.error_code == "#DIV/0!"


def test_text_fills_no_typed_slot() -> None:
    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.TEXT, text="PANEL-A"
    )

    assert (
        value.number,
        value.boolean,
        value.instant,
        value.duration,
        value.error_code,
    ) == (None, None, None, None, None)


def test_a_value_declaring_one_kind_and_filling_another_is_refused(
) -> None:
    """A value declaring itself a number while carrying a date would be
    believed by every consumer that switches on ``value_type``."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.NUMBER,
            text="2026-03-14",
            instant="2026-03-14T00:00:00",
        )


def test_a_typed_value_with_no_slot_filled_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.NUMBER, text="630"
        )


def test_text_carrying_a_typed_slot_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.TEXT,
            text="630",
            number=Decimal("630"),
        )


def test_a_value_filling_two_slots_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.NUMBER,
            text="630",
            number=Decimal("630"),
            boolean=True,
        )


def test_there_is_no_cell_type_meaning_nothing_is_here() -> None:
    """A blank cell is not materialised, so a type meaning "nothing
    here" would be unreachable - and would give a future writer somewhere
    to record a cell it could not read."""

    assert {member.value for member in CanonicalCellType} == {
        "text",
        "number",
        "boolean",
        "date_time",
        "time",
        "duration",
        "error",
    }


# --- Coordinates are the workbook's own -----------------------------------


def test_a_column_label_is_bijective_base_26() -> None:
    """Ordinary base-26 would produce ``@A`` for column 27, and a locator
    an engineer cannot paste back into the source file is not a
    locator."""

    labels = {
        number: column_label_of(number)
        for number in (1, 2, 26, 27, 28, 52, 702, 703)
    }

    assert labels == {
        1: "A",
        2: "B",
        26: "Z",
        27: "AA",
        28: "AB",
        52: "AZ",
        702: "ZZ",
        703: "AAA",
    }


def test_a_cell_addresses_itself_as_the_workbook_writes_it() -> None:
    cell = _cell(12, 28)

    assert cell.column_label == "AB"
    assert cell.a1_reference == "AB12"


def test_a_cell_reference_addresses_itself_the_same_way() -> None:
    reference = CellReference(
        worksheet_index=1,
        worksheet_name="Equipment",
        row_number=2,
        column_number=2,
    )

    assert reference.a1_reference == "B2"


def test_a_row_number_below_one_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell(
            row_number=0, column_number=1, literal=_text("x")
        )


def test_a_column_number_below_one_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell(
            row_number=1, column_number=0, literal=_text("x")
        )


# --- Ordering is required, never imposed ----------------------------------


def test_a_row_keeps_its_columns_in_ascending_order() -> None:
    row = _row(3, 1, 3, 5)

    assert tuple(cell.column_number for cell in row.cells) == (1, 3, 5)


def test_columns_out_of_order_are_refused_rather_than_sorted() -> None:
    """Sorting here would hide a reader that emitted a grid out of order,
    and the representation would look correct while proving nothing about
    what was read."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_row(
            row_number=3, cells=(_cell(3, 5), _cell(3, 1))
        )


def test_a_repeated_column_is_refused() -> None:
    """A repeated coordinate would mean one cell overwrote another in the
    record."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_row(
            row_number=3, cells=(_cell(3, 2), _cell(3, 2))
        )


def test_a_cell_belonging_to_another_row_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_row(
            row_number=3, cells=(_cell(4, 1),)
        )


def test_a_row_materialising_no_cell_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_row(row_number=3, cells=())


def test_rows_out_of_order_are_refused() -> None:
    rows = (_row(4, 1), _row(2, 1))

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_worksheet(
            worksheet_index=0,
            name="Sparse",
            visibility=WorksheetVisibility.VISIBLE,
            rows=rows,
            used_range=_used_range(rows),
        )


def test_worksheet_positions_must_be_contiguous_from_zero() -> None:
    """A representation missing worksheet 1 would be indistinguishable
    from a workbook that never had one, and every position below it would
    be wrong from there on."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        _workbook(_worksheet(0, _row(1, 1)), _worksheet(2, _row(1, 1)))


def test_worksheets_out_of_order_are_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        _workbook(_worksheet(1, _row(1, 1)), _worksheet(0, _row(1, 1)))


def test_a_negative_worksheet_position_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_worksheet(
            worksheet_index=-1,
            name="Register",
            visibility=WorksheetVisibility.VISIBLE,
        )


# --- The used range is derived from the cells, and checked ----------------


def test_the_used_range_is_the_extent_of_the_cells_present() -> None:
    worksheet = _worksheet(0, _row(1, 1, 3), _row(4, 2))

    assert worksheet.used_range.first_row == 1
    assert worksheet.used_range.last_row == 4
    assert worksheet.used_range.first_column == 1
    assert worksheet.used_range.last_column == 3


def test_a_used_range_disagreeing_with_the_cells_is_refused() -> None:
    """The range is checked against the content rather than trusted,
    because the whole reason it is derived is that a workbook's declared
    extent is routinely absent or wrong."""

    rows = (_row(1, 1),)

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_worksheet(
            worksheet_index=0,
            name="Register",
            visibility=WorksheetVisibility.VISIBLE,
            rows=rows,
            used_range=canonical_spreadsheet_factory.build_used_range(
                first_row=1, last_row=9, first_column=1, last_column=9
            ),
        )


def test_a_worksheet_with_cells_and_no_used_range_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_worksheet(
            worksheet_index=0,
            name="Register",
            visibility=WorksheetVisibility.VISIBLE,
            rows=(_row(1, 1),),
            used_range=None,
        )


def test_an_empty_worksheet_claims_no_extent() -> None:
    worksheet = _worksheet(0)

    assert worksheet.used_range is None
    assert worksheet.is_empty is True


def test_a_used_range_with_a_reversed_bound_is_refused() -> None:
    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_used_range(
            first_row=9, last_row=1, first_column=1, last_column=1
        )


# --- Lookups are lookups, never searches ---------------------------------


def test_a_row_is_found_by_the_workbooks_own_number() -> None:
    worksheet = _worksheet(0, _row(1, 1), _row(3, 1), _row(4, 1))

    assert worksheet.row(3).row_number == 3


def test_a_gap_between_rows_survives_as_a_gap() -> None:
    """Rows are sparse by design, so indexing into the tuple would
    silently return a neighbouring row."""

    worksheet = _worksheet(0, _row(1, 1), _row(3, 1), _row(4, 1))

    assert worksheet.row(2) is None
    assert tuple(row.row_number for row in worksheet.rows) == (1, 3, 4)


def test_a_worksheet_is_found_by_its_position() -> None:
    workbook = _workbook(
        _worksheet(0, _row(1, 1), name="Cables"),
        _worksheet(1, _row(1, 1), name="Equipment"),
    )

    assert workbook.worksheet(1).name == "Equipment"
    assert workbook.worksheet(9) is None
    assert workbook.worksheet_count == 2


# --- The representation states its own provenance -------------------------


def test_a_representation_without_a_checksum_is_refused() -> None:
    """Without it nothing ties the representation to a document
    version."""

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_workbook(
            document_id=7,
            content_checksum="   ",
            checksum_algorithm="sha256",
            representation_version="1.0",
            reader_name="openpyxl",
            reader_version="3.1.5",
            date_system=WorkbookDateSystem.EPOCH_1900,
            has_vba_project=False,
            has_external_links=False,
        )


def test_a_workbook_with_no_worksheet_says_so() -> None:
    workbook = _workbook()

    assert workbook.is_empty is True
    assert workbook.has_populated_cell is False


def test_a_workbook_whose_worksheets_are_all_empty_populates_nothing(
) -> None:
    """``False`` says nothing was observed anywhere - not that the file
    is a template or a macro container, which are conclusions this
    context reads nothing to support."""

    workbook = _workbook(_worksheet(0), _worksheet(1, name="Second"))

    assert workbook.is_empty is False
    assert workbook.has_populated_cell is False


def test_two_representations_of_the_same_bytes_compare_equal() -> None:
    """There is deliberately no timestamp: the value is a function of the
    bytes and the reader, so determinism is provable by equality."""

    first = _workbook(_worksheet(0, _row(1, 1, 2)))
    second = _workbook(_worksheet(0, _row(1, 1, 2)))

    assert first == second


def test_a_representation_cannot_be_edited_after_the_fact() -> None:
    workbook = _workbook(_worksheet(0, _row(1, 1)))

    with pytest.raises(Exception):
        workbook.content_checksum = "b" * 64


# --- Numbers that are not numbers -----------------------------------------


@pytest.mark.parametrize(
    "magnitude",
    [
        "Infinity",
        "-Infinity",
        "NaN",
        "-NaN",
        "sNaN",
        # Finite, and still unrecordable. A payload with no decimal
        # point is a Python integer, which has no width at all.
        "1E+15",
        "-1E+15",
        "1E+300",
        "9" * 400,
    ],
)
def test_a_number_cell_refuses_a_magnitude_it_cannot_record(
    magnitude: str
) -> None:
    """
    A magnitude this representation cannot record.

    Two different faults share one refusal. An infinity or a NaN is not
    a value a register can state at all. A finite magnitude past the
    bound is a value the column cannot hold: far enough past it, the
    stored number becomes an infinity and the row can never be read
    again - a canonical artefact that is written and unreadable, which
    is the one thing a representation must never be.

    The bound is a conservative digit-count proxy for that: some values
    just past it would in fact survive a round trip, and are refused
    anyway rather than being admitted by a rule nobody could state.
    """

    with pytest.raises(InvalidCanonicalWorkbookError):
        canonical_spreadsheet_factory.build_cell_value(
            value_type=CanonicalCellType.NUMBER,
            text=magnitude,
            number=Decimal(magnitude),
        )


@pytest.mark.parametrize(
    "magnitude",
    [
        "0",
        "-0",
        "630",
        "2.5",
        "0.000000000001",
        "1E+12",
        "-1E+12",
        # The exact edge: fifteen integer digits, the most the store
        # returns unchanged.
        "9" * 15,
        "-" + "9" * 15,
    ],
)
def test_a_number_cell_accepts_a_recordable_magnitude(
    magnitude: str
) -> None:
    """
    The control for the rule above.

    The bound is on magnitude, and it is deliberately generous: fifteen
    integer digits is a thousand million million, past anything a
    register carries. It is **not** a bound on decimal places - see
    ``test_a_number_needing_more_scale_than_the_column_is_still_read``
    for what happens to those.
    """

    value = canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType.NUMBER,
        text=magnitude,
        number=Decimal(magnitude),
    )

    assert value.number == Decimal(magnitude)
