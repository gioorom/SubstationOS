from __future__ import annotations

import pytest

from app.domain.review_workflow.review_status import (
    OPEN_STATUSES,
    TERMINAL_STATUSES,
    ReviewStatus,
    is_transition_valid,
)


def test_review_status_covers_the_minimum_required_states() -> None:
    values = {status.value for status in ReviewStatus}

    assert values == {
        "pending",
        "approved",
        "rejected",
        "needs_changes",
    }


def test_open_and_terminal_statuses_partition_every_status() -> None:
    assert OPEN_STATUSES | TERMINAL_STATUSES == set(ReviewStatus)
    assert OPEN_STATUSES & TERMINAL_STATUSES == set()


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ReviewStatus.PENDING, ReviewStatus.APPROVED),
        (ReviewStatus.PENDING, ReviewStatus.REJECTED),
        (ReviewStatus.PENDING, ReviewStatus.NEEDS_CHANGES),
        (ReviewStatus.NEEDS_CHANGES, ReviewStatus.APPROVED),
        (ReviewStatus.NEEDS_CHANGES, ReviewStatus.REJECTED),
        (ReviewStatus.NEEDS_CHANGES, ReviewStatus.PENDING),
    ],
)
def test_is_transition_valid_accepts_every_open_state_transition(
    current: ReviewStatus,
    target: ReviewStatus,
) -> None:
    assert is_transition_valid(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ReviewStatus.APPROVED, ReviewStatus.PENDING),
        (ReviewStatus.APPROVED, ReviewStatus.REJECTED),
        (ReviewStatus.APPROVED, ReviewStatus.NEEDS_CHANGES),
        (ReviewStatus.REJECTED, ReviewStatus.PENDING),
        (ReviewStatus.REJECTED, ReviewStatus.APPROVED),
        (ReviewStatus.REJECTED, ReviewStatus.NEEDS_CHANGES),
    ],
)
def test_is_transition_valid_rejects_every_transition_out_of_a_terminal_status(
    current: ReviewStatus,
    target: ReviewStatus,
) -> None:
    assert is_transition_valid(current, target) is False
