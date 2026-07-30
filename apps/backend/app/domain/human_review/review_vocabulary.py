"""
The closed vocabularies a review is expressed in.

Three decisions and eight reasons, and no way to add a ninth at a call
site. A free-text decision would make "how many statements are rejected?"
unanswerable; a free-text reason would make "why does this pipeline get
rejected?" unanswerable, which is the question the catalogue exists to
answer in aggregate.

**The vocabulary is deliberately not a workflow.** There is no
transition table, no assignment, no escalation and no approval chain. A
review is one engineer's judgement at one moment, and a later judgement
is another review - see ``review_models``.

---

**The pipeline is not right or wrong.** Nothing here says `correct` or
`incorrect` *about the pipeline*: it says what an engineer decided about
one interpreted statement. `INCORRECT_INTERPRETATION` names a defect in
one interpretation, which is a finding an engineer can make; it is not a
verdict on the rules that produced it.
"""

from __future__ import annotations

from enum import Enum


class ReviewDecision(str, Enum):
    """
    What an engineer decided.

    Three, and no custom states. ``NEEDS_INVESTIGATION`` is not a
    half-approval and not a soft rejection: it is a reviewer recording
    that they looked and could not yet decide, which is a real
    engineering outcome and the one a workflow engine would have turned
    into a queue.
    """

    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INVESTIGATION = "needs_investigation"


class ReviewReason(str, Enum):
    """
    Why. Catalogued, so the answer is aggregatable.

    A reason is **required** on every review. Recording a judgement with
    no stated grounds produces a decision nobody can act on six months
    later, which is the failure mode this whole context exists to
    prevent.
    """

    #: The interpretation matches what the source document states.
    CONFIRMED_BY_SOURCE = "confirmed_by_source"

    #: The interpretation is consistent with the installation's design.
    CONSISTENT_WITH_DESIGN = "consistent_with_design"

    #: The rule read the source and drew the wrong meaning from it.
    INCORRECT_INTERPRETATION = "incorrect_interpretation"

    #: The supporting evidence admits more than one reading.
    AMBIGUOUS_EVIDENCE = "ambiguous_evidence"

    #: There is not enough evidence to sustain the statement either way.
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

    #: The rules cannot express what this document says. A finding about
    #: the catalogue, recorded here so it can be counted.
    PIPELINE_LIMITATION = "pipeline_limitation"

    #: Correct for this installation despite looking wrong in general.
    ENGINEERING_EXCEPTION = "engineering_exception"

    #: The source document itself is wrong, unclear or out of date.
    DOCUMENTATION_ISSUE = "documentation_issue"

    #: None of the above. **Always requires a comment** - see
    #: ``review_policy``.
    OTHER = "other"


#: Which reasons may accompany which decision.
#:
#: A closed vocabulary that admitted every reason for every decision
#: would let "approved because the interpretation is incorrect" be
#: recorded, and a trail containing that sentence is worse than one
#: containing nothing. The pairing is a domain rule, enforced at
#: construction and tested.
REASONS_FOR_DECISION: dict[ReviewDecision, frozenset[ReviewReason]] = {
    ReviewDecision.APPROVED: frozenset(
        {
            ReviewReason.CONFIRMED_BY_SOURCE,
            ReviewReason.CONSISTENT_WITH_DESIGN,
            ReviewReason.ENGINEERING_EXCEPTION,
            ReviewReason.OTHER,
        }
    ),
    ReviewDecision.REJECTED: frozenset(
        {
            ReviewReason.INCORRECT_INTERPRETATION,
            ReviewReason.INSUFFICIENT_EVIDENCE,
            ReviewReason.PIPELINE_LIMITATION,
            ReviewReason.DOCUMENTATION_ISSUE,
            ReviewReason.OTHER,
        }
    ),
    ReviewDecision.NEEDS_INVESTIGATION: frozenset(
        {
            ReviewReason.AMBIGUOUS_EVIDENCE,
            ReviewReason.INSUFFICIENT_EVIDENCE,
            ReviewReason.PIPELINE_LIMITATION,
            ReviewReason.DOCUMENTATION_ISSUE,
            ReviewReason.OTHER,
        }
    ),
}


def reasons_for(decision: ReviewDecision) -> frozenset[ReviewReason]:
    """Every reason that may accompany ``decision``. Total over the enum."""

    return REASONS_FOR_DECISION[decision]


def reason_permitted(
    decision: ReviewDecision, reason: ReviewReason
) -> bool:
    """A pure function of two enums. No request, no database, no clock."""

    return reason in REASONS_FOR_DECISION[decision]
