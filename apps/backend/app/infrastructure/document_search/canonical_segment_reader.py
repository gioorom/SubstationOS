from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.document_search.search_models import (
    SearchSegment,
    SegmentKind,
    SegmentLocation,
)
from app.domain.document_search.segment_reader import DocumentSegmentReader
from app.models.canonical_pdf import (
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
)
from app.models.document import Document

#: What separates two cells when a row is rendered as one piece of text.
#:
#: Chosen because it reads as a row boundary to a person and is not part
#: of any term to the matcher, so it can never join or split a
#: designation.
CELL_SEPARATOR = " | "


class CellValues(Protocol):
    """
    The cell columns ``_cell_text`` reads.

    A protocol rather than the record type, because what arrives is a
    row of the ``SELECT`` below - not a ``CanonicalCellRecord`` - and
    naming the four columns it must carry is what keeps the query and
    the reader from drifting apart silently.
    """

    literal_text: str | None
    cached_text: str | None
    literal_number: object | None
    cached_number: object | None


class CanonicalSegmentReader(DocumentSegmentReader):
    """
    Reads the canonical PDF and spreadsheet tables as search segments.

    It reads and never writes. The representations are the authority on
    what a document says; this turns them into something findable and
    leaves them exactly as they were.

    When a document has more than one representation - one processed
    twice - the most recently stored is read, because that is the one
    the rest of the system treats as current.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def segments_for(self, document_id: int) -> tuple[SearchSegment, ...]:
        document = self._session.get(Document, document_id)

        if document is None:
            return ()

        return self._pdf_segments(document) + self._workbook_segments(
            document
        )

    # ---- PDF ----------------------------------------------------------

    def _pdf_segments(
        self, document: Document
    ) -> tuple[SearchSegment, ...]:
        """Each line of each page, rebuilt from its verbatim spans."""

        representation = self._session.scalar(
            select(CanonicalPdfRepresentation)
            .where(CanonicalPdfRepresentation.document_id == document.id)
            .order_by(CanonicalPdfRepresentation.id.desc())
            .limit(1)
        )

        if representation is None:
            return ()

        rows = self._session.execute(
            select(
                CanonicalPdfPageRecord.page_number,
                CanonicalPdfBlockRecord.reading_order,
                CanonicalPdfSpanRecord.line_index,
                CanonicalPdfSpanRecord.text,
            )
            .join(
                CanonicalPdfBlockRecord,
                CanonicalPdfBlockRecord.page_id
                == CanonicalPdfPageRecord.id,
            )
            .join(
                CanonicalPdfSpanRecord,
                CanonicalPdfSpanRecord.block_id
                == CanonicalPdfBlockRecord.id,
            )
            .where(
                CanonicalPdfPageRecord.representation_id
                == representation.id
            )
            .order_by(
                CanonicalPdfPageRecord.page_number,
                CanonicalPdfBlockRecord.reading_order,
                CanonicalPdfSpanRecord.line_index,
                CanonicalPdfSpanRecord.reading_order,
            )
        ).all()

        segments: list[SearchSegment] = []
        current: tuple[int, int, int] | None = None
        pieces: list[str] = []

        for page_number, block_order, line_index, text in rows:
            key = (page_number, block_order, line_index)

            if key != current:
                self._close_line(segments, document, current, pieces)
                current, pieces = key, []

            pieces.append(text)

        self._close_line(segments, document, current, pieces)

        return tuple(segments)

    def _close_line(
        self,
        segments: list[SearchSegment],
        document: Document,
        key: tuple[int, int, int] | None,
        pieces: list[str],
    ) -> None:
        """
        Finish one reconstructed line, discarding it if it carries no
        text. A blank line is a layout artefact, not something an
        engineer can search for.
        """

        if key is None:
            return

        text = "".join(pieces)

        if not text.strip():
            return

        page_number, block_order, line_index = key

        segments.append(
            SearchSegment(
                project_id=document.project_id,
                document_id=document.id,
                content_checksum=document.content_checksum,
                kind=SegmentKind.PDF_LINE,
                location=SegmentLocation(
                    page_number=page_number,
                    paragraph_index=block_order,
                    line_index=line_index,
                ),
                text=text,
            )
        )

    # ---- Spreadsheet --------------------------------------------------

    def _workbook_segments(
        self, document: Document
    ) -> tuple[SearchSegment, ...]:
        """
        Each row of each worksheet, rendered as one piece of text.

        **Hidden worksheets are indexed too.** A hidden sheet in a cable
        schedule is usually a working sheet, not a secret one, and its
        rows are as much a part of what the document says as any other.
        A search that silently skipped them would answer "the document
        does not say that" about text the document does say. The hit
        names the sheet, so a reader can see where it came from and
        judge it.
        """

        workbook = self._session.scalar(
            select(CanonicalWorkbookRecord)
            .where(CanonicalWorkbookRecord.document_id == document.id)
            .order_by(CanonicalWorkbookRecord.id.desc())
            .limit(1)
        )

        if workbook is None:
            return ()

        rows = self._session.execute(
            select(
                CanonicalWorksheetRecord.worksheet_index,
                CanonicalWorksheetRecord.name,
                CanonicalRowRecord.row_number,
                CanonicalCellRecord.column_number,
                CanonicalCellRecord.literal_text,
                CanonicalCellRecord.literal_number,
                CanonicalCellRecord.cached_text,
                CanonicalCellRecord.cached_number,
            )
            .join(
                CanonicalRowRecord,
                CanonicalRowRecord.worksheet_id
                == CanonicalWorksheetRecord.id,
            )
            .join(
                CanonicalCellRecord,
                CanonicalCellRecord.row_id == CanonicalRowRecord.id,
            )
            .where(CanonicalWorksheetRecord.workbook_id == workbook.id)
            .order_by(
                CanonicalWorksheetRecord.worksheet_index,
                CanonicalRowRecord.row_number,
                CanonicalCellRecord.column_number,
            )
        ).all()

        segments: list[SearchSegment] = []
        current: tuple[int, str, int] | None = None
        cells: list[tuple[int, str]] = []

        for row in rows:
            key = (row.worksheet_index, row.name, row.row_number)
            value = _cell_text(row)

            if key != current:
                self._close_row(segments, document, current, cells)
                current, cells = key, []

            if value:
                cells.append((row.column_number, value))

        self._close_row(segments, document, current, cells)

        return tuple(segments)

    def _close_row(
        self,
        segments: list[SearchSegment],
        document: Document,
        key: tuple[int, str, int] | None,
        cells: list[tuple[int, str]],
    ) -> None:
        """
        Finish one row, recording where each of its cells begins so a
        hit can later name the cell rather than only the row.

        A row whose cells are all empty is not indexed: it would match
        nothing and would still have to be read past.
        """

        if key is None or not cells:
            return

        worksheet_index, worksheet_name, row_number = key

        pieces: list[str] = []
        offsets: list[tuple[int, int]] = []
        position = 0

        for column_number, value in cells:
            if pieces:
                position += len(CELL_SEPARATOR)

            offsets.append((column_number, position))
            pieces.append(value)
            position += len(value)

        segments.append(
            SearchSegment(
                project_id=document.project_id,
                document_id=document.id,
                content_checksum=document.content_checksum,
                kind=SegmentKind.SPREADSHEET_ROW,
                location=SegmentLocation(
                    worksheet_index=worksheet_index,
                    worksheet_name=worksheet_name,
                    row_number=row_number,
                    cell_offsets=tuple(offsets),
                ),
                text=CELL_SEPARATOR.join(pieces),
            )
        )


def _cell_text(row: CellValues) -> str:
    """
    The searchable text of one cell.

    A cell is indexed by the value it shows: what the engineer typed
    (``literal_*``) or, for a formula, what some application computed
    into the file (``cached_*``). The formula expression itself is not
    indexed - somebody searching ``TR1`` is looking for the transformer,
    not for a cell that happens to reference one.
    """

    for text in (row.literal_text, row.cached_text):
        if text is not None and text.strip():
            return text.strip()

    for number in (row.literal_number, row.cached_number):
        if number is not None:
            return _number_text(number)

    return ""


def _number_text(number: object) -> str:
    """
    A stored number as the text an engineer would recognise.

    ``Numeric(38, 12)`` gives back ``150.000000000000`` for a cell
    showing ``150``, and terms are matched whole - so without trimming,
    nobody searching ``150`` would ever find it.

    A value that is not a ``Decimal`` is rendered as it stands. SQLite
    hands back a ``float`` for this column where other databases hand
    back a ``Decimal``, so this is the ordinary path on one backend and
    a fallback on another.
    """

    if not isinstance(number, Decimal):
        return str(number)

    trimmed = number.normalize()

    if trimmed == trimmed.to_integral_value():
        trimmed = trimmed.quantize(Decimal(1))

    return format(trimmed, "f")
