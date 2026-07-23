from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_exceptions import (
    InvalidReviewerError,
    InvalidReviewStatusTransitionError,
    ReviewCommentRequiredError,
)
from app.domain.review_workflow.review_workflow_factory import (
    ReviewCandidateFactory,
    ReviewDecisionFactory,
    ReviewHistoryEventFactory,
)
from app.domain.review_workflow.review_workflow_models import ReviewComment

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
DECIDED_AT = datetime(2026, 1, 2, 9, 30, 0)


def test_review_candidate_factory_creates_an_unpersisted_pending_candidate() -> (
    None
):
    candidate = ReviewCandidateFactory.create(
        project_id=10,
        proposed_claim_id=7,
        now=CREATED_AT,
    )

    assert candidate.id is None
    assert candidate.project_id == 10
    assert candidate.proposed_claim_id == 7
    assert candidate.status is ReviewStatus.PENDING
    assert candidate.review_comment is None
    assert candidate.reviewed_by is None
    assert candidate.reviewed_at is None
    assert candidate.created_at == CREATED_AT
    assert candidate.updated_at == CREATED_AT


def test_review_decision_factory_builds_a_decision_with_a_wrapped_comment() -> (
    None
):
    decision = ReviewDecisionFactory.create(
        status=ReviewStatus.REJECTED,
        reviewed_by="engineer@acme.com",
        comment="Identifier does not match the drawing.",
    )

    assert decision.status is ReviewStatus.REJECTED
    assert decision.reviewed_by == "engineer@acme.com"
    assert decision.comment == ReviewComment(
        text="Identifier does not match the drawing."
    )


def test_review_decision_factory_rejects_a_blank_reviewer() -> None:
    with pytest.raises(InvalidReviewerError):
        ReviewDecisionFactory.create(
            status=ReviewStatus.APPROVED,
            reviewed_by="   ",
        )


def test_apply_decision_moves_a_pending_candidate_to_approved() -> None:
    candidate = ReviewCandidateFactory.create(
        project_id=10,
        proposed_claim_id=7,
        now=CREATED_AT,
    )
    decision = ReviewDecisionFactory.create(
        status=ReviewStatus.APPROVED,
        reviewed_by="engineer@acme.com",
    )

    updated = ReviewCandidateFactory.apply_decision(
        candidate,
        decision,
        DECIDED_AT,
    )

    assert updated.id == candidate.id
    assert updated.status is ReviewStatus.APPROVED
    assert updated.reviewed_by == "engineer@acme.com"
    assert updated.reviewed_at == DECIDED_AT
    assert updated.created_at == CREATED_AT
    assert updated.updated_at == DECIDED_AT
    # The candidate itself is never mutated - a new instance is
    # returned.
    assert candidate.status is ReviewStatus.PENDING


def test_apply_decision_rejects_a_terminal_to_terminal_transition() -> None:
    candidate = ReviewCandidateFactory.create(
        project_id=10,
        proposed_claim_id=7,
        now=CREATED_AT,
    )
    approved = ReviewCandidateFactory.apply_decision(
        candidate,
        ReviewDecisionFactory.create(
            status=ReviewStatus.APPROVED,
            reviewed_by="engineer@acme.com",
        ),
        DECIDED_AT,
    )

    with pytest.raises(InvalidReviewStatusTransitionError):
        ReviewCandidateFactory.apply_decision(
            approved,
            ReviewDecisionFactory.create(
                status=ReviewStatus.PENDING,
                reviewed_by="engineer@acme.com",
            ),
            DECIDED_AT,
        )


def test_apply_decision_rejects_a_rejection_with_no_comment() -> None:
    candidate = ReviewCandidateFactory.create(
        project_id=10,
        proposed_claim_id=7,
        now=CREATED_AT,
    )
    decision = ReviewDecisionFactory.create(
        status=ReviewStatus.REJECTED,
        reviewed_by="engineer@acme.com",
    )

    with pytest.raises(ReviewCommentRequiredError):
        ReviewCandidateFactory.apply_decision(
            candidate,
            decision,
            DECIDED_AT,
        )


def test_review_history_event_factory_records_the_prior_status() -> None:
    decision = ReviewDecisionFactory.create(
        status=ReviewStatus.NEEDS_CHANGES,
        reviewed_by="engineer@acme.com",
        comment="Please confirm the rated voltage.",
    )

    event = ReviewHistoryEventFactory.create(
        review_candidate_id=42,
        from_status=ReviewStatus.PENDING,
        decision=decision,
        occurred_at=DECIDED_AT,
    )

    assert event.id is None
    assert event.review_candidate_id == 42
    assert event.from_status is ReviewStatus.PENDING
    assert event.to_status is ReviewStatus.NEEDS_CHANGES
    assert event.reviewed_by == "engineer@acme.com"
    assert event.comment == ReviewComment(
        text="Please confirm the rated voltage."
    )
    assert event.occurred_at == DECIDED_AT
