"""
The failure taxonomy for canonical workbook representation (ADR-0034).

A **separate enum**, deliberately, with the five shared causes carrying
identical string values and a test asserting they agree. This is the
idiom the repository already uses for exactly this problem:
``CanonicalizationFailureCode`` restates five of ``IngestionFailureCode``
rather than importing them, precisely so that one context's concerns do
not leak into another that has none.

Here the reason is stronger still. The spreadsheet lineage and the PDF
lineage never meet - a fitness function asserts it - so importing the PDF
context's enum to reuse five strings would be the first thread joining
two families that ADR-0034 forked apart on purpose. Restating the values
and asserting the agreement by test gives the same protection against
drift without the coupling.

Every cause is named. Nothing is collapsed into a generic "read failed",
because these send an engineer to different places: the file is locked,
its container is damaged, it is a decompression trap, it is simply too
big to read safely, the library gave up, or there is honestly nothing in
it.
"""

from __future__ import annotations

from enum import Enum


class WorkbookCanonicalizationFailureCode(str, Enum):
    """Why a document could not be given a canonical workbook."""

    # --- Shared with IngestionFailureCode (values asserted equal) ----
    DOCUMENT_NOT_FOUND = "document_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    CONTENT_NOT_FOUND = "content_not_found"
    CONTENT_INACCESSIBLE = "content_inaccessible"
    EMPTY_CONTENT = "empty_content"

    # --- This context's own ------------------------------------------
    # The document exists and is a spreadsheet, but no ingestion job has
    # declared it ready. Reading is the step *after* ingestion, and
    # reading a document nobody accepted would bypass the governed flow.
    NOT_READY_FOR_EXTRACTION = "not_ready_for_extraction"
    # Locked with a password: the container is an encrypted envelope
    # rather than a workbook. Distinct from malformed - the bytes are
    # intact and someone with the password could read them, so this is a
    # question for whoever supplied the file, not a data-integrity
    # fault. This system holds no password and must not guess one.
    ENCRYPTED_WORKBOOK = "encrypted_workbook"
    # The container is not a readable workbook - truncated, damaged, or
    # never a workbook despite what the format says.
    MALFORMED_PACKAGE = "malformed_package"
    # The container decompresses to far more than it is worth: an entry
    # count, an expansion ratio or an unpacked size beyond what the
    # safety policy admits. Named separately from "too large" because it
    # is a hostile-file signal, not a big honest register, and the two
    # send an engineer to different conversations.
    DECOMPRESSION_LIMIT_EXCEEDED = "decompression_limit_exceeded"
    # An honest workbook past a documented safety bound - too many
    # worksheets, rows, columns or cells to read within stated limits.
    # Refused rather than truncated: a partial representation would look
    # to every future consumer like a register that simply ends there.
    WORKBOOK_TOO_LARGE = "workbook_too_large"
    # The library failed for a reason of its own, on bytes it accepted.
    # The one genuinely unknown cause here, and the only one that should
    # ever prompt "look at the reader".
    READER_FAILURE = "reader_failure"
    # A valid container carrying no worksheet at all.
    EMPTY_WORKBOOK = "empty_workbook"
    # Worksheets exist and not one cell was populated anywhere. This
    # names an *observation*, not a diagnosis: it does not claim the file
    # is a template or a macro container, and this context reads nothing
    # that could support such a claim. It fails rather than persisting a
    # representation with no cell, which would look to every future
    # consumer like a register that genuinely says nothing.
    NO_POPULATED_CELL = "no_populated_cell"
    # The representation was built and could not be stored.
    REPRESENTATION_PERSISTENCE_FAILURE = "representation_persistence_failure"
