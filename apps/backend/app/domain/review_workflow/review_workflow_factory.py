from __future__ import annotations

from datetime import datetime

from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
    ReviewComment,
    ReviewDecision,
    ReviewHistoryEvent,
)
from app.domain.review_workflow.review_workflow_validator import (
    ReviewWorkflowValidator,
)


class ReviewCandidateFactory:
    """
    Builds and transitions ``ReviewCandidate`` instances, enforcing
    invariants at construction time (CLAUDE.md SS4.2). Because
    ``ReviewCandidate`` is frozen, "transitioning" one does not mutate
    it - ``apply_decision`` returns a new instance in the target status.
    """

    @staticmethod
    def create(
        *,
        project_id: int,
        proposed_claim_id: int,
        now: datetime,
    ) -> ReviewCandidate:
        return ReviewCandidate(
            id=None,
            project_id=project_id,
            proposed_claim_id=proposed_claim_id,
            status=ReviewStatus.PENDING,
            review_comment=None,
            reviewed_by=None,
            reviewed_at=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def apply_decision(
        candidate: ReviewCandidate,
        decision: ReviewDecision,
        now: datetime,
    ) -> ReviewCandidate:
        """
        Validates ``decision`` against ``candidate``'s current status
        and returns the new ``ReviewCandidate`` state - it does not
        persist anything or record history; that is the service's job.
        """

        ReviewWorkflowValidator.validate_reviewer(decision.reviewed_by)
        ReviewWorkflowValidator.validate_comment(decision.comment)
        ReviewWorkflowValidator.validate_comment_required_for_status(
            decision.status,
            decision.comment,
        )
        ReviewWorkflowValidator.validate_transition(
            candidate.status,
            decision.status,
        )

        return ReviewCandidate(
            id=candidate.id,
            project_id=candidate.project_id,
            proposed_claim_id=candidate.proposed_claim_id,
            status=decision.status,
            review_comment=decision.comment,
            reviewed_by=decision.reviewed_by,
            reviewed_at=now,
            created_at=candidate.created_at,
            updated_at=now,
        )


class ReviewDecisionFactory:
    """
    Builds a ``ReviewDecision`` from raw input (e.g. an API request
    body), enforcing invariants (reviewer identity, comment shape) at
    construction time - independent of whatever candidate it will later
    be applied to.
    """

    @staticmethod
    def create(
        *,
        status: ReviewStatus,
        reviewed_by: str,
        comment: str | None = None,
    ) -> ReviewDecision:
        ReviewWorkflowValidator.validate_reviewer(reviewed_by)

        review_comment = (
            ReviewComment(text=comment) if comment is not None else None
        )
        ReviewWorkflowValidator.validate_comment(review_comment)

        return ReviewDecision(
            status=status,
            reviewed_by=reviewed_by,
            comment=review_comment,
        )


class ReviewHistoryEventFactory:
    """
    Builds the immutable ``ReviewHistoryEvent`` a decision produces.
    """

    @staticmethod
    def create(
        *,
        review_candidate_id: int,
        from_status: ReviewStatus,
        decision: ReviewDecision,
        occurred_at: datetime,
    ) -> ReviewHistoryEvent:
        return ReviewHistoryEvent(
            id=None,
            review_candidate_id=review_candidate_id,
            from_status=from_status,
            to_status=decision.status,
            reviewed_by=decision.reviewed_by,
            comment=decision.comment,
            occurred_at=occurred_at,
        )
