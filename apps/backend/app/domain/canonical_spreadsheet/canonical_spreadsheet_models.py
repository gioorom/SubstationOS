"""
The canonical representation of a spreadsheet workbook (ADR-0034).

A workbook is a **second source family**, forking the derivation chain at
the bytes themselves. It borrows nothing from the PDF lineage, and the
PDF lineage borrows nothing from it: a worksheet is not a printed sheet
of paper, a row is not a line of ink, and a cell has coordinates rather
than a rectangle. Naming them as if they were the same thing would push
an invented geometry into every consumer downstream.

## The hierarchy

```
CanonicalWorkbook        one workbook, at one content checksum
  └─ CanonicalWorksheet  one worksheet, at its ordinal position, by name
       └─ CanonicalRow   one row, by its 1-based row number
            └─ CanonicalCell   one cell, by its 1-based column number
```

## What this representation is not

It records **what the reader observed**, never what the register
"probably means". There is deliberately nowhere in this hierarchy to put:

- a header row, a column name, a field name, or a record - deciding that
  row 1, or row 7 after a title, names the columns is an inference, and
  this context reads nothing that could check it;
- a computed formula result - a value this platform calculated would be
  indistinguishable in the record from the value an engineer's
  spreadsheet calculated;
- a merged range or a hidden-row flag - the reader streams, and a
  streaming reader does not report them. Defaulting such a field to
  "none" would assert something no reader ever said;
- an equipment tag, a cable, a circuit, or any reading of what the grid
  denotes.

## Absence is the record

A cell with neither a value nor a formula is **not materialised**. A
workbook declares a grid of 1,048,576 by 16,384 cells and almost all of
it is nothing; nothing is not an observation. Sparse rows keep the
workbook's own 1-based numbers, so a gap stays visible and addressable
and is never re-indexed.

Every level is immutable, so a representation cannot be edited after the
fact - only rebuilt from bytes, which is the only thing that could
legitimately change it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

_ALPHABET_SIZE = 26
_FIRST_LETTER = "A"


def column_label_of(column_number: int) -> str:
    """
    The workbook's own column label for a 1-based column number:
    1 -> ``"A"``, 26 -> ``"Z"``, 27 -> ``"AA"``.

    Bijective base-26, which is what a spreadsheet uses and what an
    engineer will type into a cell reference. Ordinary base-26 would
    produce ``"@A"`` for column 27, and a locator an engineer cannot
    paste back into the source file is not a locator.
    """

    label = ""
    remaining = column_number

    while remaining > 0:
        remaining, offset = divmod(remaining - 1, _ALPHABET_SIZE)
        label = chr(ord(_FIRST_LETTER) + offset) + label

    return label


class CanonicalCellType(str, Enum):
    """
    What kind of value the reader observed in a cell.

    There is deliberately **no blank member**. A blank cell is not
    materialised at all, so a type meaning "nothing here" would be
    unreachable by construction - and, worse, would give a future writer
    somewhere to record a cell it could not read.
    """

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE_TIME = "date_time"
    TIME = "time"
    DURATION = "duration"
    #: An error the *file* carries - ``#DIV/0!``, ``#REF!``. It is a
    #: value the workbook genuinely holds, not a failure of this system
    #: to read the cell, and dropping it would make a broken register
    #: look complete.
    ERROR = "error"


class WorksheetVisibility(str, Enum):
    """
    Whether the workbook presents a worksheet to its user.

    Hidden and very-hidden worksheets are read in full. A cable register
    left on a hidden worksheet is still what the document contains, and
    refusing to read it would be this system deciding which parts of a
    delivered document count.
    """

    VISIBLE = "visible"
    HIDDEN = "hidden"
    VERY_HIDDEN = "very_hidden"


class WorkbookDateSystem(str, Enum):
    """
    Which epoch the workbook's serial dates are counted from.

    Recorded because it is the setting that decides what a serial number
    means. Two workbooks holding the identical serial denote dates four
    years apart under the two systems, and a representation that did not
    say which one applied could not explain its own dates later.
    """

    EPOCH_1900 = "epoch_1900"
    EPOCH_1904 = "epoch_1904"


@dataclass(frozen=True, slots=True)
class CellValue:
    """
    One value, as the reader rendered it, with the typed slot for its
    kind filled and every other slot empty.

    ``text`` is always present and is **the reader's rendering**, not the
    file's own characters. For a non-integer number the reader has
    already parsed the lexical form before this system sees it, so the
    file's digits are gone by then; ADR-0034 records that as debt rather
    than pretending otherwise. For text the value is verbatim: not
    stripped, not case-folded, not normalised, not collapsed.

    The typed slots exist so a consumer never has to re-parse ``text``. A
    consumer that did would be re-deriving, under its own rules, a
    reading this stage already performed once and recorded.
    """

    value_type: CanonicalCellType
    text: str
    number: Decimal | None = None
    boolean: bool | None = None
    #: ISO-8601, naive. A workbook records a wall-clock reading with no
    #: zone; attaching one would be an invented fact about where the
    #: substation is.
    instant: str | None = None
    #: ISO-8601 duration, for an elapsed-time cell.
    duration: str | None = None
    #: The error the file carries, verbatim (``#DIV/0!``).
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalCellFormula:
    """
    A formula the file states, and separately the value some other
    application cached into the file for it.

    **Nothing here is evaluated.** Evaluation depends on a calculation
    chain, a date system and an iteration setting, and a value this
    platform computed would be indistinguishable in the record from the
    value the engineer's spreadsheet computed.

    ``cached_result is None`` says exactly one thing: no application has
    ever written a computed value into this file for this cell - the
    normal state of a workbook produced by a script and never opened. It
    is emphatically **not** a blank cell, an empty string, a zero, or a
    read failure. Those four are lies of different sizes, and the last
    three would be indistinguishable downstream from a register that
    genuinely says nothing there.
    """

    expression: str
    cached_result: CellValue | None = None

    @property
    def has_cached_result(self) -> bool:
        return self.cached_result is not None


@dataclass(frozen=True, slots=True)
class CanonicalCell:
    """
    One cell at its own 1-based coordinates, carrying **either** a
    literal **or** a formula, never both.

    There is deliberately no ``value`` property returning
    literal-or-cached. Such a property would let every consumer forget,
    silently and by default, whether it was looking at what the engineer
    typed or at what some other application computed - which is the one
    distinction this context exists to keep.

    ``number_format`` is the display format string the file states. It is
    recorded because it is the only thing that distinguishes a serial
    date from a plain number in the source, not so that anything renders
    from it.
    """

    row_number: int
    column_number: int
    number_format: str | None = None
    literal: CellValue | None = None
    formula: CanonicalCellFormula | None = None

    @property
    def column_label(self) -> str:
        return column_label_of(self.column_number)

    @property
    def a1_reference(self) -> str:
        """The cell's address as the workbook itself writes it, so a
        recorded observation can be pasted straight back into the source
        file and checked."""

        return f"{self.column_label}{self.row_number}"


@dataclass(frozen=True, slots=True)
class CanonicalRow:
    """
    One row, by the workbook's own 1-based number.

    A materialised row always carries at least one cell: a row of
    nothing is nothing, and recording it would put a row that the reader
    never observed into the record. The numbers are the file's, so a gap
    between row 12 and row 40 is a fact about the register and stays
    visible as one.
    """

    row_number: int
    cells: tuple[CanonicalCell, ...] = ()


@dataclass(frozen=True, slots=True)
class UsedRange:
    """
    The rectangle the observed cells actually occupy.

    Derived from the cells this reader saw, **never** from the file's
    declared ``dimension`` element, which producers routinely omit or
    get wrong. A declared extent that disagrees with the content would
    make every downstream bound wrong in a way nothing could detect.
    """

    first_row: int
    last_row: int
    first_column: int
    last_column: int


@dataclass(frozen=True, slots=True)
class CanonicalWorksheet:
    """
    One worksheet at its ordinal position in the workbook, under its own
    name.

    ``worksheet_index`` is 0-based because it is a position in the
    workbook's own ordering, not something an engineer cites; row and
    column numbers are 1-based because those are exactly what the
    workbook shows and what a cell reference uses. Mixing the two bases
    is deliberate: each matches the thing it addresses.

    ``used_range`` is ``None`` when nothing was observed. An empty
    worksheet with a rectangle would be claiming an extent for a sheet
    that has none.
    """

    worksheet_index: int
    name: str
    visibility: WorksheetVisibility
    rows: tuple[CanonicalRow, ...] = ()
    used_range: UsedRange | None = None

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def row(self, row_number: int) -> CanonicalRow | None:
        """
        One row by its 1-based number, or ``None`` when the worksheet
        materialised no such row.

        A lookup, never a search: rows are sparse by design, so indexing
        into the tuple would silently return a neighbouring row.
        """

        for row in self.rows:
            if row.row_number == row_number:
                return row

        return None


@dataclass(frozen=True, slots=True)
class CanonicalWorkbook:
    """
    The whole representation of one workbook at one specific content
    checksum.

    ``content_checksum`` binds this representation to the exact bytes it
    was built from. If a document's bytes change, the new checksum makes
    the new representation a *different* value rather than an overwrite
    of the old one, and a conclusion drawn last year stays explainable:
    it says which bytes, which reader, which version.

    ``reader_name``/``reader_version``/``representation_version`` are
    recorded for the same reason, and are inputs to this artifact's
    identity: a library upgrade that silently reused the old
    representation would carry a stale reading through every stage below.

    Deliberately **no timestamp**: the value is a function of the bytes
    and the reader, and two runs over identical bytes must compare equal.
    When it was built is a fact about the row, not about the
    representation.
    """

    document_id: int
    content_checksum: str
    checksum_algorithm: str
    representation_version: str
    reader_name: str
    reader_version: str
    date_system: WorkbookDateSystem
    #: Whether the workbook carries macros, and whether it points at
    #: other workbooks. Both are observations about provenance, not
    #: capabilities: no macro is ever parsed or executed, and no linked
    #: workbook is ever followed. A register whose values come from a
    #: file this system has never seen is a register to be read with
    #: care, and that has to be visible.
    has_vba_project: bool
    has_external_links: bool
    worksheets: tuple[CanonicalWorksheet, ...] = ()

    #: This artifact's deterministic identity, and the identity of the
    #: artifact it was derived from. ``None`` only for a row stored
    #: before the identity chain existed: unknown is not a value, and an
    #: artifact that cannot say what it was derived from can never prove
    #: a reuse is valid. See ``app/domain/artifact_identity``.
    artifact_identity: str | None = None
    upstream_identity: str | None = None

    @property
    def worksheet_count(self) -> int:
        return len(self.worksheets)

    @property
    def is_empty(self) -> bool:
        """No worksheets at all - a file that carries no grid."""

        return not self.worksheets

    @property
    def has_populated_cell(self) -> bool:
        """
        Whether any worksheet materialised a single cell.

        ``False`` says exactly one thing: nothing was observed anywhere.
        It does not say the workbook is a template, a macro container or
        a stub - those are conclusions, and this context reads nothing
        that could support them.
        """

        return any(row.cells for sheet in self.worksheets for row in sheet.rows)

    def worksheet(self, worksheet_index: int) -> CanonicalWorksheet | None:
        """
        One worksheet by its 0-based position, or ``None`` when the
        representation has no such worksheet.
        """

        for sheet in self.worksheets:
            if sheet.worksheet_index == worksheet_index:
                return sheet

        return None


@dataclass(frozen=True, slots=True)
class CellReference:
    """
    Where in a workbook something was observed.

    The worksheet's **name as well as its position**: an engineer looking
    for "Cable Schedule" needs the name, and a later revision of the same
    register can move that worksheet, at which point the position alone
    would silently point somewhere else. Both are recorded because
    neither alone survives a revision honestly.
    """

    worksheet_index: int
    worksheet_name: str
    row_number: int
    column_number: int

    @property
    def column_label(self) -> str:
        return column_label_of(self.column_number)

    @property
    def a1_reference(self) -> str:
        return f"{self.column_label}{self.row_number}"
