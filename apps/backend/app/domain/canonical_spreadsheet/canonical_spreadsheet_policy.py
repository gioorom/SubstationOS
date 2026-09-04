"""
The fixed policy of the canonical workbook representation (ADR-0034).

Two kinds of decision live here, and nothing else:

1. **What must be recorded alongside a representation** for it to stay
   explainable years later - the contract version and the formats this
   context admits.
2. **The safety bounds on decoding untrusted bytes.** A workbook arrives
   as a compressed container from outside this system, at the single
   riskiest point in the pipeline: the place where somebody else's bytes
   are decoded. Every bound is stated here as a named constant with the
   reason for its number, and is applied as a table rather than as a
   chain of conditions buried in the reader - so the policy can be
   reviewed by reading one file, and changing it is visibly a decision.

Neither kind is a knob to tune per document. A bound that varied by
caller would make the same bytes readable in one code path and refused
in another, which is exactly the machine-dependence this platform
forbids.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import ClassifiedFormat

# The representation's own version. Bumped when the *shape* of what is
# recorded changes - a new field, a different grouping - so a stored
# representation always says which contract it was built under. It is not
# the reader's version, which is recorded separately: the same shape can
# be produced by two library releases, and the same library can produce
# two shapes.
CANONICAL_WORKBOOK_VERSION = "1.0"

# Only the Office Open XML spreadsheet container participates. A legacy
# BIFF `.xls`, an `.xlsb`, a CSV and an ODS are four different problems,
# not four dialects of this one: CSV in particular has no worksheet, no
# types and a delimiter-guessing problem that deserves its own honest
# milestone rather than a silent partial reading here.
SUPPORTED_SPREADSHEET_FORMATS: frozenset[str] = frozenset(
    {ClassifiedFormat.XLSX.value}
)


# --- Safety bounds on decoding an untrusted container ----------------
#
# Each bound is a refusal, never a truncation. A reader that stopped at a
# limit and returned what it had would produce a representation that
# looks, to every future consumer, exactly like a register that ends
# there - and nothing downstream could tell the difference.

#: The compressed container itself. Ten times the largest cable register
#: anyone has delivered; a spreadsheet beyond it is a different kind of
#: object and deserves a conversation, not a silent read.
MAX_COMPRESSED_BYTES = 100_000_000

#: Everything the container unpacks to, in total. The bound that
#: actually protects memory and disk, because compression makes the
#: container size a poor proxy for the cost of reading it.
MAX_UNCOMPRESSED_BYTES = 1_000_000_000

#: Unpacked bytes per compressed byte, across the whole container. Office
#: Open XML is verbose, repetitive text and legitimately compresses
#: around 10:1; ten times that leaves honest files untouched while a
#: decompression bomb, which needs ratios in the thousands to be worth
#: building, is refused.
MAX_DECOMPRESSION_RATIO = 100

#: Unpacked bytes from any single entry. Stops one crafted worksheet part
#: from consuming the whole container budget on its own, which the
#: aggregate bound alone would allow.
MAX_ENTRY_UNCOMPRESSED_BYTES = 512_000_000

#: Entries in the container. A workbook needs one part per worksheet plus
#: a fixed handful of shared parts, so this admits a workbook far larger
#: than MAX_WORKSHEETS allows while refusing an archive padded with
#: entries to make inspection itself expensive.
MAX_ZIP_ENTRIES = 1024

#: Worksheets in one workbook. Comfortably beyond any delivered register
#: - the largest seen carry tens - and a bound at all because each
#: worksheet is an independent parse of untrusted XML.
MAX_WORKSHEETS = 256

#: Materialised rows in one worksheet. Roughly a fifth of the format's
#: own 1,048,576-row grid: a register beyond it is a database export, and
#: reading it as a register would be the wrong answer rather than a slow
#: one.
MAX_ROWS_PER_WORKSHEET = 200_000

#: Row indices one worksheet may make a reader walk - the format's own
#: grid, so no file a spreadsheet application can write is affected.
#:
#: Distinct from ``MAX_ROWS_PER_WORKSHEET``, and needed beside it. That
#: bound counts rows that *materialise something*, so a file declaring
#: two populated rows either side of an enormous gap never approaches
#: it - while the reader still walks every index in between. The work
#: is done whether or not anything is found in it, which is how a
#: five-kilobyte upload can cost minutes of CPU and defeat the promise
#: below that cost is bounded by bounding the work. The coordinate is
#: parsed as an unbounded integer, so the file, not the format, would
#: otherwise decide how much walking there is.
MAX_ROW_NUMBER = 1_048_576

#: The highest column number a worksheet may reach. The format allows
#: 16,384; a register that is a thousand columns wide is not a register,
#: and the bound keeps a single crafted row from forcing a wide scan.
MAX_COLUMNS_PER_WORKSHEET = 1024

#: Populated cells across the whole workbook. The bound that governs the
#: size of the representation actually built, and therefore the memory
#: this system spends on one untrusted file. Two million cells is a
#: hundred columns across every row the row bound admits.
MAX_POPULATED_CELLS = 2_000_000

#: Integer digits one recorded number may carry, and therefore the
#: widest magnitude this representation will record at all.
#:
#: **Set by what the store demonstrably preserves, not by what the
#: column declares.** The column is 38 digits with 12 after the point,
#: which would allow 26 before it - but measuring the deployed stack
#: shows exactness ends at fifteen integer digits; the sixteenth already
#: returns a different number.
#:
#: **This bounds magnitude only, and nothing here bounds scale.** The
#: column rounds to twelve decimal places, so a cell holding pi is
#: recorded as 3.14159265359 and one holding 1e-20 is recorded as zero.
#: Neither is refused, and refusing them would be the wrong trade: a
#: register legitimately carries such values, and losing the workbook
#: over them would be worse than recording them at the column's scale.
#: ``literal_text`` keeps the reading the file actually states, and
#: ADR-0034 makes it the authoritative rendering for exactly this
#: reason - the numeric column is a queryable projection of it, not a
#: second original.
#:
#: A magnitude past the bound is refused rather than truncated, for the
#: same reason a too-large workbook is refused rather than partially
#: read - and refused rather than stored, because past a certain size it
#: becomes an infinity in the column and the row can then never be read
#: again.
#:
#: Bounded here rather than only checked for finiteness because a
#: spreadsheet payload with no decimal point is parsed as a Python
#: integer, which has no width at all: a four-hundred-digit literal is a
#: perfectly finite number that no column can hold.
#:
#: Fifteen digits is a thousand million million. No rated current,
#: voltage, length or cross-section comes near it.
MAX_NUMERIC_INTEGER_DIGITS = 15

#: Characters in one cell's recorded text. The format's own limit for a
#: cell, so anything longer is a non-conformant file rather than a long
#: description, and truncating it would silently alter what the register
#: says.
MAX_CELL_TEXT_LENGTH = 32_767

# There is deliberately **no wall-clock timeout.** A bound on elapsed
# time would make the outcome depend on the machine, its load and the
# day: the same bytes would canonicalise on a fast host and fail on a
# busy one, and a representation's identity would no longer be a
# function of its inputs. Every bound above is a property of the file,
# so the same bytes always produce the same verdict everywhere. Cost is
# bounded by bounding the work, not by bounding the clock.


def is_readable_spreadsheet_format(document_format: str) -> bool:
    return document_format in SUPPORTED_SPREADSHEET_FORMATS
