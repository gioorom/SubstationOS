from __future__ import annotations

import pytest

from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_exceptions import (
    InvalidReviewCommentError,
    InvalidReviewerError,
    InvalidReviewStatusTransitionError,
    ReviewCommentRequiredError,
)
from app.domain.review_workflow.review_workflow_models import ReviewComment
from app.domain.review_workflow.review_workflow_validator import (
    ReviewWorkflowValidator,
)


@pytest.mark.parametrize("reviewed_by", ["", "   ", "\t"])
def test_validate_reviewer_rejects_blank_values(reviewed_by: str) -> None:
    with pytest.raises(InvalidReviewerError):
        ReviewWorkflowValidator.validate_reviewer(reviewed_by)


def test_validate_reviewer_accepts_a_real_identity() -> None:
    ReviewWorkflowValidator.validate_reviewer("engineer@acme.com")


def test_validate_comment_accepts_none() -> None:
    ReviewWorkflowValidator.validate_comment(None)


def test_validate_comment_accepts_real_text() -> None:
    ReviewWorkflowValidator.validate_comment(
        ReviewComment(text="Missing rated voltage on the nameplate.")
    )


def test_validate_comment_rejects_blank_text() -> None:
    with pytest.raises(InvalidReviewCommentError):
        ReviewWorkflowValidator.validate_comment(ReviewComment(text="   "))


def test_validate_comment_required_for_status_accepts_approved_with_no_comment() -> (
    None
):
    ReviewWorkflowValidator.validate_comment_required_for_status(
        ReviewStatus.APPROVED,
        None,
    )


@pytest.mark.parametrize(
    "status",
    [ReviewStatus.REJECTED, ReviewStatus.NEEDS_CHANGES],
)
def test_validate_comment_required_for_status_rejects_no_comment(
    status: ReviewStatus,
) -> None:
    with pytest.raises(ReviewCommentRequiredError):
        ReviewWorkflowValidator.validate_comment_required_for_status(
            status,
            None,
        )


def test_validate_comment_required_for_status_accepts_rejected_with_a_comment() -> (
    None
):
    ReviewWorkflowValidator.validate_comment_required_for_status(
        ReviewStatus.REJECTED,
        ReviewComment(text="Identifier does not match the drawing."),
    )


def test_validate_transition_accepts_a_valid_transition() -> None:
    ReviewWorkflowValidator.validate_transition(
        ReviewStatus.PENDING,
        ReviewStatus.APPROVED,
    )


def test_validate_transition_rejects_an_invalid_transition() -> None:
    with pytest.raises(InvalidReviewStatusTransitionError):
        ReviewWorkflowValidator.validate_transition(
            ReviewStatus.APPROVED,
            ReviewStatus.PENDING,
        )
