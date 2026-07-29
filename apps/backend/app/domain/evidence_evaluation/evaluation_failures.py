"""
The failure taxonomy for evidence evaluation (Milestone 28.2).

A separate enum from the extraction vocabulary, for the reason those are
separate from each other: these are different questions. Extraction asks
"what does this document contain?"; evaluation asks "was the extractor
right?" and has failures - a malformed corpus, an unreadable annotation -
that would be meaningless upstream.

Six named causes. Nothing is collapsed into a generic "evaluation
failed", because they send an engineer to different places: the corpus is
missing, the corpus is malformed, a reference document cannot be
materialised, the extractor itself failed, the report cannot be stored,
or two reports cannot honestly be compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvaluationFailureCode(str, Enum):
    """Why an evaluation could not be produced."""

    # No corpus with that id exists in the repository.
    CORPUS_NOT_FOUND = "corpus_not_found"
    # A corpus file exists and does not parse, or violates the model -
    # an annotation citing a token range that its own document does not
    # contain, say. Refused loudly: a corpus is the definition of
    # correct, and a malformed one would quietly redefine it.
    INVALID_CORPUS = "invalid_corpus"
    # A reference document's text could not be turned into canonical
    # text, so there is nothing to run the extractor over.
    REFERENCE_DOCUMENT_UNUSABLE = "reference_document_unusable"
    # The extractor raised while running over a reference document. The
    # one genuinely unknown cause here.
    EXTRACTION_FAILURE = "extraction_failure"
    # Built, and could not be stored.
    REPORT_PERSISTENCE_FAILURE = "report_persistence_failure"
    # A comparison was requested between reports that do not exist.
    REPORT_NOT_FOUND = "report_not_found"


@dataclass(frozen=True, slots=True)
class EvaluationFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: EvaluationFailureCode
    message: str
    detail: str | None = None
