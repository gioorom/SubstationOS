"""
Reporting a derived conclusion inside an engineering response
(EPIC 32.1).

This module does **no reasoning**. The conclusion was already reached by
a versioned rule in `app.domain.engineering_reasoning`; everything here
reads that result and restates it in the response's own vocabulary. It
evaluates no comparison, resolves no ambiguity, and never turns
`INSUFFICIENT_KNOWLEDGE` into an answer.

---

## Why the outcome becomes a warning as well as a field

`DerivedReasoningAssessment` is the machine-readable record. The
warnings are what a reader sees. Three of the four outcomes say
something a reader must not miss:

- `INCONSISTENT` - reviewed knowledge disagrees with itself. Somebody
  has to fix the source, and no answer written on top of it is safe
  until they do.
- `AMBIGUOUS` - the question named more than one piece of equipment, so
  an answer may silently describe the wrong one.
- `INSUFFICIENT_KNOWLEDGE` - the governed graph does not contain what
  the question needed. The honest report is the gap, not a conclusion.

`CONSISTENT` raises no warning: there is nothing for a reader to act on.

The three warnings map to **three different categories**, deliberately.
Collapsing "the knowledge conflicts", "the question was ambiguous" and
"the knowledge is missing" into one "not consistent" warning would erase
exactly the distinction the four-valued outcome exists to preserve.
"""

from __future__ import annotations

from app.domain.engineering_reasoning.reasoning_models import ReasoningResult
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningOutcome,
)
from app.domain.engineering_response.engineering_response_models import (
    DerivedReasoningAssessment,
    DerivedReasoningSupport,
    EngineeringWarning,
    EngineeringWarningCategory,
)


def _support(contributor) -> DerivedReasoningSupport:
    """One governed fact, restated. Every value is copied off the
    contributor unchanged - no rounding, no unit conversion, no
    normalisation. A governed quantity is reported exactly as
    governed."""

    return DerivedReasoningSupport(
        node_id=contributor.node_id,
        edge_id=contributor.edge_id,
        label=contributor.label,
        value=None if contributor.value is None else str(contributor.value),
        unit=contributor.unit,
        statement_key=contributor.statement_key,
        review_id=contributor.review_id,
        reviewer_display_name=contributor.reviewer_display_name,
        document_id=contributor.document_id,
    )


def build_derived_reasoning_assessment(
    reasoning: ReasoningResult | None,
) -> DerivedReasoningAssessment | None:
    """``None`` in, ``None`` out: a workflow that did not reason reports
    no derived reasoning, rather than reporting an empty conclusion."""

    if reasoning is None:
        return None

    return DerivedReasoningAssessment(
        outcome=reasoning.outcome,
        rule_id=reasoning.rule.rule_id,
        rule_version=reasoning.rule.rule_version,
        rule_family=reasoning.rule.family,
        diagnostic_code=reasoning.diagnostics.code,
        question=reasoning.query.question,
        result_id=reasoning.result_id,
        reasoning_policy_version=reasoning.reasoning_policy_version,
        supports=tuple(
            _support(contributor) for contributor in reasoning.contributors
        ),
    )


def build_derived_reasoning_warnings(
    reasoning: ReasoningResult | None,
) -> tuple[EngineeringWarning, ...]:
    """The warnings the outcome obliges this response to state.

    At most one, because one reasoning result has exactly one outcome.
    """

    if reasoning is None:
        return ()

    question = reasoning.query.question

    if reasoning.outcome is ReasoningOutcome.INCONSISTENT:
        values = ", ".join(
            sorted(
                {
                    f"{contributor.value} {contributor.unit or ''}".strip()
                    for contributor in reasoning.contributors
                    if contributor.value is not None
                }
            )
        )
        return (
            EngineeringWarning(
                category=EngineeringWarningCategory.CONFLICTING_KNOWLEDGE,
                message=(
                    f"Governed knowledge disagrees with itself on "
                    f"'{question}': {values}. Both values are approved, so "
                    "this conflict has to be resolved at the source."
                ),
            ),
        )

    if reasoning.outcome is ReasoningOutcome.AMBIGUOUS:
        return (
            EngineeringWarning(
                category=EngineeringWarningCategory.AMBIGUOUS_KNOWLEDGE,
                message=(
                    f"'{question}' named more than one governed piece of "
                    "equipment, which were not merged. No conclusion was "
                    "derived, and this answer may describe more than one "
                    "of them."
                ),
            ),
        )

    if reasoning.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE:
        return (
            EngineeringWarning(
                category=EngineeringWarningCategory.INSUFFICIENT_EVIDENCE,
                message=(
                    f"No conclusion could be derived for '{question}': the "
                    "governed knowledge available did not cover it "
                    f"({reasoning.diagnostics.code.value})."
                ),
            ),
        )

    return ()
