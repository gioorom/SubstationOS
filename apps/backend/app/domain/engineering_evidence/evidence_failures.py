"""
The failure taxonomy for Engineering Evidence Extraction
(Milestone 28.1).

A separate enum from the segmentation and canonicalisation vocabularies,
for the reason those are separate from each other: these are different
questions. Segmentation asks "could this text be structured?"; extraction
asks "could this structure be observed against the rules?" and has
failures - an invalid rule, an unsupported unit - that would be
meaningless upstream.

The two shared causes carry identical string values, asserted by test.

Ten named causes. Nothing is collapsed into a generic "extraction
failed", because they send an engineer to genuinely different places: a
missing input, an input built under rules this code does not know, a
defect in a rule, a document that wrote a number the policy cannot read,
a unit nobody declared, a storage fault.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceFailureCode(str, Enum):
    """Why an evidence set could not be produced."""

    # There is no canonical text for this document. Not an error about
    # the document - extraction is the step after segmentation.
    CANONICAL_TEXT_MISSING = "canonical_text_missing"
    # The canonical text was built under a segmentation contract this
    # extractor does not know. Refusing is the only safe answer: a newer
    # segmentation may group tokens differently, and provenance recorded
    # against the wrong grouping would point at the wrong characters.
    UNSUPPORTED_CANONICAL_TEXT_VERSION = (
        "unsupported_canonical_text_version"
    )
    # A candidate's provenance could not be stated exactly - it crossed a
    # line, paragraph or page boundary. Such a candidate is dropped
    # rather than recorded with an approximate location.
    INVALID_PROVENANCE = "invalid_provenance"
    # A rule in the catalogue is malformed - an unknown kind, a missing
    # version. A defect, caught before it can produce evidence.
    INVALID_EXTRACTION_RULE = "invalid_extraction_rule"
    # A rule raised while running. The one genuinely unknown cause here.
    RULE_EXECUTION_FAILURE = "rule_execution_failure"
    # A quantity matched and could not be read exactly. Reported per
    # candidate as a status; this code exists for the case where it
    # stops the whole extraction.
    INVALID_ENGINEERING_QUANTITY = "invalid_engineering_quantity"
    # A unit-shaped token that the unit catalogue does not declare.
    # Never guessed at - an undeclared unit is simply not a unit.
    UNSUPPORTED_UNIT = "unsupported_unit"
    # The assembled set violates an invariant of the model.
    EVIDENCE_VALIDATION_FAILURE = "evidence_validation_failure"
    # Built, and could not be stored.
    EVIDENCE_PERSISTENCE_FAILURE = "evidence_persistence_failure"
    # The canonical text and the document disagree about which bytes are
    # being described. Continuing would attach observations to the wrong
    # version of a document.
    INCONSISTENT_SOURCE_IDENTITY = "inconsistent_source_identity"


@dataclass(frozen=True, slots=True)
class EvidenceFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: EvidenceFailureCode
    message: str
    detail: str | None = None
