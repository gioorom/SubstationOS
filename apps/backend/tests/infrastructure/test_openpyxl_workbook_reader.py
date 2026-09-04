"""
Tests for the openpyxl adapter behind ``WorkbookReaderPort`` (ADR-0034),
against real workbooks built in memory.

These are the tests that decide whether the canonical workbook can be
trusted: every stage below reads what this adapter produced, so "the same
bytes always yield the same representation" is the contract rather than a
nicety.

They are also where the milestone's refusals are proven. A reader that
guessed a header row, closed a gap, evaluated a formula or repaired a
value would still pass a naive round-trip test and would quietly put an
inference into a record that claims to hold observations.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
    WorkbookCanonicalizationFailureCode,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCellType,
    CanonicalWorksheet,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (
    CANONICAL_WORKBOOK_VERSION,
    MAX_WORKSHEETS,
)
from app.domain.canonical_spreadsheet.workbook_reader_port import (
    WorkbookReadResult,
)
from app.infrastructure.canonical_spreadsheet.openpyxl_workbook_reader import (
    OpenpyxlWorkbookReader,
)
from tests.fixtures import synthetic_workbooks

CHECKSUM = "b" * 64


def _read(content: bytes, *, document_id: int = 7) -> WorkbookReadResult:
    return OpenpyxlWorkbookReader().read(
        content,
        document_id=document_id,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )


def _texts(worksheet: CanonicalWorksheet) -> dict[str, str]:
    """Every materialised cell of a worksheet, by its A1 address."""

    return {
        cell.a1_reference: cell.literal.text
        for row in worksheet.rows
        for cell in row.cells
        if cell.literal is not None
    }


# --- Fixture A: a plain register ------------------------------------------


def test_a_simple_register_reads_into_one_worksheet() -> None:
    result = _read(synthetic_workbooks.simple_register())
    workbook = result.workbook

    assert result.was_read
    assert workbook.worksheet_count == 1
    assert workbook.worksheets[0].name == "Register"


def test_a_simple_register_records_every_populated_cell() -> None:
    worksheet = _read(
        synthetic_workbooks.simple_register()
    ).workbook.worksheets[0]

    assert tuple(row.row_number for row in worksheet.rows) == (1, 2, 3, 4)
    assert len(_texts(worksheet)) == 16


def test_the_first_row_is_recorded_as_ordinary_cells() -> None:
    """It *looks* like a header. Nothing in this milestone treats it as
    one, and there is nowhere in the model to say it is: row 1 is four
    cells of text, no more privileged than row 2."""

    worksheet = _read(
        synthetic_workbooks.simple_register()
    ).workbook.worksheets[0]
    first, second = worksheet.row(1), worksheet.row(2)

    assert _texts(worksheet)["A1"] == "Cable ID"
    assert {cell.literal.value_type for cell in first.cells} == {
        CanonicalCellType.TEXT
    }
    assert type(first) is type(second)


def test_the_representation_records_its_own_provenance() -> None:
    """Which bytes, which reader, which contract - the first questions
    anyone asks when a downstream extraction looks wrong."""

    workbook = _read(synthetic_workbooks.simple_register()).workbook

    assert workbook.document_id == 7
    assert workbook.content_checksum == CHECKSUM
    assert workbook.checksum_algorithm == "sha256"
    assert workbook.reader_name == "openpyxl"
    assert workbook.reader_version
    assert workbook.representation_version == CANONICAL_WORKBOOK_VERSION


def test_the_date_system_is_recorded() -> None:
    """Two workbooks holding the identical serial denote dates four years
    apart under the two systems."""

    workbook = _read(synthetic_workbooks.simple_register()).workbook

    assert workbook.date_system is WorkbookDateSystem.EPOCH_1900


def test_a_workbook_without_macros_or_links_says_so() -> None:
    workbook = _read(synthetic_workbooks.simple_register()).workbook

    assert workbook.has_vba_project is False
    assert workbook.has_external_links is False


# --- Fixture B: several worksheets, one of them hidden --------------------


def test_every_worksheet_is_read_at_its_own_position() -> None:
    workbook = _read(synthetic_workbooks.multiple_sheets()).workbook

    assert tuple(
        (sheet.worksheet_index, sheet.name) for sheet in workbook.worksheets
    ) == ((0, "Cables"), (1, "Equipment"), (2, "Superseded"))


def test_a_hidden_worksheet_is_read_in_full_and_flagged() -> None:
    """A cable register left on a hidden tab is still what the document
    contains; skipping it would be this system deciding which parts of a
    delivered document count."""

    workbook = _read(synthetic_workbooks.multiple_sheets()).workbook
    hidden = workbook.worksheet(2)

    assert hidden.visibility is WorksheetVisibility.HIDDEN
    assert _texts(hidden) == {"A1": "CBL-099"}


def test_a_visible_worksheet_is_flagged_as_visible() -> None:
    workbook = _read(synthetic_workbooks.multiple_sheets()).workbook

    assert workbook.worksheet(0).visibility is WorksheetVisibility.VISIBLE


def test_each_worksheet_carries_its_own_used_range() -> None:
    workbook = _read(synthetic_workbooks.multiple_sheets()).workbook

    assert (
        workbook.worksheet(0).used_range.last_column,
        workbook.worksheet(1).used_range.last_column,
        workbook.worksheet(2).used_range.last_column,
    ) == (2, 3, 1)


def test_a_number_and_its_unit_are_recorded_as_the_two_cells_they_are(
) -> None:
    """``630`` in B2 and ``A`` in C2 are two observations at two
    addresses. Joining them would be reading the grid as a record."""

    equipment = _read(
        synthetic_workbooks.multiple_sheets()
    ).workbook.worksheet(1)
    rating = equipment.row(2).cells[1]
    unit = equipment.row(2).cells[2]

    assert (rating.a1_reference, rating.literal.number) == (
        "B2",
        Decimal("630"),
    )
    assert (unit.a1_reference, unit.literal.text) == ("C2", "A")


# --- Fixture C: the header a rule would get wrong -------------------------


def test_a_title_block_above_the_labels_is_recorded_as_ordinary_cells(
) -> None:
    """Row 1 is a title, row 4 is what a human would call the header, and
    the reader says nothing about either. This is the fixture that makes
    "row 1 is the header" indefensible."""

    worksheet = _read(
        synthetic_workbooks.header_offset()
    ).workbook.worksheets[0]

    assert _texts(worksheet)["A1"] == "SYNTHETIC CABLE SCHEDULE"
    assert _texts(worksheet)["A4"] == "Cable ID"
    assert tuple(row.row_number for row in worksheet.rows) == (1, 2, 4, 5)


def test_no_worksheet_claims_a_header_row_anywhere() -> None:
    """The absence is asserted rather than trusted: a header field added
    "for symmetry" would be read downstream as an observation."""

    worksheet = _read(
        synthetic_workbooks.header_offset()
    ).workbook.worksheets[0]

    for name in ("header_row", "header", "column_name", "field_name"):
        assert not hasattr(worksheet, name)
        assert not hasattr(worksheet.row(4), name)
        assert not hasattr(worksheet.row(4).cells[0], name)


# --- Fixture D: gaps that must survive as gaps ----------------------------


def test_an_absent_row_is_absent_rather_than_empty() -> None:
    worksheet = _read(
        synthetic_workbooks.sparse_and_blank()
    ).workbook.worksheets[0]

    assert tuple(row.row_number for row in worksheet.rows) == (1, 3, 4, 6)
    assert worksheet.row(2) is None


def test_a_hole_in_a_row_is_absent_rather_than_an_empty_cell() -> None:
    """B3 was never populated. Materialising it as an empty cell would be
    indistinguishable downstream from a register that genuinely says
    nothing there."""

    worksheet = _read(
        synthetic_workbooks.sparse_and_blank()
    ).workbook.worksheets[0]

    assert tuple(
        cell.column_number for cell in worksheet.row(3).cells
    ) == (1, 3)


def test_the_workbooks_own_numbers_are_never_re_indexed() -> None:
    """A gap between row 4 and row 6 is a fact about the register, and it
    stays visible and addressable."""

    worksheet = _read(
        synthetic_workbooks.sparse_and_blank()
    ).workbook.worksheets[0]

    assert _texts(worksheet)["E6"] == "island"
    assert worksheet.row(5) is None


def test_the_used_range_covers_the_cells_observed_and_no_more() -> None:
    worksheet = _read(
        synthetic_workbooks.sparse_and_blank()
    ).workbook.worksheets[0]

    assert (
        worksheet.used_range.first_row,
        worksheet.used_range.last_row,
        worksheet.used_range.first_column,
        worksheet.used_range.last_column,
    ) == (1, 6, 1, 5)


# --- Fixture E: repeated and missing labels -------------------------------


def test_repeated_text_is_not_deduplicated() -> None:
    """B1 and C1 carry the same characters. Two cells said it, so two
    cells record it."""

    worksheet = _read(
        synthetic_workbooks.duplicate_and_blank_headers()
    ).workbook.worksheets[0]

    assert _texts(worksheet)["B1"] == "Value"
    assert _texts(worksheet)["C1"] == "Value"


def test_a_column_with_no_label_is_given_none() -> None:
    """D1 is empty, so nothing is recorded for it - not a placeholder, not
    an invented name, and not a shifted neighbour."""

    worksheet = _read(
        synthetic_workbooks.duplicate_and_blank_headers()
    ).workbook.worksheets[0]

    assert tuple(
        cell.column_number for cell in worksheet.row(1).cells
    ) == (1, 2, 3, 5)
    assert _texts(worksheet)["D2"] == "orphan"


# --- Fixture F: a formula nothing has ever computed -----------------------


def test_a_formula_is_recorded_as_the_expression_the_file_states() -> None:
    worksheet = _read(
        synthetic_workbooks.formula_without_cached_result()
    ).workbook.worksheets[0]
    computed = worksheet.row(2).cells[2]

    assert computed.a1_reference == "C2"
    assert computed.formula.expression == "=A2*B2"


def test_a_formula_nothing_computed_carries_no_cached_result() -> None:
    """A workbook written by a script and never opened carries the
    formula and no value. That is recorded as exactly what it is."""

    worksheet = _read(
        synthetic_workbooks.formula_without_cached_result()
    ).workbook.worksheets[0]
    computed = worksheet.row(2).cells[2]

    assert computed.formula.cached_result is None
    assert computed.formula.has_cached_result is False


def test_a_formula_cell_carries_no_literal() -> None:
    """
    A cell whose formula was never computed must not be recorded as a
    blank cell, an empty string or a zero. Those are lies of different
    sizes, and the last two are indistinguishable downstream from a
    register that genuinely says nothing there - so the literal slot
    stays empty and the formula slot carries the claim.
    """

    worksheet = _read(
        synthetic_workbooks.formula_without_cached_result()
    ).workbook.worksheets[0]
    computed = worksheet.row(2).cells[2]

    assert computed.literal is None
    assert worksheet.row(2).cells[0].literal.number == Decimal("4")


def test_nothing_evaluates_the_formula() -> None:
    """``=A2*B2`` over 4 and 2.5 would be 10. No value resembling one
    appears anywhere in the representation."""

    workbook = _read(
        synthetic_workbooks.formula_without_cached_result()
    ).workbook
    recorded = tuple(
        cell.literal.text
        for sheet in workbook.worksheets
        for row in sheet.rows
        for cell in row.cells
        if cell.literal is not None
    )

    assert "10" not in recorded
    assert "10.0" not in recorded


# --- Fixture G: every value the reader renders ----------------------------


def test_each_value_is_typed_by_what_the_file_carries() -> None:
    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]
    types = {
        cell.a1_reference: cell.literal.value_type
        for row in worksheet.rows
        for cell in row.cells
    }

    assert types == {
        "A1": CanonicalCellType.TEXT,
        "A2": CanonicalCellType.NUMBER,
        "A3": CanonicalCellType.NUMBER,
        "A4": CanonicalCellType.BOOLEAN,
        "A5": CanonicalCellType.DATE_TIME,
        "A6": CanonicalCellType.TIME,
        "A7": CanonicalCellType.TEXT,
        "A8": CanonicalCellType.TEXT,
        "A9": CanonicalCellType.TEXT,
        "A10": CanonicalCellType.DURATION,
        "A11": CanonicalCellType.ERROR,
    }


def test_a_number_fills_its_typed_slot_so_no_consumer_re_parses_text(
) -> None:
    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]

    assert worksheet.row(2).cells[0].literal.number == Decimal("42")
    assert worksheet.row(3).cells[0].literal.number == Decimal("2.5")


def test_a_boolean_a_date_and_a_time_fill_their_own_slots() -> None:
    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]

    assert worksheet.row(4).cells[0].literal.boolean is True
    assert (
        worksheet.row(5).cells[0].literal.instant == "2026-03-14T09:30:00"
    )
    assert worksheet.row(6).cells[0].literal.instant == "09:30:00"


def test_significant_trailing_whitespace_survives() -> None:
    """``"QMT01 "`` is what the register says. Stripping it would be this
    reader editing a document it was asked to describe."""

    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]

    assert worksheet.row(7).cells[0].literal.text == "QMT01 "


def test_a_non_breaking_space_is_not_normalised_away() -> None:
    """The character a spreadsheet acquires from a web paste. NFKC would
    fold it into a plain space, and two different strings would then be
    recorded as one."""

    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]
    text = worksheet.row(8).cells[0].literal.text

    assert text == "PANEL\u00a0A"
    assert "\u00a0" in text


def test_an_embedded_newline_survives() -> None:
    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]

    assert worksheet.row(9).cells[0].literal.text == "first\nsecond"


def test_the_number_format_the_file_states_is_recorded() -> None:
    """It is the only thing distinguishing a serial date from a plain
    number in the source - recorded for that reason, not so anything
    renders from it."""

    worksheet = _read(
        synthetic_workbooks.mixed_value_types()
    ).workbook.worksheets[0]

    assert worksheet.row(5).cells[0].number_format == "yyyy-mm-dd h:mm:ss"


# --- Determinism ----------------------------------------------------------


def test_reading_the_same_bytes_twice_yields_an_equal_representation(
) -> None:
    """The whole reproducibility guarantee, asserted directly: a
    representation is a function of its bytes and its reader, and nothing
    else."""

    content = synthetic_workbooks.multiple_sheets()

    assert _read(content).workbook == _read(content).workbook


def test_two_reader_instances_agree() -> None:
    content = synthetic_workbooks.sparse_and_blank()
    first = OpenpyxlWorkbookReader().read(
        content,
        document_id=7,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )
    second = OpenpyxlWorkbookReader().read(
        content,
        document_id=7,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )

    assert first.workbook == second.workbook


def test_different_documents_produce_different_representations() -> None:
    content = synthetic_workbooks.simple_register()

    assert _read(content, document_id=1).workbook != _read(
        content, document_id=2
    ).workbook


# --- Typed failures, never exceptions -------------------------------------


def test_a_workbook_with_no_populated_cell_is_refused() -> None:
    """Persisting it would give every future consumer a register that
    appears to say nothing, which is indistinguishable from one that
    genuinely does."""

    result = _read(synthetic_workbooks.empty_workbook())

    assert result.was_read is False
    assert result.failure_code is (
        WorkbookCanonicalizationFailureCode.NO_POPULATED_CELL
    )


def test_a_corrupted_package_is_reported_as_malformed() -> None:
    result = _read(synthetic_workbooks.corrupted_package())

    assert result.failure_code is (
        WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE
    )


def test_an_encrypted_workbook_is_reported_as_locked_not_damaged() -> None:
    """The bytes are intact and someone with the password could read
    them: that is a question for whoever supplied the file, not a
    data-integrity fault."""

    result = _read(synthetic_workbooks.encrypted_workbook())

    assert result.failure_code is (
        WorkbookCanonicalizationFailureCode.ENCRYPTED_WORKBOOK
    )


def test_more_worksheets_than_the_policy_admits_is_refused() -> None:
    """Refused rather than truncated: a partial representation would look
    to every future consumer like a register that simply ends there."""

    result = _read(synthetic_workbooks.many_sheets(MAX_WORKSHEETS + 1))

    assert result.failure_code is (
        WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE
    )
    assert result.workbook is None


def test_a_workbook_within_the_worksheet_bound_is_read() -> None:
    """The bound refuses what is beyond it and nothing else."""

    result = _read(synthetic_workbooks.many_sheets(MAX_WORKSHEETS))

    assert result.was_read
    assert result.workbook.worksheet_count == MAX_WORKSHEETS


def test_empty_bytes_are_reported_as_empty_content() -> None:
    result = _read(b"")

    assert result.failure_code is (
        WorkbookCanonicalizationFailureCode.EMPTY_CONTENT
    )


def test_the_reader_never_raises_on_bad_input() -> None:
    """Every failure is a typed result, so the caller records a cause
    rather than catching whatever the library chose to throw this
    release."""

    for content in (
        b"",
        b"not a workbook at all",
        synthetic_workbooks.corrupted_package(),
        synthetic_workbooks.encrypted_workbook(),
        b"%PDF-1.7\n",
    ):
        assert _read(content).was_read is False


def test_a_failure_carries_a_stated_reason_and_no_workbook() -> None:
    result = _read(synthetic_workbooks.corrupted_package())

    assert result.detail
    assert result.workbook is None
