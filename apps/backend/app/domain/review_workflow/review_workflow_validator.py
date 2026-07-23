from __future__ import annotations

from app.domain.review_workflow.review_status import (
    ReviewStatus,
    is_transition_valid,
)
from app.domain.review_workflow.review_workflow_exceptions import (
    InvalidReviewCommentError,
    InvalidReviewerError,
    InvalidReviewStatusTransitionError,
    ReviewCommentRequiredError,
)
from app.domain.review_workflow.review_workflow_models import ReviewComment

# Decisions whose outcome the document's author needs to act on must
# explain why - see ReviewCommentRequiredError.
_STATUSES_REQUIRING_COMMENT: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.REJECTED,
        ReviewStatus.NEEDS_CHANGES,
    }
)


class ReviewWorkflowValidator:
    """
    Stateless validation rules for the Review Workflow, shared by the
    factory (at decision time) and any future caller building a
    ``ReviewDecision`` directly.
    """

    @staticmethod
    def validate_reviewer(reviewed_by: str) -> None:
        if not reviewed_by or not reviewed_by.strip():
            raise InvalidReviewerError(reviewed_by)

    @staticmethod
    def validate_comment(comment: ReviewComment | None) -> None:
        if comment is not None and not comment.text.strip():
            raise InvalidReviewCommentError(comment.text)

    @staticmethod
    def validate_comment_required_for_status(
        status: ReviewStatus,
        comment: ReviewComment | None,
    ) -> None:
        if status in _STATUSES_REQUIRING_COMMENT and comment is None:
            raise ReviewCommentRequiredError(status)

    @staticmethod
    def validate_transition(
        current: ReviewStatus,
        target: ReviewStatus,
    ) -> None:
        if not is_transition_valid(current, target):
            raise InvalidReviewStatusTransitionError(current, target)
