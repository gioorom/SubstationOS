from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.review_workflow.review_status import ReviewStatus


@dataclass(frozen=True, slots=True)
class ReviewComment:
    """
    A reviewer's remark explaining a decision - why a mention was
    rejected, or what needs to change before it can be approved. A
    thin wrapper rather than a bare ``str`` so the concept has one place
    to be validated (``ReviewWorkflowValidator.validate_comment``) and
    so ``REJECTED``/``NEEDS_CHANGES`` decisions can require one without
    every call site re-checking a raw string.
    """

    text: str


@dataclass(frozen=True, slots=True)
class ReviewCandidate:
    """
    One Proposed Claim under human review (Milestone 10.1 - Review
    Workflow). A ``ReviewCandidate`` references an
    ``app.domain.proposed_claims.proposed_claim_models.ProposedClaim``
    by id - it never duplicates the referenced claim's statement
    (subject/predicate/object) or its evidence. It owns only review
    information: status, who decided, when, and any comment.

    Review Workflow no longer references an Engineering Index entry
    directly (that was Milestone 10's shape) - Proposed Claims is now
    the review unit, since one claim may be built from more than one
    Engineering Index entry (evidence) and, unlike an entry, is not tied
    to a single document. There is accordingly no ``document_id`` here
    either: "every candidate touching this document" is a Proposed
    Claims-side query (``ProposedClaimRepository.list_by_document``),
    not a Review Workflow one.

    ``project_id`` mirrors the referenced claim's own ``project_id``
    (the same denormalization ``ProposedClaim``/``IndexEntry`` already
    use), so listing "every candidate for this project" needs no join
    back into Proposed Claims.

    ``id`` is ``None`` for a candidate that has not yet been persisted.
    Frozen and immutable, like every other domain object in this
    codebase (CLAUDE.md SS6): a decision does not mutate a
    ``ReviewCandidate`` in place, it produces a new one
    (``ReviewCandidateFactory.apply_decision``).
    """

    id: int | None
    project_id: int
    proposed_claim_id: int
    status: ReviewStatus
    review_comment: ReviewComment | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """
    One reviewer's decision to move a ``ReviewCandidate`` to a new
    ``ReviewStatus``: who decided, what the outcome is, and why. Applied
    to a candidate via ``ReviewCandidateFactory.apply_decision`` - the
    decision itself carries no reference to the candidate it targets, so
    it stays a small, reusable value object.
    """

    status: ReviewStatus
    reviewed_by: str
    comment: ReviewComment | None


@dataclass(frozen=True, slots=True)
class ReviewHistoryEvent:
    """
    One immutable ledger entry recording a single status change made to
    a ``ReviewCandidate``. Review history is append-only: changing a
    review's outcome again creates a new event, it never edits or
    removes a prior one. ``from_status`` is always the candidate's real
    prior status - the candidate's own ``created_at`` documents the
    (unrecorded) initial ``PENDING`` state, so every event here
    represents an actual decision, not the creation of the candidate.

    ``id`` is ``None`` for an event that has not yet been persisted.
    """

    id: int | None
    review_candidate_id: int
    from_status: ReviewStatus
    to_status: ReviewStatus
    reviewed_by: str
    comment: ReviewComment | None
    occurred_at: datetime
