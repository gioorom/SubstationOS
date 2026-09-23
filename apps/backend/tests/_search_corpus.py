"""
A small substation corpus, built directly as canonical representations.

**Every word of it is invented.** These are deterministic fixtures
written to look like substation documents - a single-line diagram, a
cable schedule - so that search can be tested against the shapes real
documents have: designations with aspect prefixes, the same identifier
appearing in two documents and in two projects, ratings written as
``150/20 kV``, sheet names in Italian.

Nothing here comes from a real installation, a real customer or a real
drawing, and nothing here may.

The corpus is written as canonical PDF and workbook records rather than
as files, because indexing reads those. Building files and processing
them would test the pipeline, which has its own tests, and would make
these tests slow and dependent on a parser.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.canonical_pdf import (
    CanonicalBlockKind,
    CanonicalPdfBlockRecord,
    CanonicalPdfPageRecord,
    CanonicalPdfRepresentation,
    CanonicalPdfSpanRecord,
)
from app.models.canonical_spreadsheet import (
    CanonicalCellRecord,
    CanonicalRowRecord,
    CanonicalWorkbookRecord,
    CanonicalWorksheetRecord,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.models.document import Document
from app.models.project import Project


def make_project(session: Session, *, name: str, code: str) -> Project:
    """A project to file documents under."""

    project = Project(name=name, code=code, customer="Cliente di prova")
    session.add(project)
    session.commit()
    session.refresh(project)

    return project


def make_document(
    session: Session,
    *,
    project: Project | None,
    filename: str,
    checksum: str | None = None,
) -> Document:
    """A document row. Its bytes are never written - nothing reads them."""

    document = Document(
        filename=filename,
        file_path=f"storage/{filename}",
        project_id=None if project is None else project.id,
        content_checksum=checksum,
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    return document


def add_pdf_pages(
    session: Session,
    document: Document,
    pages: dict[int, list[str]],
) -> CanonicalPdfRepresentation:
    """
    A canonical PDF whose pages hold the given lines.

    ``pages`` maps a 1-based page number to its lines in reading order.
    Each line becomes one block holding one span, which is the simplest
    arrangement that still exercises the grouping the reader does.
    """

    representation = CanonicalPdfRepresentation(
        document_id=document.id,
        content_checksum=document.content_checksum or "0" * 64,
        checksum_algorithm="sha256",
        representation_version="1",
        parser_name="fixture",
        parser_version="1",
        page_count=len(pages),
    )
    session.add(representation)
    session.flush()

    for page_number, lines in sorted(pages.items()):
        page = CanonicalPdfPageRecord(
            representation_id=representation.id,
            page_number=page_number,
            width=595.0,
            height=842.0,
        )
        session.add(page)
        session.flush()

        for order, line in enumerate(lines):
            block = CanonicalPdfBlockRecord(
                page_id=page.id,
                reading_order=order,
                kind=CanonicalBlockKind.TEXT,
                x0=0.0,
                y0=float(order * 10),
                x1=500.0,
                y1=float(order * 10 + 8),
            )
            session.add(block)
            session.flush()

            session.add(
                CanonicalPdfSpanRecord(
                    block_id=block.id,
                    reading_order=0,
                    line_index=0,
                    text=line,
                    x0=0.0,
                    y0=float(order * 10),
                    x1=500.0,
                    y1=float(order * 10 + 8),
                    font_family="Helvetica",
                    font_size=9.0,
                    bold=False,
                    italic=False,
                )
            )

    session.commit()

    return representation


def add_worksheet(
    session: Session,
    document: Document,
    *,
    sheet_name: str,
    rows: list[list[object]],
) -> CanonicalWorkbookRecord:
    """
    A canonical workbook with one worksheet holding ``rows``.

    A cell value that is a string is stored as ``literal_text``; a
    number as ``literal_number``, exactly as the spreadsheet context
    stores them. ``None`` leaves the cell empty.
    """

    workbook = CanonicalWorkbookRecord(
        document_id=document.id,
        content_checksum=document.content_checksum or "0" * 64,
        checksum_algorithm="sha256",
        representation_version="1",
        reader_name="fixture",
        reader_version="1",
        date_system=WorkbookDateSystem.EPOCH_1900,
        has_vba_project=False,
        has_external_links=False,
        worksheet_count=1,
    )
    session.add(workbook)
    session.flush()

    worksheet = CanonicalWorksheetRecord(
        workbook_id=workbook.id,
        worksheet_index=0,
        name=sheet_name,
        visibility=WorksheetVisibility.VISIBLE,
    )
    session.add(worksheet)
    session.flush()

    for row_number, values in enumerate(rows, start=1):
        row = CanonicalRowRecord(
            worksheet_id=worksheet.id, row_number=row_number
        )
        session.add(row)
        session.flush()

        for column_number, value in enumerate(values, start=1):
            if value is None:
                continue

            cell = CanonicalCellRecord(
                row_id=row.id, column_number=column_number
            )

            if isinstance(value, str):
                cell.literal_text = value
            else:
                cell.literal_number = Decimal(str(value))

            session.add(cell)

    session.commit()

    return workbook


# --- The corpus ----------------------------------------------------------

#: A single-line diagram's text. Page 1 is the title block, page 2 the
#: equipment list, page 3 the protection scheme.
SINGLE_LINE_DIAGRAM: dict[int, list[str]] = {
    1: [
        "SCHEMA UNIFILARE - STAZIONE ELETTRICA DI PROVA",
        "Trasformatore TR1 - 150/20 kV - 40 MVA",
        "Disegno n. 189L - Revisione 00",
    ],
    2: [
        "Sezionatore -Q1 lato alta tensione",
        "Interruttore Q01 di manovra",
        "Trasformatore TR2 - 150/20 kV - 25 MVA",
        "Quadro MT ubicazione +189L",
    ],
    3: [
        "Protezione differenziale M1 del trasformatore TR1",
        "MORSETTIERA E1 - collegamenti di scatto",
    ],
}

#: A cable schedule.
#:
#: The header row names the columns in Italian and the ratings are bare
#: numbers, as a real schedule writes them - so ``TR1 150`` finds a data
#: row while the unit ``kV`` appears only in the diagram. Two cable tags
#: carry an aspect prefix and one data row repeats ``-Q1``, so the
#: prefixed and bare forms can be told apart across both source
#: families.
CABLE_SCHEDULE: list[list[object]] = [
    ["Sigla", "Partenza", "Arrivo", "Tensione", "Sezione mm2"],
    ["-W1", "TR1", "Q01", 150, 240],
    ["-W2", "TR2", "-Q1", 150, 185],
    ["-W3", "Quadro MT", "MORSETTIERA E1", 20, 95],
]
