"""
The openpyxl adapter behind ``WorkbookReaderPort`` (ADR-0034).

The **only** module in this system that knows what a spreadsheet is made
of, and the only one that imports ``openpyxl``. Everything else - the
domain, the service, the API, every future consumer - deals in canonical
value objects, so replacing this library means rewriting this file and
re-canonicalising, and touching nothing else.

## What it does

Streams each worksheet in read-only mode and records the cells it
observes at the workbook's own 1-based coordinates. It reads the same
in-memory bytes **twice**, each time through a fresh stream and never
re-fetched: once with formulas visible, to record what the file states,
and once with cached values visible, to record what some other
application computed into the file. The two are kept apart in the
record, because a cached value is a claim by whatever last opened the
file and a formula is a claim by the file itself.

The used extent is derived from the cells actually observed. The
declared ``dimension`` element is deliberately not consulted: producers
routinely omit it or get it wrong, and a bound that disagreed with the
content would be wrong in a way nothing downstream could detect.

## Reading untrusted bytes

This is the point in the system where somebody else's compressed archive
is decoded, so the container is inspected with the standard library
before the library ever sees it: entry count, unpacked size per entry
and in total, expansion ratio, hostile entry names, and any document
type or entity declaration - which Office Open XML forbids outright, so
refusing one is a conformance check rather than a heuristic, and it
closes entity expansion as a class.

An encrypted workbook is an OLE2 envelope rather than a container, and
is recognised by its own signature and refused before anything is
unpacked. Every remaining bound is enforced against running counters
*while* streaming, so a hostile file is refused before its memory is
spent rather than after.

Every bound is a property of the file. There is no wall-clock timeout,
because a verdict that depended on how busy the machine was would make a
representation's identity depend on the machine.

## What it does not do

No formula is evaluated. No header row, column name or record is
identified. No cell is sorted, merged, renumbered or repaired, and text
is recorded verbatim - not stripped, not case-folded, not normalised,
not collapsed. Macros in a macro-enabled workbook are never parsed and
never executed; that the file carries them is recorded, and that is all.
No file access of any kind: it receives bytes.

It never raises. Every library failure is mapped onto a typed cause, so
the caller records *why* rather than catching whatever the library chose
to throw this release.

## One honest limitation

A number reaches this adapter already parsed into a Python value, so for
a non-integer the file's own characters are gone before this code runs.
``CellValue.text`` is therefore **this reader's rendering** of the value,
not the file's lexical form. ADR-0034 records that as debt; exact
numeric fidelity would require reading the worksheet markup directly.
"""

from __future__ import annotations

import datetime
import io
import zipfile
import zlib
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

import openpyxl
from openpyxl.cell.read_only import ReadOnlyCell
from openpyxl.utils.datetime import CALENDAR_MAC_1904
from openpyxl.utils.exceptions import (
    InvalidFileException,
    ReadOnlyWorkbookException,
)
from openpyxl.worksheet._read_only import ReadOnlyWorksheet

from app.domain.canonical_spreadsheet import canonical_spreadsheet_factory
from app.domain.canonical_spreadsheet.canonical_spreadsheet_exceptions import (
    InvalidCanonicalWorkbookError,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
    WorkbookCanonicalizationFailureCode,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalCellType,
    CanonicalRow,
    CanonicalWorksheet,
    CellValue,
    UsedRange,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (
    CANONICAL_WORKBOOK_VERSION,
    MAX_CELL_TEXT_LENGTH,
    MAX_COLUMNS_PER_WORKSHEET,
    MAX_COMPRESSED_BYTES,
    MAX_DECOMPRESSION_RATIO,
    MAX_ENTRY_UNCOMPRESSED_BYTES,
    MAX_NUMERIC_INTEGER_DIGITS,
    MAX_POPULATED_CELLS,
    MAX_ROW_NUMBER,
    MAX_ROWS_PER_WORKSHEET,
    MAX_UNCOMPRESSED_BYTES,
    MAX_WORKSHEETS,
    MAX_ZIP_ENTRIES,
)
from app.domain.canonical_spreadsheet.workbook_reader_port import (
    WorkbookReadResult,
    WorkbookReaderPort,
)

READER_NAME = "openpyxl"

#: The OLE2 / Compound File Binary header. An encrypted Office Open XML
#: workbook is not a damaged container: it is an OLE2 envelope with the
#: real container encrypted inside it. Recognising the envelope is what
#: lets this adapter say "locked" instead of "damaged", which are two
#: different conversations with whoever supplied the file.
_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: Container entries that are facts about provenance. Their presence is
#: recorded; their content is never opened.
#: General-purpose bit 0 of a ZIP local header: the member is
#: encrypted. A fact the archive states about itself, so it can be
#: read without attempting extraction and without matching a message.
_ZIP_ENCRYPTED_FLAG = 0x1

_VBA_PROJECT_ENTRY = "xl/vbaProject.bin"
_EXTERNAL_LINK_PREFIX = "xl/externalLinks/"

#: Office Open XML forbids a document type declaration outright, so an
#: entry carrying one is non-conformant by the format's own rules. That
#: makes refusing it a conformance check rather than a guess - and it
#: closes entity expansion, which is the attack a document type
#: declaration is the door to.
_FORBIDDEN_MARKUP = (b"<!DOCTYPE", b"<!ENTITY")
_MARKUP_SUFFIXES = (".xml", ".rels")
_MARKER_OVERLAP = max(len(marker) for marker in _FORBIDDEN_MARKUP) - 1
_SCAN_CHUNK_BYTES = 65_536

_VISIBILITY_BY_STATE: dict[str, WorksheetVisibility] = {
    "visible": WorksheetVisibility.VISIBLE,
    "hidden": WorksheetVisibility.HIDDEN,
    "veryHidden": WorksheetVisibility.VERY_HIDDEN,
}

#: openpyxl's own marker for a cell the file states as a formula.
_FORMULA_DATA_TYPE = "f"
#: openpyxl's own marker for an error the *file* carries.
_ERROR_DATA_TYPE = "e"

#: The closed sets of faults this adapter maps onto a typed cause, split
#: by what each one says about the file. A bare ``Exception`` is never
#: caught: a fault these lists do not name is a fault nobody has
#: understood yet, and swallowing it would turn a bug into a silently
#: unreadable document.
#:
#: A malformed-container fault says the bytes are not a workbook: the
#: archive is damaged, a required part is absent, or a part is not
#: well-formed markup. Each is a defect of the file, and an engineer
#: sent to the supplier rather than to this code.
#:
#: ``SyntaxError`` stands for the markup parse failure rather than a
#: parser's own error class, because both back-ends openpyxl can select
#: derive from it - ``xml.etree.ElementTree.ParseError`` and
#: ``lxml.etree.XMLSyntaxError`` alike - so the mapping stays correct
#: whichever one is installed, without importing either.
#: ``zlib.error`` and ``NotImplementedError`` are the two the archive
#: raises once it is *open* and a member turns out to be unreadable - a
#: corrupt deflate stream and an unsupported compression method. They
#: were missing, and a half-uploaded workbook is the ordinary way to
#: meet the first: the container header is intact, so nothing fails
#: until a member is actually decompressed.
#: ``OSError`` is openpyxl's own signal for "this package has no
#: workbook part" (it raises a bare ``IOError``), which is what an OOXML
#: file that is not a spreadsheet at all looks like - a ``.docx``
#: renamed ``.xlsx`` being the ordinary way to meet it. It is safe to
#: read as a file defect here because this adapter is handed **bytes**
#: and opens nothing: there is no disk, socket or handle in scope that
#: could raise an ``OSError`` meaning anything else.
#: ``IndexError`` is the shared-string table's version of the same
#: thing: a ``t="s"`` cell holds an *index* into `sharedStrings.xml`,
#: resolved as a plain list subscript, so a package whose table is
#: shorter than its cells claim - truncated, or written by a generator
#: that miscounted - fails there. It sits beside ``KeyError`` for the
#: same reason: a part that is present but does not hold what another
#: part says it does.
_MALFORMED_PACKAGE_FAULTS = (
    zipfile.BadZipFile,
    zipfile.LargeZipFile,
    InvalidFileException,
    KeyError,
    IndexError,
    SyntaxError,
    zlib.error,
    NotImplementedError,
    OSError,
)

#: A reader fault says the container opened and the library then failed
#: on bytes it had accepted - the one genuinely unknown cause here, and
#: the only one that should ever prompt "look at the reader".
_READER_FAULTS = (
    ReadOnlyWorkbookException,
    ValueError,
    TypeError,
)


class _UnreadableWorkbook(Exception):
    """
    Adapter-private control flow: a bound was exceeded or the file
    contradicted the format, deep inside a stream, and the read must
    stop with a stated cause.

    Deliberately not a domain error. It never leaves this module - it is
    caught in :meth:`OpenpyxlWorkbookReader.read` and turned into a typed
    result - and making it a domain error would invite a caller to catch
    an adapter's internal signal.
    """

    def __init__(
        self, code: WorkbookCanonicalizationFailureCode, detail: str
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class _ContainerFacts:
    """What inspecting the container established about its provenance."""

    has_vba_project: bool
    has_external_links: bool


@dataclass(frozen=True, slots=True)
class _Observation:
    """One populated cell as the library reported it, before the cached
    value of a formula has been looked up."""

    row_number: int
    column_number: int
    number_format: str | None
    literal: CellValue | None
    expression: str | None


@dataclass(frozen=True, slots=True)
class _ReadGrid:
    """Everything the two reads established about the workbook itself."""

    date_system: WorkbookDateSystem
    worksheets: tuple[CanonicalWorksheet, ...]


class _CellBudget:
    """
    How many populated cells the whole workbook may still yield.

    Spent while streaming rather than checked afterwards, so a hostile
    file is refused before the memory it wanted has been allocated.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._spent = 0

    def spend(self) -> None:
        self._spent += 1

        if self._spent > self._limit:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
                f"The workbook populates more than {self._limit} cells.",
            )


class OpenpyxlWorkbookReader(WorkbookReaderPort):
    """``WorkbookReaderPort`` implemented with openpyxl."""

    @property
    def reader_name(self) -> str:
        return READER_NAME

    @property
    def reader_version(self) -> str:
        return openpyxl.__version__

    def read(
        self,
        content: bytes,
        *,
        document_id: int,
        content_checksum: str,
        checksum_algorithm: str,
    ) -> WorkbookReadResult:
        if not content:
            return _failed(
                WorkbookCanonicalizationFailureCode.EMPTY_CONTENT,
                f"Document '{document_id}' has no bytes to read.",
            )

        if content.startswith(_OLE2_SIGNATURE):
            return _failed(
                WorkbookCanonicalizationFailureCode.ENCRYPTED_WORKBOOK,
                f"Document '{document_id}' is an encrypted workbook; "
                "this system holds no password and must not guess one.",
            )

        if len(content) > MAX_COMPRESSED_BYTES:
            return _failed(
                WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
                f"Document '{document_id}' is {len(content)} bytes, "
                f"beyond the {MAX_COMPRESSED_BYTES} byte bound.",
            )

        try:
            facts = _inspect_container(content)
        except _UnreadableWorkbook as refusal:
            return _failed(refusal.code, refusal.detail)
        except _MALFORMED_PACKAGE_FAULTS as error:
            return _failed(
                WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE,
                f"Document '{document_id}' is not a readable workbook "
                f"container: {error}",
            )
        except _READER_FAULTS as error:
            # The pre-flight streams every member, so it fails the same
            # ways the grid read does. Leaving this off meant a fault
            # raised here escaped the port's no-raise contract entirely.
            return _failed(
                WorkbookCanonicalizationFailureCode.READER_FAILURE,
                f"The reader failed while inspecting document "
                f"'{document_id}': {error}",
            )

        try:
            grid = _read_grid(content)
        except _UnreadableWorkbook as refusal:
            return _failed(refusal.code, refusal.detail)
        except InvalidCanonicalWorkbookError as error:
            # The library produced something the model refuses. Recorded
            # as a reader failure rather than silently corrected: a
            # representation quietly repaired into shape would be
            # trusted by every future consumer.
            return _failed(
                WorkbookCanonicalizationFailureCode.READER_FAILURE,
                f"The reader produced an invalid representation of "
                f"document '{document_id}': {error.detail}",
            )
        except _MALFORMED_PACKAGE_FAULTS as error:
            return _failed(
                WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE,
                f"Document '{document_id}' is not a readable workbook "
                f"container: {error}",
            )
        except _READER_FAULTS as error:
            return _failed(
                WorkbookCanonicalizationFailureCode.READER_FAILURE,
                f"The reader failed while reading document "
                f"'{document_id}': {error}",
            )

        if not grid.worksheets:
            return _failed(
                WorkbookCanonicalizationFailureCode.EMPTY_WORKBOOK,
                f"Document '{document_id}' is a valid container "
                "carrying no worksheet.",
            )

        try:
            workbook = canonical_spreadsheet_factory.build_workbook(
                document_id=document_id,
                content_checksum=content_checksum,
                checksum_algorithm=checksum_algorithm,
                representation_version=CANONICAL_WORKBOOK_VERSION,
                reader_name=READER_NAME,
                reader_version=self.reader_version,
                date_system=grid.date_system,
                has_vba_project=facts.has_vba_project,
                has_external_links=facts.has_external_links,
                worksheets=grid.worksheets,
            )
        except InvalidCanonicalWorkbookError as error:
            return _failed(
                WorkbookCanonicalizationFailureCode.READER_FAILURE,
                f"The reader produced an invalid representation of "
                f"document '{document_id}': {error.detail}",
            )

        if not workbook.has_populated_cell:
            return _failed(
                WorkbookCanonicalizationFailureCode.NO_POPULATED_CELL,
                f"Document '{document_id}' has worksheets and not one "
                "populated cell anywhere.",
            )

        return WorkbookReadResult(workbook=workbook)


# --- Inspecting the container before the library sees it -------------


def _inspect_container(content: bytes) -> _ContainerFacts:
    """
    Walk the archive with the standard library alone, enforcing every
    bound the policy states, and report what its entry names say about
    the workbook's provenance.

    Declared sizes are checked first because they are free, and then
    ignored: the entries are streamed and their **actual** unpacked
    bytes counted, because a declared size is a number in the archive's
    own index and a hostile archive controls it.
    """

    with zipfile.ZipFile(io.BytesIO(content)) as container:
        entries = container.infolist()

        if len(entries) > MAX_ZIP_ENTRIES:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.DECOMPRESSION_LIMIT_EXCEEDED,
                f"The container holds {len(entries)} entries, beyond "
                f"the {MAX_ZIP_ENTRIES} entry bound.",
            )

        _require_declared_size_within_bounds(entries, len(content))

        unpacked = 0

        for entry in entries:
            _require_safe_entry_name(entry.filename)
            _require_unencrypted_entry(entry)
            unpacked += _scan_entry(
                container, entry, remaining=MAX_UNCOMPRESSED_BYTES - unpacked
            )
            _require_ratio_within_bounds(unpacked, len(content))

        names = frozenset(container.namelist())

    return _ContainerFacts(
        has_vba_project=_VBA_PROJECT_ENTRY in names,
        has_external_links=any(
            name.startswith(_EXTERNAL_LINK_PREFIX) for name in names
        ),
    )


def _require_unencrypted_entry(entry: zipfile.ZipInfo) -> None:
    """
    Refuse a member the archive itself declares encrypted.

    This is the ZIP container's own password protection, which is a
    different thing from the agile encryption Excel writes - that one
    produces an OLE2 file and is caught by its signature before the
    archive is opened at all. Both mean the same thing to a reader with
    no password, so both answer ``ENCRYPTED_WORKBOOK``.

    Read from general-purpose bit 0 rather than from the exception the
    archive would raise on extraction, because the bit is a fact the
    file states and the exception is a message that could be reworded.
    """

    if entry.flag_bits & _ZIP_ENCRYPTED_FLAG:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.ENCRYPTED_WORKBOOK,
            f"The container entry '{entry.filename}' is password "
            f"protected. No password is held and none is guessed.",
        )


def _require_declared_size_within_bounds(
    entries: list[zipfile.ZipInfo], compressed_bytes: int
) -> None:
    declared = 0

    for entry in entries:
        if entry.file_size > MAX_ENTRY_UNCOMPRESSED_BYTES:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.DECOMPRESSION_LIMIT_EXCEEDED,
                f"Container entry '{entry.filename}' declares "
                f"{entry.file_size} unpacked bytes, beyond the "
                f"{MAX_ENTRY_UNCOMPRESSED_BYTES} byte bound.",
            )

        declared += entry.file_size

    if declared > MAX_UNCOMPRESSED_BYTES:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.DECOMPRESSION_LIMIT_EXCEEDED,
            f"The container declares {declared} unpacked bytes, beyond "
            f"the {MAX_UNCOMPRESSED_BYTES} byte bound.",
        )

    _require_ratio_within_bounds(declared, compressed_bytes)


def _require_ratio_within_bounds(
    unpacked_bytes: int, compressed_bytes: int
) -> None:
    if unpacked_bytes > compressed_bytes * MAX_DECOMPRESSION_RATIO:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.DECOMPRESSION_LIMIT_EXCEEDED,
            f"The container unpacks {unpacked_bytes} bytes from "
            f"{compressed_bytes}, beyond the "
            f"{MAX_DECOMPRESSION_RATIO}:1 bound.",
        )


def _require_safe_entry_name(name: str) -> None:
    """
    An entry name is a name inside the archive, never a path on this
    machine. Nothing here writes a file, so this is not a fix for a
    traversal bug; it is a refusal to read an archive that is not what
    it claims to be, at the point where that is still cheap.
    """

    unsafe = (
        not name
        or name.startswith("/")
        or name[1:2] == ":"
        or "\\" in name
        or "\x00" in name
        or ".." in name.split("/")
    )

    if unsafe:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE,
            f"Container entry name {name!r} is not a conformant "
            "relative name.",
        )


def _scan_entry(
    container: zipfile.ZipFile, entry: zipfile.ZipInfo, *, remaining: int
) -> int:
    """
    Stream one entry, count what it actually unpacks to, and refuse a
    markup entry that declares a document type or an entity.

    The chunk boundary is overlapped so a declaration split across two
    reads is still seen; a scan that could be evaded by inserting one
    byte would be theatre.
    """

    is_markup = entry.filename.endswith(_MARKUP_SUFFIXES)
    unpacked = 0
    tail = b""

    with container.open(entry) as stream:
        while True:
            chunk = stream.read(_SCAN_CHUNK_BYTES)

            if not chunk:
                return unpacked

            unpacked += len(chunk)

            if (
                unpacked > MAX_ENTRY_UNCOMPRESSED_BYTES
                or unpacked > remaining
            ):
                raise _UnreadableWorkbook(
                    WorkbookCanonicalizationFailureCode.DECOMPRESSION_LIMIT_EXCEEDED,
                    f"Container entry '{entry.filename}' unpacks to "
                    "more than it declared, beyond the stated bounds.",
                )

            if is_markup:
                _require_no_document_type(tail + chunk, entry.filename)
                tail = chunk[-_MARKER_OVERLAP:]


def _require_no_document_type(data: bytes, name: str) -> None:
    for marker in _FORBIDDEN_MARKUP:
        if marker in data:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE,
                f"Container entry '{name}' carries a "
                f"{marker.decode('ascii')} declaration, which Office "
                "Open XML forbids.",
            )


# --- Reading the grid -------------------------------------------------


def _read_grid(content: bytes) -> _ReadGrid:
    """
    Two reads over the same bytes, each through its own fresh stream and
    neither re-fetched from anywhere.

    The first sees formulas as the file states them; the second sees the
    values another application cached for them. One read cannot show
    both, and choosing one would silently discard whichever the caller
    happened not to get.
    """

    stated = _load(content, data_only=False)

    try:
        cached = _load(content, data_only=True)

        try:
            return _ReadGrid(
                date_system=_date_system(stated),
                worksheets=_read_worksheets(stated, cached),
            )
        finally:
            cached.close()
    finally:
        stated.close()


def _load(content: bytes, *, data_only: bool) -> openpyxl.Workbook:
    return openpyxl.load_workbook(
        io.BytesIO(content),
        read_only=True,
        data_only=data_only,
        keep_links=False,
        keep_vba=False,
    )


def _date_system(workbook: openpyxl.Workbook) -> WorkbookDateSystem:
    if workbook.epoch == CALENDAR_MAC_1904:
        return WorkbookDateSystem.EPOCH_1904

    return WorkbookDateSystem.EPOCH_1900


def _read_worksheets(
    stated: openpyxl.Workbook, cached: openpyxl.Workbook
) -> tuple[CanonicalWorksheet, ...]:
    if len(stated.worksheets) > MAX_WORKSHEETS:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
            f"The workbook holds {len(stated.worksheets)} worksheets, "
            f"beyond the {MAX_WORKSHEETS} worksheet bound.",
        )

    if len(stated.worksheets) != len(cached.worksheets):
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.READER_FAILURE,
            "The two reads of the same bytes disagree about how many "
            "worksheets the workbook has.",
        )

    budget = _CellBudget(MAX_POPULATED_CELLS)

    return tuple(
        _read_worksheet(
            worksheet_index=index,
            stated_worksheet=stated.worksheets[index],
            cached_worksheet=cached.worksheets[index],
            budget=budget,
        )
        for index in range(len(stated.worksheets))
    )


def _read_worksheet(
    *,
    worksheet_index: int,
    stated_worksheet: ReadOnlyWorksheet,
    cached_worksheet: ReadOnlyWorksheet,
    budget: _CellBudget,
) -> CanonicalWorksheet:
    observations = _observe(stated_worksheet, budget)
    cached_results = _cached_results(
        cached_worksheet, _formula_coordinates(observations)
    )
    rows = _build_rows(observations, cached_results)

    return canonical_spreadsheet_factory.build_worksheet(
        worksheet_index=worksheet_index,
        name=stated_worksheet.title,
        visibility=_visibility(stated_worksheet.sheet_state),
        rows=rows,
        used_range=_used_range(rows),
    )


def _visibility(sheet_state: str) -> WorksheetVisibility:
    """
    Hidden and very-hidden worksheets are read in full. A cable register
    left on a hidden worksheet is still what the document contains, and
    skipping it would be this system deciding which parts of a delivered
    document count.
    """

    if sheet_state not in _VISIBILITY_BY_STATE:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE,
            f"Worksheet visibility {sheet_state!r} is not one Office "
            "Open XML defines.",
        )

    return _VISIBILITY_BY_STATE[sheet_state]


def _observe(
    worksheet: ReadOnlyWorksheet, budget: _CellBudget
) -> tuple[_Observation, ...]:
    """
    Stream one worksheet, recording only the cells that carry something.

    The declared extent is discarded first, so what is recorded is what
    was seen rather than what the file claimed. Rows that materialise
    nothing are skipped entirely, which is what keeps a sparse register
    sparse and its gaps visible.
    """

    _discard_declared_extent(worksheet)

    observations: list[_Observation] = []
    rows_observed = 0
    rows_scanned = 0

    for raw_row in worksheet.rows:
        # **Counted before the row is looked at**, and separately from
        # ``rows_observed`` below, because these two count different
        # things and only this one bounds the walk.
        #
        # A file that declares one populated row at an enormous
        # coordinate makes the library materialise every index beneath
        # it - each yielded as an empty row that ``rows_observed`` then
        # correctly declines to count. The work is done regardless, so
        # without this the *file* decides how long a read takes, and a
        # five-kilobyte upload can cost minutes of CPU. The coordinate
        # is parsed as an unbounded integer, so there is no natural
        # ceiling to reach.
        rows_scanned += 1

        if rows_scanned > MAX_ROW_NUMBER:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
                f"A worksheet spans more than {MAX_ROW_NUMBER} row "
                "indices, beyond the format's own grid.",
            )

        populated = tuple(
            cell for cell in raw_row if cell.value is not None
        )

        if not populated:
            continue

        rows_observed += 1

        if rows_observed > MAX_ROWS_PER_WORKSHEET:
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
                f"A worksheet populates more than "
                f"{MAX_ROWS_PER_WORKSHEET} rows.",
            )

        for cell in populated:
            _require_column_within_bounds(cell.column)
            budget.spend()
            observations.append(_observe_cell(cell))

    return tuple(observations)


def _discard_declared_extent(worksheet: ReadOnlyWorksheet) -> None:
    """The file's declared extent is routinely absent or wrong, so it is
    thrown away and the real one derived from the cells observed."""

    reset = getattr(worksheet, "reset_dimensions", None)

    if reset is not None:
        reset()


def _require_column_within_bounds(column_number: int) -> None:
    if column_number > MAX_COLUMNS_PER_WORKSHEET:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
            f"A worksheet reaches column {column_number}, beyond the "
            f"{MAX_COLUMNS_PER_WORKSHEET} column bound.",
        )


def _observe_cell(cell: ReadOnlyCell) -> _Observation:
    if cell.data_type == _FORMULA_DATA_TYPE:
        return _Observation(
            row_number=cell.row,
            column_number=cell.column,
            number_format=cell.number_format,
            literal=None,
            expression=_expression(cell),
        )

    return _Observation(
        row_number=cell.row,
        column_number=cell.column,
        number_format=cell.number_format,
        literal=_value(cell),
        expression=None,
    )


def _expression(cell: ReadOnlyCell) -> str:
    """
    The formula text the file states, for an ordinary formula and for
    the leading cell of an array formula alike.

    A cell the library reports as a formula for which the file states no
    text at all - a data-table cell - has no honest place in this model:
    it carries a computed value and no expression, and the model requires
    a literal or a formula with an expression. Recording it as a literal
    would present a computed value as one an engineer typed, and
    recording an empty expression would say the file states a formula it
    does not. Refused instead, and named, so it is reviewed rather than
    silently mis-recorded.
    """

    value = cell.value
    text = value if isinstance(value, str) else getattr(value, "text", None)

    if not isinstance(text, str) or not text.strip():
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.READER_FAILURE,
            f"Cell row {cell.row}, column {cell.column} is reported as "
            "a formula for which the file states no expression.",
        )

    _require_text_within_bounds(text)

    return text


def _value(cell: ReadOnlyCell) -> CellValue:
    """
    One literal, typed by what the library actually handed over rather
    than by what the cell's format suggests.

    A cell whose format says "date" but whose serial is outside the
    representable range never reaches here as a date: openpyxl itself
    substitutes the error ``#VALUE!`` for it, and that is recorded as the
    error it now is - never as an invented date, and never as a reason to
    refuse the whole workbook. A serial that arrives as a plain number
    despite a date format is likewise recorded as the number it is.
    """

    value = cell.value

    if cell.data_type == _ERROR_DATA_TYPE:
        return _typed(
            CanonicalCellType.ERROR, str(value), error_code=str(value)
        )

    if isinstance(value, bool):
        return _typed(
            CanonicalCellType.BOOLEAN,
            "TRUE" if value else "FALSE",
            boolean=value,
        )

    if isinstance(value, (datetime.datetime, datetime.date)):
        return _typed(
            CanonicalCellType.DATE_TIME,
            value.isoformat(),
            instant=value.isoformat(),
        )

    if isinstance(value, datetime.time):
        return _typed(
            CanonicalCellType.TIME,
            value.isoformat(),
            instant=value.isoformat(),
        )

    if isinstance(value, datetime.timedelta):
        return _typed(
            CanonicalCellType.DURATION,
            _iso_duration(value),
            duration=_iso_duration(value),
        )

    if isinstance(value, (int, float, Decimal)):
        number = Decimal(repr(value))

        if not number.is_finite() or (
            number.adjusted() >= MAX_NUMERIC_INTEGER_DIGITS
        ):
            # `<v>1e999</v>` parses to a double that is simply
            # `inf`. Refused here, with the cell named, rather than
            # recorded: an infinity cannot be stored and read back, and
            # substituting a finite stand-in or an error code would put
            # a number in the register that the file never stated.
            raise _UnreadableWorkbook(
                WorkbookCanonicalizationFailureCode
                .UNREPRESENTABLE_NUMBER,
                f"Cell row {cell.row}, column {cell.column} states a "
                "magnitude no recorded number can hold "
                f"({value!r}).",
            )

        return _typed(
            CanonicalCellType.NUMBER, repr(value), number=number
        )

    if isinstance(value, str):
        return _typed(CanonicalCellType.TEXT, value)

    raise _UnreadableWorkbook(
        WorkbookCanonicalizationFailureCode.READER_FAILURE,
        f"Cell row {cell.row}, column {cell.column} holds a "
        f"{type(value).__name__}, which this reader cannot record "
        "without inventing a rendering for it.",
    )


def _typed(
    value_type: CanonicalCellType,
    text: str,
    *,
    number: Decimal | None = None,
    boolean: bool | None = None,
    instant: str | None = None,
    duration: str | None = None,
    error_code: str | None = None,
) -> CellValue:
    _require_text_within_bounds(text)

    return canonical_spreadsheet_factory.build_cell_value(
        value_type=value_type,
        text=text,
        number=number,
        boolean=boolean,
        instant=instant,
        duration=duration,
        error_code=error_code,
    )


def _require_text_within_bounds(text: str) -> None:
    if len(text) > MAX_CELL_TEXT_LENGTH:
        raise _UnreadableWorkbook(
            WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
            f"A cell carries {len(text)} characters, beyond the "
            f"{MAX_CELL_TEXT_LENGTH} character bound the format itself "
            "states.",
        )


def _iso_duration(value: datetime.timedelta) -> str:
    """An elapsed time as ISO-8601, so a duration cell is recorded as a
    duration rather than as an instant the workbook never named."""

    sign = "-" if value < datetime.timedelta(0) else ""
    magnitude = abs(value)
    hours, remainder = divmod(magnitude.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days = f"{magnitude.days}D" if magnitude.days else ""
    fraction = (
        f".{magnitude.microseconds:06d}".rstrip("0")
        if magnitude.microseconds
        else ""
    )

    return f"{sign}P{days}T{hours}H{minutes}M{seconds}{fraction}S"


def _formula_coordinates(
    observations: tuple[_Observation, ...]
) -> frozenset[tuple[int, int]]:
    return frozenset(
        (observation.row_number, observation.column_number)
        for observation in observations
        if observation.expression is not None
    )


def _cached_results(
    worksheet: ReadOnlyWorksheet,
    coordinates: frozenset[tuple[int, int]],
) -> dict[tuple[int, int], CellValue]:
    """
    The values another application computed into the file, for the
    formula cells only.

    Restricted to those coordinates on purpose: every other cell's value
    is already recorded as a literal from the first read, and holding a
    second copy of a large register to no end would spend memory this
    adapter has just promised to bound.
    """

    if not coordinates:
        return {}

    _discard_declared_extent(worksheet)
    results: dict[tuple[int, int], CellValue] = {}

    for raw_row in worksheet.rows:
        for cell in raw_row:
            if cell.value is None:
                continue

            coordinate = (cell.row, cell.column)

            if coordinate in coordinates:
                results[coordinate] = _value(cell)

    return results


def _build_rows(
    observations: tuple[_Observation, ...],
    cached_results: dict[tuple[int, int], CellValue],
) -> tuple[CanonicalRow, ...]:
    """Observations arrive in the worksheet's own order, so consecutive
    ones share a row: grouping them needs no sort, and doing one would
    hide a reader that had lost the file's order."""

    return tuple(
        canonical_spreadsheet_factory.build_row(
            row_number=row_number,
            cells=tuple(
                _cell(observation, cached_results)
                for observation in group
            ),
        )
        for row_number, group in groupby(
            observations, key=lambda observation: observation.row_number
        )
    )


def _cell(
    observation: _Observation,
    cached_results: dict[tuple[int, int], CellValue],
) -> CanonicalCell:
    formula = None

    if observation.expression is not None:
        formula = canonical_spreadsheet_factory.build_formula(
            expression=observation.expression,
            cached_result=cached_results.get(
                (observation.row_number, observation.column_number)
            ),
        )

    return canonical_spreadsheet_factory.build_cell(
        row_number=observation.row_number,
        column_number=observation.column_number,
        number_format=observation.number_format,
        literal=observation.literal,
        formula=formula,
    )


def _used_range(rows: tuple[CanonicalRow, ...]) -> UsedRange | None:
    if not rows:
        return None

    columns = tuple(
        cell.column_number for row in rows for cell in row.cells
    )

    return canonical_spreadsheet_factory.build_used_range(
        first_row=rows[0].row_number,
        last_row=rows[-1].row_number,
        first_column=min(columns),
        last_column=max(columns),
    )


def _failed(
    code: WorkbookCanonicalizationFailureCode, detail: str
) -> WorkbookReadResult:
    return WorkbookReadResult(failure_code=code, detail=detail)
