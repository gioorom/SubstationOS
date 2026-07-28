"""
The failure taxonomy for canonical text segmentation (Milestone 27.1).

A separate enum from ``CanonicalizationFailureCode``, for the same reason
that one is separate from ``IngestionFailureCode``: these are different
questions. Canonicalisation asks "could these bytes be turned into
text?"; segmentation asks "could that text be turned into a structure?"
and has no idea what a PDF is.

The one shared cause - a persistence failure - carries an identical
string value, and a test asserts the two agree.

Five causes, each named. Nothing is collapsed into a generic
"segmentation failed", because they send an engineer to five different
places: nothing to segment, something malformed to segment, something
built under rules this code does not know, a fault in the segmenter, or a
fault in storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SegmentationFailureCode(str, Enum):
    """Why a document could not be segmented."""

    # There is no canonical representation for this document. Not an
    # error about the document - it simply has not been canonicalised,
    # and segmentation is the step after that one.
    CANONICAL_REPRESENTATION_MISSING = "canonical_representation_missing"
    # A representation exists and does not hold together - a page
    # sequence with a hole in it, a reading order that skips. Distinct
    # from a segmenter fault: the input was already wrong.
    INVALID_CANONICAL_REPRESENTATION = "invalid_canonical_representation"
    # The representation was built under a contract this segmenter does
    # not know. Refusing is the only safe answer: a newer representation
    # may carry fields whose meaning this code would silently
    # misinterpret.
    UNSUPPORTED_REPRESENTATION_VERSION = "unsupported_representation_version"
    # The segmenter failed on input it accepted - the one genuinely
    # unknown cause here.
    SEGMENTATION_FAILURE = "segmentation_failure"
    # Shared with Milestone 26.1 (value asserted equal by test).
    REPRESENTATION_PERSISTENCE_FAILURE = "representation_persistence_failure"


@dataclass(frozen=True, slots=True)
class SegmentationFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: SegmentationFailureCode
    message: str
    detail: str | None = None
