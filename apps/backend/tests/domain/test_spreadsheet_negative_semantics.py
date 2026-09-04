"""
The boundary tests of ADR-0034: what this milestone must **not** be able
to say.

A cable register read today produces designation-shaped text at stated
coordinates and nothing else, so a test written as "assert no cable was
created" would pass because no rule reads a cable code - and would keep
passing on the day somebody adds one. A negative test that cannot fail is
worse than no test, because it certifies a boundary it never checks.

Every assertion here is therefore written against a **closed set**: the
exact members of an enum, the exact field names of a value object, the
exact column names of a table. Widening any of them - a ``CABLE`` entity
type, a ``from_id`` field, a ``column_role`` column - fails a test here,
at the boundary, rather than being absorbed silently three milestones
later.

The architecture tests in ``tests/architecture`` assert the same
boundaries over the *source text*. These assert them over the *values and
tables the running system actually has*, which is the half a source scan
cannot see.
"""

from __future__ import annotations

from dataclasses import fields

from app.domain.canonical_spreadsheet import canonical_spreadsheet_factory
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalCellType,
    CanonicalRow,
    CanonicalWorkbook,
    CanonicalWorksheet,
    CellReference,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.engineering_entities.entity_models import EntityType
from app.domain.spreadsheet_evidence.spreadsheet_evidence_extractor import (
    extract_cell_evidence,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    CellEvidenceProvenance,
    SpreadsheetEvidence,
    SpreadsheetEvidenceSet,
)
from app.models.canonical_spreadsheet import (
    CanonicalCellRecord,
    CanonicalRowRecord,
    CanonicalWorkbookRecord,
    CanonicalWorksheetRecord,
)
from app.models.spreadsheet_evidence import (
    SpreadsheetEvidenceRecord,
    SpreadsheetEvidenceSetRecord,
)

#: Names that would each introduce a judgement this milestone has no way
#: to check: a relationship between two cells, a role for a column, or an
#: identity for the thing a cell supposedly denotes.
#:
#: They are asserted as a set against every field and column of the two
#: contexts, so the test fails on the *first* one added rather than on a
#: reviewer noticing later. ADR-0034 §6 and §10 are the argument; this is
#: the enforcement.
FORBIDDEN_NAMES = frozenset(
    {
        "from_id",
        "to_id",
        "source_id",
        "destination_id",
        "connects",
        "connected_to",
        "relation",
        "relation_kind",
        "role",
        "column_role",
        "semantic_role",
        "entity_id",
        "equipment_id",
        "cable_id",
        "circuit_id",
        "terminal_id",
        "belongs_to",
        "parent_id",
        "header",
        "header_row",
        "column_name",
        "field_name",
        "record",
    }
)

SPREADSHEET_VALUE_OBJECTS = (
    CanonicalCell,
    CanonicalRow,
    CanonicalWorksheet,
    CanonicalWorkbook,
    CellReference,
    UsedRange,
    CellEvidenceProvenance,
    SpreadsheetEvidence,
    SpreadsheetEvidenceSet,
)

SPREADSHEET_TABLES = (
    CanonicalWorkbookRecord,
    CanonicalWorksheetRecord,
    CanonicalRowRecord,
    CanonicalCellRecord,
    SpreadsheetEvidenceSetRecord,
    SpreadsheetEvidenceRecord,
)


def _field_names(value_object: type) -> frozenset[str]:
    return frozenset(field.name for field in fields(value_object))


def _column_names(model: type) -> frozenset[str]:
    return frozenset(column.name for column in model.__table__.columns)


# --- The catalogue of things this platform can conclude -------------------


def test_the_entity_catalogue_admits_no_cable_and_no_circuit() -> None:
    """
    Pinned as a closed set on purpose.

    This milestone reads registers full of cable codes and creates no
    entity from any of them. The day a ``CABLE`` member is added, that
    decision has to be argued for here - in the test that states what the
    platform is willing to conclude - rather than appearing quietly in an
    enum three files away.
    """

    assert set(EntityType) == {
        EntityType.EQUIPMENT_DESIGNATION,
        EntityType.ENGINEERING_QUANTITY,
        EntityType.STRUCTURAL_LOCATION,
    }


# --- The evidence model has nowhere to put a relationship -----------------


def test_an_observation_carries_exactly_these_fields() -> None:
    """
    The exact set, so a field added for a relationship fails here.

    "There is nowhere in the model to record a connection" is only true
    while the set of places is enumerated; a ``related_to`` added for one
    convenient case would make every consumer able to read a judgement
    out of an observation.
    """

    assert _field_names(SpreadsheetEvidence) == {
        "evidence_key",
        "evidence_type",
        "status",
        "observed_text",
        "rule_id",
        "rule_version",
        "provenance",
        "quantity",
        "designation",
    }


def test_provenance_carries_exactly_the_cell_coordinates() -> None:
    """Cell-shaped and complete: no page, no paragraph, no line, no span,
    and equally no neighbouring cell, no column role and no record
    index."""

    assert _field_names(CellEvidenceProvenance) == {
        "worksheet_index",
        "worksheet_name",
        "row_number",
        "column_number",
        "column_label",
        "character_start",
        "character_end",
        "source_text",
    }


def test_an_evidence_set_carries_exactly_these_fields() -> None:
    assert _field_names(SpreadsheetEvidenceSet) == {
        "document_id",
        "project_id",
        "content_checksum",
        "representation_version",
        "extraction_policy_version",
        "evidence",
        "artifact_identity",
        "upstream_identity",
    }


def test_no_value_object_in_either_context_carries_a_forbidden_name(
) -> None:
    """One assertion over every value object of both contexts, so a new
    relational or interpretive field fails wherever it is added."""

    offenders = {
        value_object.__name__: sorted(
            _field_names(value_object) & FORBIDDEN_NAMES
        )
        for value_object in SPREADSHEET_VALUE_OBJECTS
        if _field_names(value_object) & FORBIDDEN_NAMES
    }

    assert offenders == {}


# --- The schema has nowhere to put one either -----------------------------


def test_the_canonical_cell_table_carries_exactly_these_columns() -> None:
    """
    A cell is coordinates, a display format, and one of two mutually
    exclusive readings of what it holds.

    Stated as the exact set because the pressure ADR-0034 predicts lands
    here first: a ``column_role`` or a ``header_row`` column would be a
    one-line migration, and every consumer downstream would read the
    guess as an observation.
    """

    assert _column_names(CanonicalCellRecord) == {
        "id",
        "row_id",
        "column_number",
        "number_format",
        "literal_type",
        "literal_text",
        "literal_number",
        "literal_boolean",
        "literal_instant",
        "literal_duration",
        "literal_error_code",
        "formula_expression",
        "cached_type",
        "cached_text",
        "cached_number",
        "cached_boolean",
        "cached_instant",
        "cached_duration",
        "cached_error_code",
    }


def test_the_canonical_row_table_carries_only_its_number() -> None:
    """A row is a number and its cells. Anything else stored here would
    be a claim about what the row *is*."""

    assert _column_names(CanonicalRowRecord) == {
        "id",
        "worksheet_id",
        "row_number",
    }


def test_the_worksheet_table_carries_no_header_and_no_extent_it_invented(
) -> None:
    assert _column_names(CanonicalWorksheetRecord) == {
        "id",
        "workbook_id",
        "worksheet_index",
        "name",
        "visibility",
        "used_first_row",
        "used_last_row",
        "used_first_column",
        "used_last_column",
    }


def test_the_spreadsheet_evidence_table_carries_exactly_these_columns(
) -> None:
    """The persisted shape of one observation, pinned for the same reason
    the value object is: a stored relational column is far harder to
    remove than a proposed one."""

    assert _column_names(SpreadsheetEvidenceRecord) == {
        "id",
        "evidence_set_id",
        "evidence_key",
        "evidence_type",
        "status",
        "observed_text",
        "rule_id",
        "rule_version",
        "quantity_value",
        "quantity_unit",
        "quantity_base_value",
        "quantity_base_unit",
        "designation_normalized",
        "worksheet_index",
        "worksheet_name",
        "row_number",
        "column_number",
        "column_label",
        "character_start",
        "character_end",
        "source_text",
    }


def test_no_table_in_either_context_carries_a_forbidden_column() -> None:
    """One assertion over every table both contexts own, so a relational
    column fails wherever the migration puts it."""

    offenders = {
        model.__tablename__: sorted(_column_names(model) & FORBIDDEN_NAMES)
        for model in SPREADSHEET_TABLES
        if _column_names(model) & FORBIDDEN_NAMES
    }

    assert offenders == {}


def test_no_table_names_a_cable_a_circuit_or_a_terminal() -> None:
    """Neither the table names nor the column names admit the vocabulary
    a register tempts a reader into: what is stored is a grid."""

    vocabulary = ("cable", "circuit", "terminal", "connect", "conductor")
    names = {model.__tablename__ for model in SPREADSHEET_TABLES} | {
        column for model in SPREADSHEET_TABLES
        for column in _column_names(model)
    }

    assert not [
        name for name in names if any(word in name for word in vocabulary)
    ]


# --- Row adjacency is a fact about a grid, never a connection -------------


def _two_cells_in_one_row() -> SpreadsheetEvidenceSet:
    """A register row carrying a designation in column A and another in
    column B - the shape an engineer reads as "A connects to B"."""

    cells = tuple(
        canonical_spreadsheet_factory.build_cell(
            row_number=2,
            column_number=column,
            literal=canonical_spreadsheet_factory.build_cell_value(
                value_type=CanonicalCellType.TEXT, text=text
            ),
        )
        for column, text in ((1, "QA1"), (2, "TR1"))
    )
    row = canonical_spreadsheet_factory.build_row(row_number=2, cells=cells)
    worksheet = canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=0,
        name="Register",
        visibility=WorksheetVisibility.VISIBLE,
        rows=(row,),
        used_range=canonical_spreadsheet_factory.build_used_range(
            first_row=2, last_row=2, first_column=1, last_column=2
        ),
    )

    return extract_cell_evidence(
        canonical_spreadsheet_factory.build_workbook(
            document_id=7,
            content_checksum="a" * 64,
            checksum_algorithm="sha256",
            representation_version="1.0",
            reader_name="openpyxl",
            reader_version="3.1.5",
            date_system=WorkbookDateSystem.EPOCH_1900,
            has_vba_project=False,
            has_external_links=False,
            worksheets=(worksheet,),
        )
    )


def test_two_cells_in_one_row_are_two_independent_observations() -> None:
    """
    That two designations share a row is an observation about a grid -
    exactly as two observations on the same line of a PDF are two
    observations that happen to be adjacent.

    Independence is asserted three ways, because "no relationship was
    created" is only meaningful if the observations could not encode one:
    distinct identities, no field naming the other, and no substring of
    one appearing anywhere in the other's record.
    """

    first, second = _two_cells_in_one_row().evidence

    assert first.evidence_key != second.evidence_key
    assert first.provenance.a1_reference == "A2"
    assert second.provenance.a1_reference == "B2"

    for item, other_text in ((first, "TR1"), (second, "QA1")):
        recorded = {
            field.name: getattr(item, field.name) for field in fields(item)
        }
        assert other_text not in str(recorded)
