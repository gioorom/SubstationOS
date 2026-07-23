"""
Application services for the Review Workflow (Milestone 10, reshaped by
Milestone 10.1). Each function is a single use case, orchestrating the
domain (``app.domain.review_workflow``) through the
``ReviewCandidateRepository`` and ``ReviewHistoryRepository`` ports -
never a raw database session.

Review Workflow reviews Proposed Claims, not Engineering Index entries
directly (Milestone 10.1) - it depends on ``ProposedClaimRepository``
(read-only: fetch the claim being reviewed, confirm it exists) and the
Project bounded context's own ``ProjectRepository`` (read-only: confirm
the claim's Project is still mutable). Document-level scope validation
is Proposed Claims' responsibility now, performed once at claim-creation
time - Review Workflow no longer re-derives it, since a claim's evidence
can span more than one document and there is no single document left to
check here. Nothing in this module writes into Proposed Claims, the
Engineering Index, or the Project Knowledge Graph.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.project.project_repository import ProjectRepository
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.domain.review_workflow.review_candidate_repository import (
    ReviewCandidateRepository,
)
from app.domain.review_workflow.review_history_repository import (
    ReviewHistoryRepository,
)
from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_exceptions import (
    DuplicateOpenReviewCandidateError,
    ProjectNotReviewableError,
    ReviewCandidateNotFoundError,
    ReviewedProjectNotFoundError,
    ReviewedProposedClaimNotFoundError,
)
from app.domain.review_workflow.review_workflow_factory import (
    ReviewCandidateFactory,
    ReviewDecisionFactory,
    ReviewHistoryEventFactory,
)
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
    ReviewHistoryEvent,
)


def _require_reviewable_project(
    project_repository: ProjectRepository,
    project_id: int,
) -> None:
    project = project_repository.get_by_id(project_id)

    if project is None:
        raise ReviewedProjectNotFoundError(project_id)

    if not project.is_mutable():
        raise ProjectNotReviewableError(
            project_id,
            project.lifecycle_state,
        )


def create_review_candidate(
    candidate_repository: ReviewCandidateRepository,
    claim_repository: ProposedClaimRepository,
    project_repository: ProjectRepository,
    *,
    proposed_claim_id: int,
    now: datetime,
) -> ReviewCandidate:
    """
    Opens a Review Candidate against an existing Proposed Claim. Raises
    ``ReviewedProposedClaimNotFoundError`` if the claim does not exist,
    ``ProjectNotReviewableError`` if its Project is Archived or Deleted,
    and ``DuplicateOpenReviewCandidateError`` if the claim already has an
    open (``PENDING``/``NEEDS_CHANGES``) candidate - a new review cycle
    for the same claim is only possible once that one reaches a terminal
    outcome.
    """

    claim = claim_repository.get_by_id(proposed_claim_id)

    if claim is None:
        raise ReviewedProposedClaimNotFoundError(proposed_claim_id)

    _require_reviewable_project(project_repository, claim.project_id)

    existing = candidate_repository.get_open_by_claim(proposed_claim_id)

    if existing is not None:
        raise DuplicateOpenReviewCandidateError(
            proposed_claim_id,
            existing.id,  # type: ignore[arg-type]
        )

    candidate = ReviewCandidateFactory.create(
        project_id=claim.project_id,
        proposed_claim_id=proposed_claim_id,
        now=now,
    )

    return candidate_repository.create(candidate)


def _apply_decision(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    project_repository: ProjectRepository,
    *,
    candidate_id: int,
    status: ReviewStatus,
    reviewed_by: str,
    comment: str | None,
    now: datetime,
) -> ReviewCandidate:
    candidate = candidate_repository.get_by_id(candidate_id)

    if candidate is None:
        raise ReviewCandidateNotFoundError(candidate_id)

    # Re-validated on every decision, not only at candidate creation: a
    # Project may have been archived while this candidate sat open.
    _require_reviewable_project(project_repository, candidate.project_id)

    decision = ReviewDecisionFactory.create(
        status=status,
        reviewed_by=reviewed_by,
        comment=comment,
    )

    updated = ReviewCandidateFactory.apply_decision(
        candidate,
        decision,
        now,
    )
    persisted = candidate_repository.update(updated)

    event = ReviewHistoryEventFactory.create(
        review_candidate_id=candidate_id,
        from_status=candidate.status,
        decision=decision,
        occurred_at=now,
    )
    history_repository.append(event)

    return persisted


def approve_review_candidate(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    project_repository: ProjectRepository,
    *,
    candidate_id: int,
    reviewed_by: str,
    comment: str | None = None,
    now: datetime,
) -> ReviewCandidate:
    return _apply_decision(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate_id,
        status=ReviewStatus.APPROVED,
        reviewed_by=reviewed_by,
        comment=comment,
        now=now,
    )


def reject_review_candidate(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    project_repository: ProjectRepository,
    *,
    candidate_id: int,
    reviewed_by: str,
    comment: str | None,
    now: datetime,
) -> ReviewCandidate:
    return _apply_decision(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate_id,
        status=ReviewStatus.REJECTED,
        reviewed_by=reviewed_by,
        comment=comment,
        now=now,
    )


def request_review_changes(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    project_repository: ProjectRepository,
    *,
    candidate_id: int,
    reviewed_by: str,
    comment: str | None,
    now: datetime,
) -> ReviewCandidate:
    return _apply_decision(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate_id,
        status=ReviewStatus.NEEDS_CHANGES,
        reviewed_by=reviewed_by,
        comment=comment,
        now=now,
    )


def resubmit_review_candidate(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    project_repository: ProjectRepository,
    *,
    candidate_id: int,
    reviewed_by: str,
    comment: str | None = None,
    now: datetime,
) -> ReviewCandidate:
    """
    Moves a candidate from ``NEEDS_CHANGES`` back to ``PENDING`` - the
    same candidate, not a new review cycle - once whatever the reviewer
    flagged has been addressed. The only action that targets ``PENDING``
    as an outcome; every other decision (approve/reject/request
    changes) moves a candidate away from it.
    """

    return _apply_decision(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate_id,
        status=ReviewStatus.PENDING,
        reviewed_by=reviewed_by,
        comment=comment,
        now=now,
    )


def get_review_candidate(
    candidate_repository: ReviewCandidateRepository,
    candidate_id: int,
) -> ReviewCandidate:
    candidate = candidate_repository.get_by_id(candidate_id)

    if candidate is None:
        raise ReviewCandidateNotFoundError(candidate_id)

    return candidate


def list_pending_review_candidates(
    candidate_repository: ReviewCandidateRepository,
) -> list[ReviewCandidate]:
    return candidate_repository.list_pending()


def list_review_candidates_for_project(
    candidate_repository: ReviewCandidateRepository,
    project_id: int,
    *,
    status: ReviewStatus | None = None,
) -> list[ReviewCandidate]:
    return candidate_repository.list_by_project(project_id, status=status)


def get_review_history(
    candidate_repository: ReviewCandidateRepository,
    history_repository: ReviewHistoryRepository,
    candidate_id: int,
) -> list[ReviewHistoryEvent]:
    if candidate_repository.get_by_id(candidate_id) is None:
        raise ReviewCandidateNotFoundError(candidate_id)

    return history_repository.list_by_candidate(candidate_id)
