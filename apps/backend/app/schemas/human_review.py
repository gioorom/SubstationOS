"""
The public Human Review contract.

**Every response is a projection.** There is no `current_decision` field
anywhere that a client could write to, and no `superseded` flag on a
stored record - both are computed from the history on read, and the
schemas below say so in their own shape.

No schema here carries a semantic statement, a fact, an entity or a piece
of evidence. A review names what it is about by key and records the
identity that artefact had; what the artefact *said* is read from the
engineering endpoints, which remain its single account.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.human_review.review_applicability import (
    ReviewApplicability,
)
from app.domain.human_review.review_models import (
    MAX_COMMENT_LENGTH,
    Review,
)
from app.domain.human_review.review_projection import (
    ReviewHistoryEntry,
    TargetReviewProjection,
)
from app.domain.human_review.review_target import ReviewTargetType
from app.domain.human_review.review_vocabulary import (
    ReviewDecision,
    ReviewReason,
)
from app.schemas.pagination import PageMetadata

# --- Requests ------------------------------------------------------------


class RecordReviewRequest(BaseModel):
    """
    One judgement, as a client submits it.

    There is deliberately **no reviewer field**. The actor is the
    authenticated identity, resolved by the security layer; a body that
    could name a reviewer would be a body in which a caller could claim
    to be somebody else, which is the exact failure EPIC 30.3 removed
    from project creation.

    There is likewise no target field: the statement is named by the URL,
    so a review cannot be submitted against one artefact while claiming
    to be about another.
    """

    decision: ReviewDecision
    reason: ReviewReason
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)


# --- Responses -----------------------------------------------------------


class ReviewerRead(BaseModel):
    """
    Who reviewed, as they were at the moment of reviewing.

    Copied onto the review rather than joined from ``users``, so the
    record stays readable after an account is renamed, re-roled or
    disabled. Carries no credential; there is no field here for one.
    """

    user_id: int
    display_name: str
    email: str
    role: str


class ReviewSnapshotRead(BaseModel):
    """
    The identity the reviewed artefact had, at review time.

    Identity only - which bytes, which rules, which policies, and a
    fingerprint over the support chain. Not the artefact: what the
    statement said is read from the semantic endpoints, which stay its
    single account.
    """

    content_checksum: str
    semantic_rule_id: str
    semantic_rule_version: str
    semantic_contract_version: str
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    support_fingerprint: str
    support_count: int

    model_config = ConfigDict(from_attributes=True)


class ReviewRead(BaseModel):
    """One recorded judgement, exactly as it was written."""

    review_id: int
    target_type: ReviewTargetType
    target_key: str
    document_id: int
    decision: ReviewDecision
    reason: ReviewReason
    comment: str | None
    reviewer: ReviewerRead
    snapshot: ReviewSnapshotRead
    recorded_at: datetime
    record_version: str

    @classmethod
    def of(cls, review: Review) -> "ReviewRead":
        return cls(
            review_id=review.review_id,
            target_type=review.target.target_type,
            target_key=review.target.target_key,
            document_id=review.target.document_id,
            decision=review.decision,
            reason=review.reason,
            comment=None if review.comment is None else review.comment.text,
            reviewer=ReviewerRead(
                user_id=review.reviewer.user_id,
                display_name=review.reviewer.display_name,
                email=review.reviewer.email,
                role=review.reviewer.role,
            ),
            snapshot=ReviewSnapshotRead.model_validate(review.snapshot),
            recorded_at=review.recorded_at,
            record_version=review.record_version,
        )


class CurrentReviewRead(BaseModel):
    """
    The effective decision for one statement.

    ``current`` is ``null`` for a statement nobody has reviewed - a
    distinct state from every decision, and never to be rendered as one.

    ``applicability`` says whether that judgement still describes today's
    pipeline. It is computed on every read from the review's snapshot and
    the document's current interpretation; it is not stored, and there is
    no column it could drift from.
    """

    target_type: ReviewTargetType
    target_key: str
    document_id: int
    current: ReviewRead | None
    review_count: int
    applicability: ReviewApplicability

    snapshot_intact: bool = Field(
        description=(
            "False only if a statement kept its key and changed its "
            "support, which should be impossible. A false here means an "
            "engineering artefact's identity has stopped meaning what it "
            "claims, and is worth investigating rather than ignoring."
        )
    )

    @classmethod
    def of(cls, projection: TargetReviewProjection) -> "CurrentReviewRead":
        return cls(
            target_type=projection.target.target_type,
            target_key=projection.target.target_key,
            document_id=projection.target.document_id,
            current=(
                None
                if projection.current is None
                else ReviewRead.of(projection.current)
            ),
            review_count=projection.review_count,
            applicability=projection.applicability,
            snapshot_intact=projection.snapshot_intact,
        )


class ReviewHistoryEntryRead(BaseModel):
    """
    One review, plus what it now means.

    ``superseded`` is derived from position in the newest-first history,
    never from a stored flag: writing one would mean modifying an
    immutable record.
    """

    review: ReviewRead
    superseded: bool
    applicability: ReviewApplicability

    @classmethod
    def of(cls, entry: ReviewHistoryEntry) -> "ReviewHistoryEntryRead":
        return cls(
            review=ReviewRead.of(entry.review),
            superseded=entry.superseded,
            applicability=entry.applicability,
        )


class ReviewHistoryResponse(BaseModel):
    """One page of a statement's history, newest first."""

    items: tuple[ReviewHistoryEntryRead, ...]
    pagination: PageMetadata


class DocumentReviewSummaryResponse(BaseModel):
    """
    The current decision for every reviewed statement in one document.

    One request, so a Workspace listing two hundred statements does not
    make two hundred more. Statements nobody has reviewed are simply
    absent - the client treats an absent key as "never reviewed", which
    is what it is.
    """

    document_id: int
    items: tuple[CurrentReviewRead, ...]


class ReviewVocabularyResponse(BaseModel):
    """
    Which reasons may accompany which decision.

    Served rather than duplicated in the frontend: a client that
    hard-coded the pairing would eventually offer a combination the
    backend refuses, and the reviewer would discover it on submit.
    """

    decisions: tuple[ReviewDecision, ...]
    reasons_by_decision: dict[ReviewDecision, tuple[ReviewReason, ...]]
    decisions_requiring_comment: tuple[ReviewDecision, ...]
