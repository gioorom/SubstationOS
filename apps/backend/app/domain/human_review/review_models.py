"""
One recorded engineering judgement.

**A review is immutable and the history is append-only.** There is no
method here that changes a decision, no status field that a later event
flips, and the repository port declares no update and no delete. An
engineer who changes their mind records another review; the first one
stays exactly as it was written, because "what did we think in March?" is
a question an engineering record has to be able to answer.

The consequence, stated once because everything else follows from it:
**the current decision is never stored.** It is the newest review for a
target, computed on read. A stored `current` column would be a second
account of the same fact, and the day it disagreed with the history there
would be no way to tell which was true.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.human_review.review_exceptions import (
    InvalidReviewCommentError,
)
from app.domain.human_review.review_snapshot import ReviewSnapshot
from app.domain.human_review.review_target import ReviewTarget
from app.domain.human_review.review_vocabulary import (
    ReviewDecision,
    ReviewReason,
)

MAX_COMMENT_LENGTH = 4000

REVIEW_RECORD_VERSION = "1.0"
"""
The version of the review record's own shape.

Recorded on every review so a future change to what a review carries can
be told from the outside. It is **not** a pipeline version and has
nothing to do with the artefact reviewed - those live on the snapshot.
"""


@dataclass(frozen=True, slots=True)
class ReviewComment:
    """
    A reviewer's explanation, in plain text.

    Plain text, not markdown, and that is a decision rather than an
    omission: rendering user-authored markup means sanitising it, and a
    review comment is read by engineers and by an audit, neither of whom
    needs a heading. See `human_review.md` on what it would take to
    change this safely.
    """

    text: str

    def __post_init__(self) -> None:
        stripped = self.text.strip()

        if not stripped:
            raise InvalidReviewCommentError(
                "A comment must say something; leave it out instead."
            )

        if len(stripped) > MAX_COMMENT_LENGTH:
            raise InvalidReviewCommentError(
                f"A comment may not exceed {MAX_COMMENT_LENGTH} "
                "characters."
            )

        object.__setattr__(self, "text", stripped)

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class ReviewerIdentity:
    """
    Who reviewed, as they were at the moment of reviewing.

    Copied from the authenticated ``AuditIdentity`` rather than referenced
    by id, and deliberately so: an account can be renamed, re-roled or
    disabled, and a review that rendered as "user 7" afterwards would have
    lost the thing it exists to record. The id is kept as well, so the
    trail can still be joined to a live account when there is one.

    Carries no credential. There is no field here one could occupy.
    """

    user_id: int
    display_name: str
    email: str
    role: str

    def describe(self) -> str:
        return f"{self.display_name} <{self.email}>"


@dataclass(frozen=True, slots=True)
class Review:
    """
    One judgement, recorded once, never amended.

    It references an artefact by key (``target``) and records the identity
    that artefact had at the time (``snapshot``). It contains no part of
    the artefact, and there is no field in which one could be placed - so
    a review cannot become a second, divergent account of what a document
    says.

    ``review_id`` is ``None`` before the repository assigns one, the same
    convention every other entity in this codebase uses.
    """

    review_id: int | None
    target: ReviewTarget
    decision: ReviewDecision
    reason: ReviewReason
    comment: ReviewComment | None
    reviewer: ReviewerIdentity
    snapshot: ReviewSnapshot
    recorded_at: datetime
    record_version: str = REVIEW_RECORD_VERSION

    @property
    def has_comment(self) -> bool:
        return self.comment is not None

    def describe(self) -> str:
        """One line, for an audit event's detail."""

        return (
            f"{self.decision.value} ({self.reason.value}) on "
            f"{self.target.describe()}"
        )
