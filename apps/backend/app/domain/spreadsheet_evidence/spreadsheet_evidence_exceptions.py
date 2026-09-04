"""
The error vocabulary of the spreadsheet evidence context (ADR-0034).

Two kinds of error live here, and the module holds both because this
context has exactly one of each and splitting them would give a reader
two files to open for one question:

1. **A raised error**, for a value object built in a state the model
   forbids. It is raised at construction and never later - an incoherent
   observation that reached storage would be trusted by every future
   consumer, and the fault would surface as an inexplicable extraction
   rather than as the defect it is.
2. **A returned failure**, for an extraction that could not be performed
   at all. A missing workbook or a storage fault is a condition of the
   world, not a defect, and a caller needs one honest answer rather than
   an exception crossing the boundary.

The taxonomy is **restated, not imported** from
``engineering_evidence.evidence_failures``. That is the same idiom
``WorkbookCanonicalizationFailureCode`` already uses against
``IngestionFailureCode``, and the reason is stronger here: ADR-0034
forks the spreadsheet lineage from the PDF one at the bytes, and
importing the PDF family's enum to reuse a handful of strings would be
the first thread joining two families that were separated on purpose.

Every cause is named. Nothing is collapsed into a generic "extraction
failed", because these send an engineer to different places: there is no
workbook yet, the workbook was read under a contract this extractor does
not know, its provenance is unknown, a rule is defective, or storage
refused the set.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpreadsheetEvidenceError(Exception):
    """Base error for everything this bounded context raises."""


class InvalidSpreadsheetEvidenceError(SpreadsheetEvidenceError):
    """
    An observation was constructed in a state the model forbids - a
    single item carrying both a quantity and a designation.

    Both populated would leave every consumer free to pick whichever
    suited it, and "what was observed here" would then vary by consumer.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class SpreadsheetEvidenceFailureCode(str, Enum):
    """Why a spreadsheet evidence set could not be produced."""

    # There is no canonical workbook for this document. Not an error
    # about the document - extraction is the step after the workbook was
    # read, and this context never opens a file itself.
    CANONICAL_WORKBOOK_MISSING = "canonical_workbook_missing"
    # The workbook was recorded under a representation contract this
    # extractor does not know. Refusing is the only safe answer: a newer
    # contract may record a cell's text differently, and character
    # offsets taken against the wrong recording would point at the wrong
    # characters - which is worse than no evidence at all.
    UNSUPPORTED_WORKBOOK_VERSION = "unsupported_workbook_version"
    # The workbook and the document disagree about what is being
    # described, or the workbook carries no derivation identity at all.
    # Continuing would attach observations to the wrong document, or to
    # a source that can never prove its own reuse is valid.
    INCONSISTENT_SOURCE_IDENTITY = "inconsistent_source_identity"
    # A rule raised while running. The one genuinely unknown cause here,
    # and the only one that should ever prompt "look at the rules".
    RULE_EXECUTION_FAILURE = "rule_execution_failure"
    # The set was built and could not be stored.
    EVIDENCE_PERSISTENCE_FAILURE = "evidence_persistence_failure"


@dataclass(frozen=True, slots=True)
class SpreadsheetEvidenceFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: SpreadsheetEvidenceFailureCode
    message: str
    detail: str | None = None
