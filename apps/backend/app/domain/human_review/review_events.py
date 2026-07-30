"""
The domain events of Human Review.

Four events, and they belong to **this** context. Nothing in the
engineering pipeline emits, consumes or knows about them: the pipeline
produces knowledge deterministically and has no opinion about who
approved what.

---

## Why these are values, not an event bus

Two of them (`ReviewRecorded`, `ReviewSuperseded`) describe something
that *happened* - a write - and are recorded in the audit trail at the
moment it happens.

The other two (`ReviewBecameHistorical`, `ReviewRequiresRevalidation`)
describe something that *became true* without anybody doing it: a
pipeline re-run under new rules did not visit the review context, and yet
afterwards the review no longer describes the current interpretation.
They are **observations, derived on read** from
``review_applicability.evaluate``.

Modelling them as published events would mean a subscriber, a queue and a
delivery guarantee - a workflow engine, which this milestone explicitly
must not build. Modelling them as values means the same distinctions are
nameable, testable and renderable, and nothing has to be kept in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.human_review.review_applicability import (
    ReviewApplicability,
)
from app.domain.human_review.review_models import Review
from app.domain.human_review.review_target import ReviewTarget


class ReviewEventType(str, Enum):
    """The closed catalogue of things that happen to a review."""

    RECORDED = "review_recorded"
    SUPERSEDED = "review_superseded"
    BECAME_HISTORICAL = "review_became_historical"
    REQUIRES_REVALIDATION = "review_requires_revalidation"


@dataclass(frozen=True, slots=True)
class ReviewRecorded:
    """A judgement was appended. The one event that always follows a write."""

    event_type: ReviewEventType = ReviewEventType.RECORDED
    review: Review | None = None
    occurred_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReviewSuperseded:
    """
    A newer judgement replaced an earlier one as the effective decision.

    The earlier review is **not** modified - it is still exactly what was
    written. This event names the fact that something newer now sits in
    front of it.
    """

    superseded_review: Review
    superseded_by: Review
    occurred_at: datetime
    event_type: ReviewEventType = ReviewEventType.SUPERSEDED


@dataclass(frozen=True, slots=True)
class ReviewBecameHistorical:
    """
    The reviewed artefact has no current interpretation to compare with.

    The semantic stage has not been run since, or its set is gone. Nothing
    is wrong with the review; there is simply nothing to check it against.
    """

    target: ReviewTarget
    event_type: ReviewEventType = ReviewEventType.BECAME_HISTORICAL


@dataclass(frozen=True, slots=True)
class ReviewRequiresRevalidation:
    """
    The document was re-interpreted under different bytes or rules, and
    the reviewed statement is not in the new interpretation.

    The judgement may well still hold. **Only a human may say so** -
    carrying it across to a differently-derived statement would attribute
    to an engineer an opinion about something they never saw.
    """

    target: ReviewTarget
    reviewed_rule_identity: str
    event_type: ReviewEventType = ReviewEventType.REQUIRES_REVALIDATION


ReviewEvent = (
    ReviewRecorded
    | ReviewSuperseded
    | ReviewBecameHistorical
    | ReviewRequiresRevalidation
)


def event_for_applicability(
    target: ReviewTarget,
    review: Review,
    applicability: ReviewApplicability,
) -> ReviewEvent | None:
    """
    The observation implied by a review's current applicability.

    ``None`` when the review still applies - nothing has become true that
    was not true when it was written, and an event saying "still fine"
    would be noise in a record that has to stay readable.
    """

    if applicability is ReviewApplicability.APPLIES:
        return None

    if applicability is ReviewApplicability.ORPHANED:
        return ReviewBecameHistorical(target=target)

    return ReviewRequiresRevalidation(
        target=target,
        reviewed_rule_identity=review.snapshot.rule_identity,
    )
