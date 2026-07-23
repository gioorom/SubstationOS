from __future__ import annotations

from enum import Enum


class ReviewStatus(str, Enum):
    """
    The lifecycle state of one Review Candidate (Milestone 10 - Review
    Workflow). Separate from, and never merged with, the Engineering
    Index entry it reviews (ADR-0002): the Index stays a flat,
    unreviewed inventory: this enum is where "reviewed or not, and how"
    lives instead.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


# States in which a candidate still awaits a final decision. A
# duplicate-open-candidate check (ReviewWorkflowService) treats these,
# and only these, as "already under review" for a given Engineering
# Index entry.
OPEN_STATUSES: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.PENDING,
        ReviewStatus.NEEDS_CHANGES,
    }
)

# Once a candidate is APPROVED or REJECTED, it is closed: reaching a
# different outcome requires an explicit new review cycle (a new
# ReviewCandidate against the same Engineering Index entry), never a
# transition out of a terminal state on the same candidate.
TERMINAL_STATUSES: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
    }
)

# PENDING and NEEDS_CHANGES both accept every decision, including each
# other - NEEDS_CHANGES is a mid-cycle detour a reviewer can revisit,
# not a dead end. APPROVED and REJECTED accept nothing: they are
# terminal for this candidate.
VALID_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.PENDING: frozenset(
        {
            ReviewStatus.APPROVED,
            ReviewStatus.REJECTED,
            ReviewStatus.NEEDS_CHANGES,
        }
    ),
    ReviewStatus.NEEDS_CHANGES: frozenset(
        {
            ReviewStatus.APPROVED,
            ReviewStatus.REJECTED,
            ReviewStatus.PENDING,
        }
    ),
    ReviewStatus.APPROVED: frozenset(),
    ReviewStatus.REJECTED: frozenset(),
}


def is_transition_valid(
    current: ReviewStatus,
    target: ReviewStatus,
) -> bool:
    return target in VALID_TRANSITIONS[current]
