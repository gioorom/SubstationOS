"""
The current decision, computed rather than stored.

**Nothing in this module is persisted.** The history is authoritative;
everything here is derived from it on read. A stored `current_decision`
column would be a second account of the same fact, and the day it
disagreed with the history there would be no way to tell which was true -
so there is no such column, and an architecture test asserts it.

The projection answers, for one target:

- has anybody reviewed this at all?
- if so, what is the effective decision, and who made it when?
- does that decision still describe today's pipeline?
- which earlier judgements has it superseded?
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.human_review.review_applicability import (
    CurrentPipelineState,
    ReviewApplicability,
    evaluate,
    has_integrity,
)
from app.domain.human_review.review_models import Review
from app.domain.human_review.review_target import ReviewTarget
from app.domain.human_review.review_vocabulary import ReviewDecision


@dataclass(frozen=True, slots=True)
class TargetReviewProjection:
    """
    Everything a reader needs about one target's review state.

    ``current`` is ``None`` for a target nobody has reviewed - which is a
    distinct state from every decision, and never rendered as one.
    """

    target: ReviewTarget

    #: The newest review, or ``None`` when there are none.
    current: Review | None

    #: How many reviews exist in total, including the current one.
    review_count: int

    #: Whether the current judgement still describes today's pipeline.
    #: ``ORPHANED`` for a target with no reviews, since there is nothing
    #: whose applicability could be in question.
    applicability: ReviewApplicability

    #: ``False`` only when a statement kept its key and changed its
    #: support - which should be impossible. See ``has_integrity``.
    snapshot_intact: bool = True

    @property
    def is_reviewed(self) -> bool:
        return self.current is not None

    @property
    def decision(self) -> ReviewDecision | None:
        return None if self.current is None else self.current.decision

    @property
    def requires_revalidation(self) -> bool:
        return (
            self.is_reviewed
            and self.applicability is ReviewApplicability.REQUIRES_REVALIDATION
        )


def project(
    target: ReviewTarget,
    history: tuple[Review, ...],
    current_state: CurrentPipelineState,
) -> TargetReviewProjection:
    """
    Builds the projection for one target.

    ``history`` must be **newest first** - the repository port says so,
    and the ordering is the whole of how "current" is decided. Taking the
    newest rather than scanning for a status field is what keeps the
    current decision a projection: there is no flag anywhere that could
    disagree with the order the reviews were written in.
    """

    if not history:
        return TargetReviewProjection(
            target=target,
            current=None,
            review_count=0,
            applicability=ReviewApplicability.ORPHANED,
            snapshot_intact=True,
        )

    current = history[0]

    return TargetReviewProjection(
        target=target,
        current=current,
        review_count=len(history),
        applicability=evaluate(current.snapshot, current_state),
        snapshot_intact=has_integrity(current.snapshot, current_state),
    )


@dataclass(frozen=True, slots=True)
class ReviewHistoryEntry:
    """
    One review, plus whether it is still the effective one.

    ``superseded`` is derived from position, not stored: every review
    except the newest has been superseded by definition. A stored flag
    would have to be written onto an immutable record, which is exactly
    what this context does not do.
    """

    review: Review
    superseded: bool

    #: The applicability of *this* review's own snapshot. A history entry
    #: from before a rule change reports `REQUIRES_REVALIDATION` even when
    #: a newer review applies, because that is the truth about the
    #: judgement that entry records.
    applicability: ReviewApplicability


def build_history(
    history: tuple[Review, ...],
    current_state: CurrentPipelineState,
) -> tuple[ReviewHistoryEntry, ...]:
    """
    Annotates a newest-first history with what each entry now means.

    Deterministic and order-preserving: the same history and the same
    pipeline state always produce the same annotations, which is what
    makes a review timeline worth attaching to an engineering query.
    """

    return tuple(
        ReviewHistoryEntry(
            review=review,
            superseded=index > 0,
            applicability=evaluate(review.snapshot, current_state),
        )
        for index, review in enumerate(history)
    )


@dataclass(frozen=True, slots=True)
class DocumentReviewSummary:
    """
    Every reviewed target in one document, as one value.

    Exists so the Workspace can badge a list of statements with one
    request instead of one per statement - the same reasoning that kept
    EPIC 30.2 from building a support-chain endpoint, applied in the
    other direction.
    """

    document_id: int
    projections: tuple[TargetReviewProjection, ...] = field(
        default_factory=tuple
    )

    def for_key(self, target_key: str) -> TargetReviewProjection | None:
        for projection in self.projections:
            if projection.target.target_key == target_key:
                return projection

        return None
