"""
Synthetic workbooks, built in memory rather than stored as files.

Every workbook here is fabricated. None of it is derived from, adapted
from, or transcribed out of a real engineering document: the designations,
panel names and cable codes are invented to be *shaped* like the real
thing without being any part of it.

They are built rather than committed for two reasons. The repository's
source-data firewall refuses ``*.xlsx`` anywhere in the tree as defence in
depth, and a fixture that has to be exempted from that rule weakens the
rule for every future reader. And a workbook expressed as code can be read
in review: what a binary fixture contains is whatever someone once saved,
which nobody checks again.

The builders return raw bytes, because that is what
``WorkbookReaderPort.read`` accepts - the port takes content, never a path,
so a test exercises the same entry point the application does.
"""

from __future__ import annotations

import datetime
import io

from openpyxl import Workbook


def _to_bytes(workbook: Workbook) -> bytes:
    """Serialise a workbook to the bytes a reader would receive."""

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def simple_register() -> bytes:
    """
    Fixture A - one sheet, a header-shaped first row, three data rows.

    The first row *looks* like a header. Nothing in this milestone treats
    it as one, and a test asserts that: the row is four cells of text at
    row 1, no more privileged than row 2.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Register"
    sheet.append(["Cable ID", "From", "To", "Function"])
    sheet.append(["CBL-001", "PANEL-A", "PANEL-B", "Control"])
    sheet.append(["CBL-002", "PANEL-B", "PANEL-C", "Power"])
    sheet.append(["CBL-003", "PANEL-A", "PANEL-C", "Control"])
    return _to_bytes(workbook)


def multiple_sheets() -> bytes:
    """
    Fixture B - two sheets whose structures differ, plus a hidden third.

    The hidden sheet carries a populated cell on purpose. A register left
    on a hidden tab is still what the document contains, so the reader
    records it and flags the visibility rather than skipping it.
    """

    workbook = Workbook()
    first = workbook.active
    first.title = "Cables"
    first.append(["Cable ID", "Formation"])
    first.append(["CBL-010", "4x2.5"])

    second = workbook.create_sheet("Equipment")
    second.append(["Tag", "Rating", "Unit"])
    second.append(["QA1", 630, "A"])
    second.append(["TR1", 25, "MVA"])

    hidden = workbook.create_sheet("Superseded")
    hidden["A1"] = "CBL-099"
    hidden.sheet_state = "hidden"
    return _to_bytes(workbook)


def header_offset() -> bytes:
    """
    Fixture C - a title block above the header-shaped row.

    This is the fixture that makes "row 1 is the header" indefensible:
    row 1 is a document title, row 2 is a revision, row 3 is blank, and
    the row a human would call the header is row 4.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Schedule"
    sheet["A1"] = "SYNTHETIC CABLE SCHEDULE"
    sheet["A2"] = "Revision"
    sheet["B2"] = "C"
    sheet["A4"] = "Cable ID"
    sheet["B4"] = "From"
    sheet["C4"] = "To"
    sheet["A5"] = "CBL-020"
    sheet["B5"] = "PANEL-D"
    sheet["C5"] = "PANEL-E"
    return _to_bytes(workbook)


def sparse_and_blank() -> bytes:
    """
    Fixture D - gaps that must survive as gaps.

    Row 2 is entirely absent, row 3 has a hole at column B, and rows 8-10
    are empty. The reader records nothing for any of them, and the row and
    column numbers of what remains are the workbook's own - so a gap stays
    visible instead of being closed up by re-indexing.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sparse"
    sheet["A1"] = "Tag"
    sheet["B1"] = "Value"
    sheet["C1"] = "Unit"
    # row 2 omitted entirely
    sheet["A3"] = "QA2"
    sheet["C3"] = "A"          # B3 deliberately absent
    sheet["A4"] = "QA3"
    sheet["B4"] = 400
    sheet["C4"] = "A"
    sheet["E6"] = "island"     # far from the rest, no neighbours
    return _to_bytes(workbook)


def duplicate_and_blank_headers() -> bytes:
    """
    Fixture E - repeated and missing header-shaped labels.

    Two columns carry the same text and one carries none. Nothing here is
    deduplicated, renamed, or filled in: a test asserts the reader records
    four cells at row 1 and invents no identity for column D.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Duplicates"
    sheet["A1"] = "Tag"
    sheet["B1"] = "Value"
    sheet["C1"] = "Value"      # same text as B1
    # D1 deliberately empty
    sheet["E1"] = "Notes"
    sheet["A2"] = "QA4"
    sheet["B2"] = 11
    sheet["C2"] = 22
    sheet["D2"] = "orphan"
    return _to_bytes(workbook)


def formula_without_cached_result() -> bytes:
    """
    Fixture F - a formula in a workbook no spreadsheet application has
    ever opened.

    This is the common case, not the exotic one: a workbook written by a
    script carries the formula and no cached value at all. The reader must
    record that as "no application has ever computed a value here", never
    as a blank cell, an empty string, or a zero.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Computed"
    sheet["A1"] = "Cores"
    sheet["B1"] = "Section"
    sheet["A2"] = 4
    sheet["B2"] = 2.5
    sheet["C2"] = "=A2*B2"
    return _to_bytes(workbook)


def mixed_value_types() -> bytes:
    """
    Fixture G - one sheet exercising every cell type the model admits.

    Includes the two strings that must survive untouched: a value with
    significant trailing whitespace, and one carrying a non-breaking space
    - the character a spreadsheet acquires from a web paste and that NFKC
    normalisation would silently fold away.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Types"
    sheet["A1"] = "text"
    sheet["A2"] = 42                       # integer
    sheet["A3"] = 2.5                      # non-integer
    sheet["A4"] = True
    sheet["A5"] = datetime.datetime(2026, 3, 14, 9, 30, 0)
    sheet["A6"] = datetime.time(9, 30, 0)
    sheet["A7"] = "QMT01 "                 # trailing space is significant
    sheet["A8"] = "PANEL A"           # non-breaking space
    sheet["A9"] = "first\nsecond"          # embedded newline
    sheet["A10"] = datetime.timedelta(hours=26, minutes=30)
    # An error value as the file stores one. Assigning the text
    # alone would give a string that merely looks like an error; the
    # data type is what makes it one, and it is the reader's handling
    # of that type - not of the spelling - that needs proving.
    sheet["A11"] = "#DIV/0!"
    sheet["A11"].data_type = "e"
    return _to_bytes(workbook)


def empty_workbook() -> bytes:
    """Fixture H - a structurally valid workbook with no populated cell."""

    workbook = Workbook()
    workbook.active.title = "Blank"
    return _to_bytes(workbook)


def corrupted_package() -> bytes:
    """
    Fixture I - bytes that are not a readable OOXML package.

    A truncated ZIP: the local-file header is present, so a signature
    check alone would accept it, and only actually opening the package
    reveals that it is malformed.
    """

    return b"PK\x03\x04" + b"\x00" * 64


def encrypted_workbook() -> bytes:
    """
    Fixture J - the OLE2/CFB container Excel writes for an encrypted
    workbook.

    Deterministically distinguishable from a corrupted file by its first
    eight bytes, and worth distinguishing: the bytes are intact and
    someone holding the password could read them. No password is held
    here and none is guessed.
    """

    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64


def many_sheets(count: int) -> bytes:
    """
    Fixture K - a workbook with more sheets than the policy admits.

    Built small on purpose: the guardrail is a declared count, so proving
    it fires needs no large file and no slow test.
    """

    workbook = Workbook()
    workbook.active.title = "Sheet0"
    workbook.active["A1"] = "x"
    for index in range(1, count):
        sheet = workbook.create_sheet(f"Sheet{index}")
        sheet["A1"] = "x"
    return _to_bytes(workbook)
