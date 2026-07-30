"""
What makes a review admissible.

Three rules, each of which exists because its absence produces a record
nobody can act on:

1. **A reason is always required**, from the closed catalogue. A decision
   with no stated grounds cannot be aggregated, cannot be argued with,
   and cannot be explained to whoever inherits the project.
2. **The reason must fit the decision.** "Approved because the
   interpretation is incorrect" is a sentence the trail must not be able
   to contain.
3. **A comment is required where the reason alone does not explain
   anything**: for ``OTHER``, which says only that the catalogue did not
   fit, and for ``REJECTED`` and ``NEEDS_INVESTIGATION``, where the next
   engineer's whole question is *what did you see?*

An approval under a catalogued reason may stand alone. Requiring prose
for the common, uncontroversial case is how a review process becomes
something engineers work around.

Every function here is pure: enums and an optional comment in, violations
out. No request, no database, no clock.
"""

from __future__ import annotations

from app.domain.human_review.review_exceptions import (
    ReviewPolicyViolationError,
)
from app.domain.human_review.review_models import ReviewComment
from app.domain.human_review.review_vocabulary import (
    ReviewDecision,
    ReviewReason,
    reason_permitted,
    reasons_for,
)

#: Decisions whose grounds are never self-evident from the reason alone.
DECISIONS_REQUIRING_COMMENT = frozenset(
    {
        ReviewDecision.REJECTED,
        ReviewDecision.NEEDS_INVESTIGATION,
    }
)


def requires_comment(
    decision: ReviewDecision, reason: ReviewReason
) -> bool:
    """Whether this pairing may be recorded without prose."""

    return (
        decision in DECISIONS_REQUIRING_COMMENT
        or reason is ReviewReason.OTHER
    )


def check(
    decision: ReviewDecision,
    reason: ReviewReason,
    comment: ReviewComment | None,
) -> None:
    """
    Raises ``ReviewPolicyViolationError`` if the review may not be
    recorded.

    Violations are collected and reported together: a reviewer should
    learn everything wrong with their submission in one attempt, not one
    round trip at a time.
    """

    violations: list[str] = []

    if not reason_permitted(decision, reason):
        permitted = ", ".join(
            sorted(item.value for item in reasons_for(decision))
        )

        violations.append(
            f"'{reason.value}' is not a reason for a "
            f"'{decision.value}' decision. Permitted: {permitted}."
        )

    if requires_comment(decision, reason) and comment is None:
        violations.append(
            f"A '{decision.value}' decision with reason "
            f"'{reason.value}' requires a comment explaining it."
        )

    if violations:
        raise ReviewPolicyViolationError(
            "This review does not satisfy the review policy.",
            violations=tuple(violations),
        )
