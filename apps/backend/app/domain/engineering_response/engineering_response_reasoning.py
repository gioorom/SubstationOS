"""
Reporting a derived conclusion inside an engineering response
(EPIC 32.1, extended by EPIC 32.2).

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

## Structural conclusions warn differently, and never about conflict

`ESTABLISHED` raises no warning. `AMBIGUOUS` and `INSUFFICIENT_KNOWLEDGE`
reuse the existing categories, which already mean what those outcomes
mean.

`CONFLICTING_KNOWLEDGE` is **never** raised for a structural conclusion.
Two assets whose governed locations differ are not two approved
statements contradicting each other - the graph is partial and location
identity is document-scoped, so they may well be in one room. Calling
that a conflict would send somebody hunting a documentation error that
does not exist.

The three warnings map to **three different categories**, deliberately.
Collapsing "the knowledge conflicts", "the question was ambiguous" and
"the knowledge is missing" into one "not consistent" warning would erase
exactly the distinction the four-valued outcome exists to preserve.
"""

from __future__ import annotations

from app.domain.engineering_reasoning.reasoning_models import ReasoningResult
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningOutcome,
    StructuralReasoningOutcome,
)
from app.domain.engineering_response.engineering_response_models import (
    DerivedReasoningAssessment,
    DerivedReasoningSupport,
    EngineeringWarning,
    EngineeringWarningCategory,
    SharedStructuralLocationReport,
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
        structural=_structural_report(reasoning),
    )


def _structural_report(
    reasoning: ReasoningResult,
) -> SharedStructuralLocationReport | None:
    """
    The structural half, restated - or ``None`` for a family that has
    none.

    Copies governed identities and copies **no meaning**: the derived
    relationship is whatever the rule concluded, and it is ``None``
    unless the rule established it.
    """

    assessment = reasoning.structural

    if assessment is None:
        return None

    path = assessment.inference_path

    return SharedStructuralLocationReport(
        derived_relationship=assessment.derived_relationship,
        shared_location_node_id=assessment.shared_location_node_id,
        shared_location_label=assessment.shared_location_label,
        left_asset_node_id=reasoning.query.left_asset_node_id,
        right_asset_node_id=reasoning.query.right_asset_node_id,
        inference_path=(
            () if path is None else path.governed_identities
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

    if isinstance(reasoning.outcome, StructuralReasoningOutcome):
        return _structural_warnings(reasoning, question)

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


def _structural_warnings(
    reasoning: ReasoningResult, question: str
) -> tuple[EngineeringWarning, ...]:
    """
    The warnings a structural conclusion obliges this response to state.

    Two of the three outcomes warn, and the mapping reuses the existing
    categories rather than inventing structural ones: what a reader must
    act on is that the question was ambiguous, or that governed knowledge
    did not answer it - which is what those categories already mean.

    **`CONFLICTING_KNOWLEDGE` is deliberately not used.** Nothing this
    rule can conclude is a conflict: two assets in different governed
    locations are not approved statements that contradict each other,
    they are two statements that simply do not answer the question
    together. Reporting that as a conflict would send an engineer looking
    for a documentation error that does not exist.

    `ESTABLISHED` raises no warning: there is nothing for a reader to act
    on.
    """

    if reasoning.outcome is StructuralReasoningOutcome.AMBIGUOUS:
        return (
            EngineeringWarning(
                category=EngineeringWarningCategory.AMBIGUOUS_KNOWLEDGE,
                message=(
                    f"'{question}' could not be answered as one question: "
                    "the governed knowledge resolved to more than one "
                    "possibility, and reasoning does not choose between "
                    "them."
                ),
            ),
        )

    if (
        reasoning.outcome
        is StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE
    ):
        return (
            EngineeringWarning(
                category=EngineeringWarningCategory.INSUFFICIENT_EVIDENCE,
                message=(
                    f"Governed knowledge does not establish '{question}'. "
                    "This is not a finding that they are apart: no "
                    "governed statement places them together, and the "
                    "graph records only what documents state and "
                    "engineers have approved."
                ),
            ),
        )

    return ()
