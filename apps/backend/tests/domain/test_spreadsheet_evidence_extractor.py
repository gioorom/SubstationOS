"""
Tests for the spreadsheet evidence extractor (ADR-0034).

Pure domain tests over hand-built canonical workbooks: no file, no
spreadsheet library, no database. The grids mirror the synthetic
workbooks the reader is tested against, so the two layers are specified
against the same registers without this one depending on that one.

They specify what the rule catalogue observes in a cell and - at least as
importantly - what it refuses to observe. A cell is the whole window a
rule may look at, and every "nothing was found" test here names the
boundary it is guarding, because a false observation becomes an entity
somebody has to disprove.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.domain.canonical_spreadsheet import canonical_spreadsheet_factory
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCellType,
    CanonicalRow,
    CanonicalWorkbook,
    CanonicalWorksheet,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_extractor import (
    extract_cell_evidence,
    observable_text,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    SpreadsheetEvidenceSet,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_policy import (
    SPREADSHEET_EXTRACTION_POLICY_VERSION,
)

#: The cable register the reader fixtures use, as a grid: row number ->
#: column number -> the cell's text. Not one token of it matches a
#: designation pattern, which is what makes it the right negative case.
CABLE_REGISTER: dict[int, dict[int, str]] = {
    1: {1: "Cable ID", 2: "From", 3: "To", 4: "Function"},
    2: {1: "CBL-001", 2: "PANEL-A", 3: "PANEL-B", 4: "Control"},
    3: {1: "CBL-002", 2: "PANEL-B", 3: "PANEL-C", 4: "Power"},
}


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
    index: int, name: str, grid: dict[int, dict[int, str]]
) -> CanonicalWorksheet:
    rows = tuple(
        canonical_spreadsheet_factory.build_row(
            row_number=row_number,
            cells=tuple(
                canonical_spreadsheet_factory.build_cell(
                    row_number=row_number,
                    column_number=column_number,
                    literal=canonical_spreadsheet_factory.build_cell_value(
                        value_type=CanonicalCellType.TEXT, text=text
                    ),
                )
                for column_number, text in sorted(columns.items())
            ),
        )
        for row_number, columns in sorted(grid.items())
    )

    return canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=index,
        name=name,
        visibility=WorksheetVisibility.VISIBLE,
        rows=rows,
        used_range=_used_range(rows),
    )


def _workbook(
    *worksheets: CanonicalWorksheet,
    document_id: int = 7,
    content_checksum: str = "a" * 64,
    artifact_identity: str | None = None,
) -> CanonicalWorkbook:
    workbook = canonical_spreadsheet_factory.build_workbook(
        document_id=document_id,
        content_checksum=content_checksum,
        checksum_algorithm="sha256",
        representation_version="1.0",
        reader_name="openpyxl",
        reader_version="3.1.5",
        date_system=WorkbookDateSystem.EPOCH_1900,
        has_vba_project=False,
        has_external_links=False,
        worksheets=worksheets,
    )

    if artifact_identity is None:
        return workbook

    return replace(workbook, artifact_identity=artifact_identity)


def _one_sheet(
    grid: dict[int, dict[int, str]], name: str = "Register"
) -> SpreadsheetEvidenceSet:
    """The evidence of a single-worksheet workbook carrying ``grid``."""

    return extract_cell_evidence(_workbook(_worksheet(0, name, grid)))


def _cell(
    text: str, *, row: int = 2, column: int = 1
) -> SpreadsheetEvidenceSet:
    """The evidence of one cell, at coordinates the test can state."""

    return _one_sheet({row: {column: text}})


def _texts(
    evidence_set: SpreadsheetEvidenceSet, evidence_type: EvidenceType
) -> list[str]:
    return [item.observed_text for item in evidence_set.of_type(evidence_type)]


# --- What a cell states ---------------------------------------------------


def test_a_designation_in_a_cell_is_observed() -> None:
    result = _cell("QA1")

    assert _texts(result, EvidenceType.DESIGNATION) == ["QA1"]


def test_a_quantity_written_in_one_cell_is_observed() -> None:
    result = _cell("630 A")
    item = result.of_type(EvidenceType.CURRENT_VALUE)[0]

    assert item.quantity.value == Decimal("630")
    assert item.quantity.unit == "A"


def test_a_number_and_a_unit_in_two_cells_are_not_a_quantity() -> None:
    """``630`` in B2 and ``A`` in C2 are two cells. Pairing them would be
    reading the grid as a record - the inference this milestone refuses -
    and there is no cross-cell window in which a rule could even see
    both."""

    result = _one_sheet({2: {2: "630", 3: "A"}})

    assert result.of_type(EvidenceType.CURRENT_VALUE) == ()
    assert result.evidence_count == 0


def test_a_number_alone_in_a_cell_is_not_a_quantity() -> None:
    """An undeclared unit is not a unit: nothing is inferred from a
    neighbouring cell, a column position, or a header-shaped row
    above."""

    assert _cell("630").evidence_count == 0


def test_a_compound_designation_yields_its_location_aspect_too() -> None:
    result = _cell("+E01-QA1")

    assert _texts(result, EvidenceType.DESIGNATION) == ["+E01-QA1"]
    assert _texts(result, EvidenceType.LOCATION_ASPECT) == ["+E01"]


def test_an_ambiguous_number_is_observed_without_a_value() -> None:
    """The observation is real; the number is not settled, and a consumer
    must not be able to read a guess as a measurement."""

    item = _cell("1.250 kVA").of_type(EvidenceType.POWER_VALUE)[0]

    assert item.status is EvidenceStatus.AMBIGUOUS
    assert item.quantity is None


# --- The cable register observes nothing, and that is the point -----------


def test_a_cable_register_row_yields_no_observation_at_all() -> None:
    """``CBL-001`` and ``PANEL-A`` match no designation pattern - the
    hyphen breaks letters-then-digits - so the register produces nothing.

    The value of this test is that it is *specific*: it names the count,
    so a rule added later that starts reading cable codes changes this
    number and has to be argued for rather than absorbed.
    """

    result = _one_sheet(CABLE_REGISTER)

    assert result.evidence_count == 0
    assert result.is_empty is True


def test_a_header_shaped_row_is_read_exactly_like_a_data_row() -> None:
    """Row 1 carries ``Cable ID``, ``From``, ``To``. Nothing privileges
    it, and nothing skips it: it is offered to the same rules as row 2
    and, like row 2, matches none of them."""

    labelled = _one_sheet({1: CABLE_REGISTER[1]})
    data = _one_sheet({2: CABLE_REGISTER[2]})

    assert labelled.evidence_count == data.evidence_count == 0


# --- A formula states a value, or it states none --------------------------


def test_a_formula_with_no_cached_result_contributes_nothing() -> None:
    """No application has ever computed a value into this file for this
    cell, so the cell states nothing - and the expression is not read as
    if it were a value."""

    cell = canonical_spreadsheet_factory.build_cell(
        row_number=2,
        column_number=3,
        formula=canonical_spreadsheet_factory.build_formula(
            expression="=A2*B2"
        ),
    )
    row = canonical_spreadsheet_factory.build_row(
        row_number=2, cells=(cell,)
    )
    worksheet = canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=0,
        name="Computed",
        visibility=WorksheetVisibility.VISIBLE,
        rows=(row,),
        used_range=_used_range((row,)),
    )

    assert observable_text(cell) is None
    assert extract_cell_evidence(_workbook(worksheet)).evidence_count == 0


def test_a_formula_expression_is_never_tokenised() -> None:
    """``=QA1*2`` states how a value would be computed. Matching
    designation-shaped text inside it would record the register's
    arithmetic as if it were the register's content."""

    cell = canonical_spreadsheet_factory.build_cell(
        row_number=2,
        column_number=1,
        formula=canonical_spreadsheet_factory.build_formula(
            expression="=QA1*2"
        ),
    )
    row = canonical_spreadsheet_factory.build_row(
        row_number=2, cells=(cell,)
    )
    worksheet = canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=0,
        name="Computed",
        visibility=WorksheetVisibility.VISIBLE,
        rows=(row,),
        used_range=_used_range((row,)),
    )

    result = extract_cell_evidence(_workbook(worksheet))

    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_a_formulas_cached_result_is_what_the_cell_states() -> None:
    """A cached value is a claim by whatever last opened the workbook,
    and it is the only value the file actually states for that cell."""

    cell = canonical_spreadsheet_factory.build_cell(
        row_number=2,
        column_number=1,
        formula=canonical_spreadsheet_factory.build_formula(
            expression="=B2",
            cached_result=canonical_spreadsheet_factory.build_cell_value(
                value_type=CanonicalCellType.TEXT, text="QA1"
            ),
        ),
    )
    row = canonical_spreadsheet_factory.build_row(
        row_number=2, cells=(cell,)
    )
    worksheet = canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=0,
        name="Computed",
        visibility=WorksheetVisibility.VISIBLE,
        rows=(row,),
        used_range=_used_range((row,)),
    )

    result = extract_cell_evidence(_workbook(worksheet))

    assert observable_text(cell) == "QA1"
    assert _texts(result, EvidenceType.DESIGNATION) == ["QA1"]


# --- Provenance is exact, and it is recorded at match time ----------------


def test_character_offsets_recover_the_observed_text_from_the_cell(
) -> None:
    """The provenance guarantee, asserted directly rather than by
    searching for the text: the recorded range indexes the cell's own
    string, and slicing it returns exactly what was observed."""

    cell_text = "quadro QA1 e trasformatore TR1"
    result = _cell(cell_text)

    assert result.evidence_count == 2
    for item in result.evidence:
        recovered = cell_text[
            item.provenance.character_start : item.provenance.character_end
        ]
        assert recovered == item.observed_text


def test_offsets_exclude_the_punctuation_that_was_trimmed() -> None:
    """``(T1),`` yields an observation whose range covers ``T1`` and not
    the brackets. Trimming without narrowing the range would be a small,
    permanent lie about where the observation came from."""

    cell_text = "(T1),"
    item = _cell(cell_text).of_type(EvidenceType.DESIGNATION)[0]

    assert (
        cell_text[
            item.provenance.character_start : item.provenance.character_end
        ]
        == "T1"
    )


def test_provenance_addresses_the_cell_the_way_the_workbook_does() -> None:
    item = _one_sheet({2: {2: "QA1"}}, name="Equipment").evidence[0]

    assert item.provenance.worksheet_index == 0
    assert item.provenance.worksheet_name == "Equipment"
    assert item.provenance.row_number == 2
    assert item.provenance.column_number == 2
    assert item.provenance.column_label == "B"
    assert item.provenance.a1_reference == "B2"


def test_the_same_text_on_two_worksheets_stays_distinguishable() -> None:
    """Provenance must not collapse. Two worksheets carrying the same
    string at the same row and column are two observations, and the
    worksheet is what tells them apart."""

    result = extract_cell_evidence(
        _workbook(
            _worksheet(0, "Alpha", {2: {1: "QA1"}}),
            _worksheet(1, "Beta", {2: {1: "QA1"}}),
        )
    )
    first, second = result.evidence

    assert first.observed_text == second.observed_text == "QA1"
    assert (first.provenance.worksheet_index, first.provenance.worksheet_name) == (
        0,
        "Alpha",
    )
    assert (second.provenance.worksheet_index, second.provenance.worksheet_name) == (
        1,
        "Beta",
    )
    assert first.evidence_key != second.evidence_key


def test_the_evidence_key_changes_when_the_coordinate_changes() -> None:
    """The coordinates are in the key, so the same text observed
    elsewhere in the same workbook is a different observation."""

    at_a2 = _cell("QA1", row=2, column=1).evidence[0]
    at_a3 = _cell("QA1", row=3, column=1).evidence[0]
    at_b2 = _cell("QA1", row=2, column=2).evidence[0]

    assert len({at_a2.evidence_key, at_a3.evidence_key, at_b2.evidence_key}) == 3


def test_a_key_survives_the_same_extraction_run_twice() -> None:
    """Deterministic by construction, which is what lets the schema
    enforce idempotency rather than merely hope for it."""

    first = _one_sheet({2: {1: "QA1", 2: "630 A"}})
    second = _one_sheet({2: {1: "QA1", 2: "630 A"}})

    assert [item.evidence_key for item in first.evidence] == [
        item.evidence_key for item in second.evidence
    ]


def test_two_workbooks_of_different_documents_yield_different_keys(
) -> None:
    first = extract_cell_evidence(
        _workbook(_worksheet(0, "S", {2: {1: "QA1"}}), document_id=1)
    )
    second = extract_cell_evidence(
        _workbook(_worksheet(0, "S", {2: {1: "QA1"}}), document_id=2)
    )

    assert first.evidence[0].evidence_key != second.evidence[0].evidence_key


# --- One extraction, one set ---------------------------------------------


def test_the_set_records_the_provenance_of_the_workbook_it_read() -> None:
    result = extract_cell_evidence(
        _workbook(
            _worksheet(0, "Register", {2: {1: "QA1"}}),
            document_id=11,
            content_checksum="c" * 64,
        ),
        project_id=4,
    )

    assert result.document_id == 11
    assert result.project_id == 4
    assert result.content_checksum == "c" * 64
    assert result.representation_version == "1.0"
    assert (
        result.extraction_policy_version
        == SPREADSHEET_EXTRACTION_POLICY_VERSION
    )


def test_the_set_carries_the_identity_of_the_workbook_it_derived_from(
) -> None:
    result = extract_cell_evidence(
        _workbook(
            _worksheet(0, "Register", {2: {1: "QA1"}}),
            artifact_identity="a" * 64,
        )
    )

    assert result.upstream_identity == "a" * 64
    assert result.artifact_identity


def test_a_workbook_with_no_identity_yields_a_set_with_none() -> None:
    """Unknown provenance is not compatible provenance: an artifact that
    cannot say what it came from can never prove a reuse is valid."""

    result = extract_cell_evidence(
        _workbook(_worksheet(0, "Register", {2: {1: "QA1"}}))
    )

    assert result.artifact_identity is None
    assert result.upstream_identity is None


def test_the_same_workbook_extracted_twice_yields_an_equal_set() -> None:
    workbook = _workbook(_worksheet(0, "Register", {2: {1: "QA1"}}))

    assert extract_cell_evidence(workbook) == extract_cell_evidence(workbook)


def test_worksheets_are_walked_in_the_workbooks_own_order() -> None:
    result = extract_cell_evidence(
        _workbook(
            _worksheet(0, "Cables", {2: {1: "QA1"}}),
            _worksheet(1, "Equipment", {2: {1: "TR1"}}),
        )
    )

    assert [item.observed_text for item in result.evidence] == ["QA1", "TR1"]
