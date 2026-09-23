"""
What a search indexes, and what it returns.

A **segment** is the smallest piece of a document that is worth showing
an engineer on its own: one line of a drawing's text, or one cell of a
workbook. It is the unit because it is the unit a reader can verify -
a hit that named only the document would leave them to find the words
themselves, and a hit that named a whole page would often be a page of
a table.

Every segment carries where it came from, and every hit carries it
forward unchanged. A result that cannot say which document, which
version of it, and where inside it, is not a search result in this
system - it is a claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SegmentKind(str, Enum):
    """
    Which source family a segment was read from.

    Two families, matching the two canonical representations that exist
    (ADR-0034). The kind decides which location fields are meaningful:
    a line has a page, a row has a worksheet.

    A spreadsheet segment is a **row**, not a cell, because a reading
    an engineer would call one fact is spread across a row: ``TR1`` in
    one column, ``150`` in another, ``kV`` in a third. Cell-sized
    segments would answer "no results" to a query the sheet plainly
    contains. The individual cell is not lost - ``cell_offsets`` records
    where each one starts, so the exact cell behind a match is
    recovered rather than guessed.
    """

    PDF_LINE = "pdf_line"
    SPREADSHEET_ROW = "spreadsheet_row"


@dataclass(frozen=True, slots=True)
class SegmentLocation:
    """
    Where a segment sits in its document.

    Every field is optional because the two families answer different
    questions, and a field that does not apply is absent rather than
    zero. A cell has no page; a line has no column. Absent also means
    *not known*, which is reported as such rather than guessed at - see
    ``search_location.describe``.
    """

    page_number: int | None = None
    paragraph_index: int | None = None
    line_index: int | None = None
    worksheet_index: int | None = None
    worksheet_name: str | None = None
    row_number: int | None = None
    column_number: int | None = None

    cell_offsets: tuple[tuple[int, int], ...] = ()
    """
    For a spreadsheet row, ``(column_number, start_offset)`` for each
    cell that contributed text, in column order.

    This is what lets a hit in a row name the cell it is really in: the
    offset of the match is looked up against these boundaries. Without
    it a row hit could only say "somewhere on row 12", and pointing an
    engineer at a row of forty columns is barely pointing at all.
    """


@dataclass(frozen=True, slots=True)
class SearchSegment:
    """One indexable piece of one document, with its provenance."""

    project_id: int | None
    document_id: int
    content_checksum: str | None
    kind: SegmentKind
    location: SegmentLocation
    text: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    """
    A segment that matched, with the document it belongs to named.

    ``document_filename`` is carried so a result list can be read
    without a second query per row. It is a copy taken at read time, not
    a second source of truth: the document row remains authoritative.
    """

    document_id: int
    document_filename: str
    content_checksum: str | None
    kind: SegmentKind
    location: SegmentLocation
    text: str


@dataclass(frozen=True, slots=True)
class SearchPage:
    """
    One page of matching segments, with the totals behind it.

    The repository returns this rather than a finished outcome: its job
    is to answer *which segments match*, and grouping them under their
    documents is a decision about presentation that belongs above it.

    ``hits`` arrive in a total order fixed by the adapter, so the same
    query returns the same page every time and a document's hits are
    contiguous within it.
    """

    hits: tuple[SearchHit, ...]
    total_segments: int
    total_documents: int


@dataclass(frozen=True, slots=True)
class DocumentMatches:
    """
    Every hit returned for one document, under that document's identity.

    Results are grouped because an engineer looks for a *document*
    first and a position inside it second. Ten lines of one drawing are
    one answer, not ten - and a flat list would bury a second drawing
    that mentioned the identifier once.
    """

    document_id: int
    document_filename: str
    content_checksum: str | None
    kind: SegmentKind
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class TermSuggestion:
    """
    A term that matched nothing, and the designations the project does
    contain that differ from it only by an IEC 81346 aspect prefix.

    This exists so an empty result can be **explained** rather than
    merely reported. It is deliberately not a correction: the variants
    are shown, the search is not silently rerun with them. ``-Q1`` and
    ``Q1`` are different designations, and which one the engineer meant
    is theirs to say.
    """

    term: str
    present_variants: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    """
    What a search found, and what it was asked.

    ``terms`` is returned because a reader is entitled to see what the
    system actually searched for after normalization - if they typed
    ``TR-1`` and the system searched ``tr`` and ``1``, that is
    something they need to see rather than guess at.

    ``total_segments`` counts every matching segment and
    ``total_documents`` every document containing one, so a caller can
    say "12 matches in 3 documents" while showing the first page of
    them.

    ``suggestions`` is populated only when nothing matched.
    """

    terms: tuple[str, ...]
    documents: tuple[DocumentMatches, ...] = ()
    total_segments: int = 0
    total_documents: int = 0
    suggestions: tuple[TermSuggestion, ...] = field(default_factory=tuple)

    @property
    def found_nothing(self) -> bool:
        """True when the search ran and matched no segment at all."""

        return self.total_segments == 0
