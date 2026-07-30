"""
Typed failures of the Human Review context.

Every one derives from ``HumanReviewError``. None of them carries an
engineering artefact - a review context that raised an exception holding
a semantic statement would have had to obtain one first.
"""

from __future__ import annotations


class HumanReviewError(Exception):
    """Base class for every failure of the Human Review context."""


class InvalidReviewTargetError(HumanReviewError):
    """The target names no artefact, or no document."""


class InvalidReviewCommentError(HumanReviewError):
    """A comment that is empty, or longer than the record allows."""


class ReviewPolicyViolationError(HumanReviewError):
    """
    The review is well-formed and the policy refuses it.

    Carries the unmet requirements so a caller can report all of them at
    once, rather than a reviewer discovering them one submission at a
    time.
    """

    def __init__(self, message: str, *, violations: tuple[str, ...]) -> None:
        super().__init__(message)
        self.violations = violations


class InvalidReviewSnapshotError(HumanReviewError):
    """A snapshot that does not identify what was reviewed."""


class ReviewTargetNotFoundError(HumanReviewError):
    """
    No such statement in the document's current interpretation.

    Raised when recording a review, never when reading one: a review of a
    statement that has since disappeared stays readable forever - that is
    the entire point of the snapshot.
    """

    def __init__(self, message: str, *, target_key: str) -> None:
        super().__init__(message)
        self.target_key = target_key


class ReviewPersistenceError(HumanReviewError):
    """The review could not be appended."""
