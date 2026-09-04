from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.canonical_spreadsheet import canonical_spreadsheet_factory
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalCellType,
    CanonicalWorkbook,
    CellValue,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.canonical_spreadsheet.canonical_workbook_repository import (
    CanonicalWorkbookRepository,
)
from app.models.canonical_spreadsheet import (
    CanonicalCellRecord,
    CanonicalRowRecord,
    CanonicalWorkbookRecord,
    CanonicalWorksheetRecord,
)


class SqlAlchemyCanonicalWorkbookRepository(CanonicalWorkbookRepository):
    """
    SQLAlchemy adapter over the four canonical-workbook tables.

    Writes only those tables. It holds no reference to the document row,
    to ``Document.file_path``, or to stored content of any kind - the
    uploaded workbook is authoritative and this adapter has no way to
    touch it. It imports no spreadsheet library: by the time a
    representation reaches here it is value objects, and the only module
    that knows what a workbook is made of is the reader adapter.

    On read it rebuilds the value objects **through the domain factory**,
    so a row that somehow violates an invariant is refused on the way out
    exactly as it would have been on the way in. A representation is
    trusted by every future consumer; it should never be trusted merely
    because it is old.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, representation: CanonicalWorkbook) -> None:
        record = CanonicalWorkbookRecord(
            artifact_identity=representation.artifact_identity,
            upstream_identity=representation.upstream_identity,
            document_id=representation.document_id,
            content_checksum=representation.content_checksum,
            checksum_algorithm=representation.checksum_algorithm,
            representation_version=representation.representation_version,
            reader_name=representation.reader_name,
            reader_version=representation.reader_version,
            date_system=representation.date_system,
            has_vba_project=representation.has_vba_project,
            has_external_links=representation.has_external_links,
            worksheet_count=representation.worksheet_count,
        )

        for worksheet in representation.worksheets:
            used = worksheet.used_range
            worksheet_record = CanonicalWorksheetRecord(
                worksheet_index=worksheet.worksheet_index,
                name=worksheet.name,
                visibility=worksheet.visibility,
                used_first_row=None if used is None else used.first_row,
                used_last_row=None if used is None else used.last_row,
                used_first_column=(
                    None if used is None else used.first_column
                ),
                used_last_column=None if used is None else used.last_column,
            )

            for row in worksheet.rows:
                row_record = CanonicalRowRecord(row_number=row.row_number)

                for cell in row.cells:
                    row_record.cells.append(_cell_record(cell))

                worksheet_record.rows.append(row_record)

            record.worksheets.append(worksheet_record)

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> CanonicalWorkbook | None:
        record = (
            self._session.query(CanonicalWorkbookRecord)
            .filter(
                CanonicalWorkbookRecord.document_id == document_id,
                CanonicalWorkbookRecord.artifact_identity
                == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> CanonicalWorkbook | None:
        record = (
            self._session.query(CanonicalWorkbookRecord)
            .filter(CanonicalWorkbookRecord.document_id == document_id)
            .order_by(CanonicalWorkbookRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _cell_record(cell: CanonicalCell) -> CanonicalCellRecord:
    """
    A cell's literal and its formula's cached result are written to
    **different columns**, so nothing downstream can conflate what the
    engineer typed with what another application computed.

    A formula whose ``cached_result`` is ``None`` leaves every
    ``cached_*`` column null. That is the record of "no application has
    ever computed a value into this file for this cell" - never a blank,
    an empty string or a zero.
    """

    literal = cell.literal
    formula = cell.formula
    cached = None if formula is None else formula.cached_result

    return CanonicalCellRecord(
        column_number=cell.column_number,
        number_format=cell.number_format,
        literal_type=None if literal is None else literal.value_type,
        literal_text=None if literal is None else literal.text,
        literal_number=None if literal is None else literal.number,
        literal_boolean=None if literal is None else literal.boolean,
        literal_instant=None if literal is None else literal.instant,
        literal_duration=None if literal is None else literal.duration,
        literal_error_code=None if literal is None else literal.error_code,
        formula_expression=None if formula is None else formula.expression,
        cached_type=None if cached is None else cached.value_type,
        cached_text=None if cached is None else cached.text,
        cached_number=None if cached is None else cached.number,
        cached_boolean=None if cached is None else cached.boolean,
        cached_instant=None if cached is None else cached.instant,
        cached_duration=None if cached is None else cached.duration,
        cached_error_code=None if cached is None else cached.error_code,
    )


def _to_domain(record: CanonicalWorkbookRecord) -> CanonicalWorkbook:
    built = canonical_spreadsheet_factory.build_workbook(
        document_id=record.document_id,
        content_checksum=record.content_checksum,
        checksum_algorithm=record.checksum_algorithm,
        representation_version=record.representation_version,
        reader_name=record.reader_name,
        reader_version=record.reader_version,
        date_system=WorkbookDateSystem(record.date_system),
        has_vba_project=record.has_vba_project,
        has_external_links=record.has_external_links,
        worksheets=tuple(
            canonical_spreadsheet_factory.build_worksheet(
                worksheet_index=worksheet.worksheet_index,
                name=worksheet.name,
                visibility=WorksheetVisibility(worksheet.visibility),
                rows=tuple(
                    canonical_spreadsheet_factory.build_row(
                        row_number=row.row_number,
                        cells=tuple(
                            _to_cell(row.row_number, cell)
                            for cell in row.cells
                        ),
                    )
                    for row in worksheet.rows
                ),
                used_range=_to_used_range(worksheet),
            )
            for worksheet in record.worksheets
        ),
    )

    # The factory validates the representation; identity is provenance
    # recorded about it, not something it validates.
    return replace(
        built,
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
    )


def _to_used_range(
    record: CanonicalWorksheetRecord,
) -> UsedRange | None:
    if record.used_first_row is None:
        return None

    return canonical_spreadsheet_factory.build_used_range(
        first_row=record.used_first_row,
        last_row=record.used_last_row,
        first_column=record.used_first_column,
        last_column=record.used_last_column,
    )


def _to_cell(row_number: int, record: CanonicalCellRecord) -> CanonicalCell:
    formula = (
        None
        if record.formula_expression is None
        else canonical_spreadsheet_factory.build_formula(
            expression=record.formula_expression,
            cached_result=_to_value(
                record.cached_type,
                record.cached_text,
                record.cached_number,
                record.cached_boolean,
                record.cached_instant,
                record.cached_duration,
                record.cached_error_code,
            ),
        )
    )

    return canonical_spreadsheet_factory.build_cell(
        row_number=row_number,
        column_number=record.column_number,
        number_format=record.number_format,
        literal=_to_value(
            record.literal_type,
            record.literal_text,
            record.literal_number,
            record.literal_boolean,
            record.literal_instant,
            record.literal_duration,
            record.literal_error_code,
        ),
        formula=formula,
    )


def _to_value(
    value_type: CanonicalCellType | None,
    text: str | None,
    number: Decimal | None,
    boolean: bool | None,
    instant: str | None,
    duration: str | None,
    error_code: str | None,
) -> CellValue | None:
    """
    One value, or ``None`` when the column group holds nothing.

    ``value_type`` is what decides: a group with no declared kind
    recorded no value, and reconstructing one from whichever slot
    happened to be populated would be this adapter guessing.
    """

    if value_type is None:
        return None

    return canonical_spreadsheet_factory.build_cell_value(
        value_type=CanonicalCellType(value_type),
        text=text or "",
        number=None if number is None else _normalized(number),
        boolean=boolean,
        instant=instant,
        duration=duration,
        error_code=error_code,
    )


def _normalized(value: Decimal) -> Decimal:
    """
    Values are normalised on the way out.

    A numeric column returns a ``Decimal`` whose exponent reflects the
    column's declared scale, so ``Decimal("2.5")`` stored comes back as
    ``Decimal("2.500000000000")``. Both are the same number and
    ``Decimal.__eq__`` agrees, so the value objects compare equal either
    way - ``normalize`` is applied so a reader sees the number the
    workbook wrote rather than the column's padding.
    """

    normalized = Decimal(value).normalize()

    # ``normalize`` renders large integers in exponent form
    # (Decimal("630000") -> Decimal("6.3E+5")). Equal as numbers, but
    # surprising to read back, so integral values are restored to plain
    # notation.
    return (
        normalized.quantize(Decimal(1))
        if normalized == normalized.to_integral_value()
        else normalized
    )
