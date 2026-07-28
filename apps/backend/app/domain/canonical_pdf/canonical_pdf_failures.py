"""
The failure taxonomy for canonical PDF representation (Milestone 26.1).

A **separate enum** from ``IngestionFailureCode``, deliberately, with the
five shared causes carrying identical string values and a test asserting
they agree. Two contexts, two vocabularies:

- ingestion answers "may this document proceed?" and knows nothing about
  PDF internals;
- canonicalisation answers "could these bytes be turned into text?" and
  has failures - encrypted, corrupted, parser failure - that would mean
  nothing on an ingestion job.

Importing ingestion's enum here would drag PDF-parsing concerns into a
context that deliberately has none, and would grow that enum every time a
new format is supported. Restating the shared values and asserting the
agreement by test gives the same protection against drift without the
coupling - the same discipline ``ClassifiedFormat`` uses against
``DocumentFormat``.

Every cause is named. Nothing is collapsed into a generic "parse failed",
because these five send an engineer to five different places: the file is
not a PDF at all, it is locked, it is damaged, the library gave up, or
there is simply nothing in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CanonicalizationFailureCode(str, Enum):
    """Why a document could not be given a canonical representation."""

    # --- Shared with IngestionFailureCode (values asserted equal) ----
    DOCUMENT_NOT_FOUND = "document_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    CONTENT_NOT_FOUND = "content_not_found"
    CONTENT_INACCESSIBLE = "content_inaccessible"
    EMPTY_CONTENT = "empty_content"

    # --- This context's own ------------------------------------------
    # The document exists and is a PDF, but no ingestion job has declared
    # it ready. Canonicalisation is the step *after* ingestion, and
    # parsing a document nobody accepted would bypass the governed flow.
    NOT_READY_FOR_EXTRACTION = "not_ready_for_extraction"
    # Locked with a password. Distinct from corrupted: the bytes are
    # intact and someone with the password could read them, so this is a
    # question for whoever supplied the file, not a data-integrity fault.
    ENCRYPTED_DOCUMENT = "encrypted_document"
    # The bytes are not a readable PDF - truncated, damaged, or never a
    # PDF despite what the format says.
    CORRUPTED_DOCUMENT = "corrupted_document"
    # The library failed for a reason of its own, on bytes it accepted.
    # The one genuinely unknown cause here, and the only one that should
    # ever prompt "look at the parser".
    PARSER_FAILURE = "parser_failure"
    # A valid PDF carrying no pages at all.
    EMPTY_DOCUMENT = "empty_document"
    # Pages exist and not one text span was found anywhere. This names an
    # *observation*, not a diagnosis: it does not claim the document is
    # scanned, and this milestone reads nothing that could support such a
    # claim. It fails rather than persisting a representation with no
    # text, which would look to every future extractor like a document
    # that genuinely says nothing.
    NO_EXTRACTABLE_TEXT = "no_extractable_text"
    # The representation was built and could not be stored.
    REPRESENTATION_PERSISTENCE_FAILURE = "representation_persistence_failure"


@dataclass(frozen=True, slots=True)
class CanonicalizationFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: CanonicalizationFailureCode
    message: str
    detail: str | None = None
