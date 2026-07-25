from __future__ import annotations

import pytest

from app.domain.canonicalization.canonicalization_exceptions import (
    CrossProjectCanonicalizationError,
    ReviewCandidateNotApprovedError,
)
from app.domain.canonicalization.canonicalization_validator import (
    CanonicalizationValidator,
)
from app.domain.review_workflow.review_status import ReviewStatus


def test_validate_approved_accepts_an_approved_status() -> None:
    CanonicalizationValidator.validate_approved(1, ReviewStatus.APPROVED)


@pytest.mark.parametrize(
    "status",
    [
        ReviewStatus.PENDING,
        ReviewStatus.REJECTED,
        ReviewStatus.NEEDS_CHANGES,
    ],
)
def test_validate_approved_rejects_every_other_status(
    status: ReviewStatus,
) -> None:
    with pytest.raises(ReviewCandidateNotApprovedError):
        CanonicalizationValidator.validate_approved(1, status)


def test_validate_same_project_accepts_matching_projects() -> None:
    CanonicalizationValidator.validate_same_project(10, 10)


def test_validate_same_project_rejects_a_mismatch() -> None:
    with pytest.raises(CrossProjectCanonicalizationError):
        CanonicalizationValidator.validate_same_project(10, 20)
