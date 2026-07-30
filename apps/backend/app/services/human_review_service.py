"""
Application service for Human Review.

This is the **one** place the two contexts meet, and the meeting is
strictly one-directional:

```
    Human Review  ◀──reads──  Engineering Semantics
         │
         └── writes only engineering_reviews
```

It reads the semantic set to answer two questions - *does this statement
exist?* and *what identity does it have now?* - and it writes only
reviews. It never calls a pipeline stage, never modifies a semantic set,
and has no code path that could: the engineering repositories it holds
are read through, and the only write it performs is
``ReviewRepository.append``.

The domain modules underneath know nothing of this. ``review_applicability``
takes a ``CurrentPipelineState`` - a thin description of identity - and
this service is what fills it in, which is how the Human Review domain
stays free of any engineering import at all. An architecture test asserts
the direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.engineering_semantics.engineering_semantic_repository import (
    EngineeringSemanticRepository,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
    EngineeringSemanticStatement,
)
from app.domain.human_review import review_policy
from app.domain.human_review.review_applicability import (
    CurrentPipelineState,
)
from app.domain.human_review.review_events import (
    ReviewEvent,
    ReviewRecorded,
    ReviewSuperseded,
    event_for_applicability,
)
from app.domain.human_review.review_exceptions import (
    ReviewTargetNotFoundError,
)
from app.domain.human_review.review_models import (
    Review,
    ReviewComment,
    ReviewerIdentity,
)
from app.domain.human_review.review_projection import (
    DocumentReviewSummary,
    ReviewHistoryEntry,
    TargetReviewProjection,
    build_history,
    project,
)
from app.domain.human_review.review_repository import ReviewRepository
from app.domain.human_review.review_snapshot import (
    ReviewSnapshot,
    fingerprint_support,
)
from app.domain.human_review.review_target import ReviewTarget
from app.domain.human_review.review_vocabulary import (
    ReviewDecision,
    ReviewReason,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.shared_kernel.pagination import Page, PageRequest


@dataclass(frozen=True, slots=True)
class RecordedReview:
    """
    What appending a review produced.

    ``events`` carries what happened, for the caller to put in the audit
    trail. ``superseded`` is the review this one displaced, or ``None`` -
    and the displaced review is returned **unmodified**, because nothing
    modified it.
    """

    review: Review
    superseded: Review | None
    events: tuple[ReviewEvent, ...]


def record_review(
    reviews: ReviewRepository,
    semantics: EngineeringSemanticRepository,
    *,
    document_id: int,
    statement_key: str,
    decision: ReviewDecision,
    reason: ReviewReason,
    comment: str | None,
    identity: AuditIdentity,
    now: datetime,
) -> RecordedReview:
    """
    Appends one judgement about one semantic statement.

    Four things happen, in this order, and the order matters:

    1. **The policy is checked** before anything is read or written, so a
       malformed review costs no database work.
    2. **The statement is resolved** in the document's *current*
       interpretation. A review may only be recorded against something
       that exists right now - reviewing a statement that has already been
       superseded would produce a judgement that was stale the moment it
       was written.
    3. **The snapshot is taken** from that statement and its set. This is
       what lets the review outlive both.
    4. **The review is appended.** Nothing is updated; the previous
       current review is read only so the caller can record that it was
       superseded.

    ``identity`` is the **authenticated** actor, resolved by the API's
    security layer. There is no parameter here through which a caller
    could name somebody else.
    """

    parsed_comment = None if comment is None else ReviewComment(comment)

    review_policy.check(decision, reason, parsed_comment)

    semantic_set = semantics.find_latest_for_document(document_id)
    statement = _require_statement(semantic_set, document_id, statement_key)

    target = ReviewTarget.semantic_statement(statement_key, document_id)
    previous = reviews.latest_for(target)

    appended = reviews.append(
        Review(
            review_id=None,
            target=target,
            decision=decision,
            reason=reason,
            comment=parsed_comment,
            reviewer=_reviewer(identity),
            snapshot=_snapshot_of(statement, semantic_set),
            recorded_at=now,
        )
    )

    events: list[ReviewEvent] = [
        ReviewRecorded(review=appended, occurred_at=now)
    ]

    if previous is not None:
        events.append(
            ReviewSuperseded(
                superseded_review=previous,
                superseded_by=appended,
                occurred_at=now,
            )
        )

    return RecordedReview(
        review=appended,
        superseded=previous,
        events=tuple(events),
    )


def current_review(
    reviews: ReviewRepository,
    semantics: EngineeringSemanticRepository,
    *,
    document_id: int,
    statement_key: str,
) -> TargetReviewProjection:
    """
    The effective decision for one statement, computed from history.

    Works for a statement that no longer exists: that is the case the
    snapshot exists for, and the projection reports it as
    ``REQUIRES_REVALIDATION`` or ``ORPHANED`` rather than as an error.
    """

    target = ReviewTarget.semantic_statement(statement_key, document_id)
    latest = reviews.latest_for(target)
    state = _pipeline_state(semantics, target)

    if latest is None:
        return project(target, (), state)

    # `project` decides applicability and integrity from the newest
    # review; the count is the one thing it cannot know from a single
    # review, so it is read separately and substituted in.
    projected = project(target, (latest,), state)

    return TargetReviewProjection(
        target=target,
        current=latest,
        review_count=reviews.count_for(target),
        applicability=projected.applicability,
        snapshot_intact=projected.snapshot_intact,
    )


def review_history(
    reviews: ReviewRepository,
    semantics: EngineeringSemanticRepository,
    *,
    document_id: int,
    statement_key: str,
    page: PageRequest,
) -> tuple[Page[Review], tuple[ReviewHistoryEntry, ...]]:
    """
    One page of a statement's history, annotated.

    The page carries the raw reviews and the paging metadata; the
    annotations say, for each, whether it has been superseded and whether
    its own snapshot still describes today's pipeline.

    **Superseded-ness is computed per page and is position-relative.**
    Entry 0 of page 2 is superseded - everything on page 1 is newer than
    it - which is why the annotation is derived from the absolute offset
    rather than from the index within the page.
    """

    target = ReviewTarget.semantic_statement(statement_key, document_id)
    found = reviews.history_for(target, page)
    state = _pipeline_state(semantics, target)

    annotated = build_history(found.items, state)

    if page.offset > 0:
        # Nothing on a later page can be the current review.
        annotated = tuple(
            ReviewHistoryEntry(
                review=entry.review,
                superseded=True,
                applicability=entry.applicability,
            )
            for entry in annotated
        )

    return (found, annotated)


def document_review_summary(
    reviews: ReviewRepository,
    semantics: EngineeringSemanticRepository,
    *,
    document_id: int,
) -> DocumentReviewSummary:
    """
    The current decision for every reviewed statement in one document.

    One request, so the Workspace can badge a list of statements without a
    request per row - the same reasoning that kept EPIC 30.2 from adding a
    support-chain endpoint, applied in the other direction. The semantic
    set is read **once** and every projection is evaluated against it.
    """

    semantic_set = semantics.find_latest_for_document(document_id)
    latest = reviews.latest_for_document(document_id)

    return DocumentReviewSummary(
        document_id=document_id,
        projections=tuple(
            _summarise(reviews, semantic_set, review) for review in latest
        ),
    )


def _summarise(
    reviews: ReviewRepository,
    semantic_set: EngineeringSemanticSet | None,
    review: Review,
) -> TargetReviewProjection:
    projected = project(
        review.target,
        (review,),
        _state_from_set(semantic_set, review.target.target_key),
    )

    return TargetReviewProjection(
        target=review.target,
        current=review,
        review_count=reviews.count_for(review.target),
        applicability=projected.applicability,
        snapshot_intact=projected.snapshot_intact,
    )


def observations_for(
    projection: TargetReviewProjection,
) -> tuple[ReviewEvent, ...]:
    """
    What has become true about this review without anybody doing it.

    Empty when the review still applies. See ``review_events`` on why
    these are derived observations rather than published events.
    """

    if projection.current is None:
        return ()

    event = event_for_applicability(
        projection.target, projection.current, projection.applicability
    )

    return () if event is None else (event,)


# --- Reading the pipeline, without touching it ---------------------------


def _require_statement(
    semantic_set: EngineeringSemanticSet | None,
    document_id: int,
    statement_key: str,
) -> EngineeringSemanticStatement:
    if semantic_set is None:
        raise ReviewTargetNotFoundError(
            f"Document '{document_id}' has no interpreted semantics; "
            "there is nothing to review yet.",
            target_key=statement_key,
        )

    statement = semantic_set.statement(statement_key)

    if statement is None:
        raise ReviewTargetNotFoundError(
            f"Statement '{statement_key}' is not in this document's "
            "current interpretation.",
            target_key=statement_key,
        )

    return statement


def _pipeline_state(
    semantics: EngineeringSemanticRepository, target: ReviewTarget
) -> CurrentPipelineState:
    semantic_set = semantics.find_latest_for_document(target.document_id)

    return _state_from_set(semantic_set, target.target_key)


def _state_from_set(
    semantic_set: EngineeringSemanticSet | None, target_key: str
) -> CurrentPipelineState:
    """
    Translates a semantic set into the thin identity the domain compares.

    This function is the whole of the coupling between the two contexts,
    and it is one-way: identity out, nothing in.
    """

    if semantic_set is None:
        return CurrentPipelineState.absent()

    statement = semantic_set.statement(target_key)

    return CurrentPipelineState(
        exists=True,
        target_key_present=statement is not None,
        content_checksum=semantic_set.content_checksum,
        resolution_policy_version=semantic_set.resolution_policy_version,
        fact_policy_version=semantic_set.fact_policy_version,
        semantic_policy_version=semantic_set.semantic_policy_version,
        support_fingerprint=(
            None
            if statement is None
            else fingerprint_support(statement.supporting_fact_keys)
        ),
    )


def _snapshot_of(
    statement: EngineeringSemanticStatement,
    semantic_set: EngineeringSemanticSet,
) -> ReviewSnapshot:
    return ReviewSnapshot(
        content_checksum=semantic_set.content_checksum,
        semantic_rule_id=statement.semantic_rule_id,
        semantic_rule_version=statement.semantic_rule_version,
        semantic_contract_version=statement.semantic_contract_version,
        resolution_policy_version=semantic_set.resolution_policy_version,
        fact_policy_version=semantic_set.fact_policy_version,
        semantic_policy_version=semantic_set.semantic_policy_version,
        support_fingerprint=fingerprint_support(
            statement.supporting_fact_keys
        ),
        support_count=len(statement.supporting_fact_keys),
    )


def _reviewer(identity: AuditIdentity) -> ReviewerIdentity:
    """
    Copied, not referenced.

    An account can be renamed, re-roled or disabled; a review that
    rendered as "user 7" afterwards would have lost what it exists to
    record.
    """

    return ReviewerIdentity(
        user_id=identity.user_id,
        display_name=identity.display_name,
        email=identity.email,
        role=identity.role.value,
    )
