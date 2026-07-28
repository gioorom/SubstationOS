"""
Reading the outcome of an engineering comparison (Milestone 24.2).

The same declared-protocol device Milestone 24.1 established for
verification verdicts, applied to a second question: Prompt Builder asks
the model to open its answer with one of three declared tokens, and this
module matches the first line against those three literals, imported from
Prompt Builder rather than restated. Nothing beyond the first line is
examined; a non-matching line yields **no outcome** rather than an
inferred one.

**The structural bound is stronger here than for verification.** A
comparison whose *either* side retrieved no evidence is forced to
``INSUFFICIENT_EVIDENCE``, whatever the model wrote.

That matters more than it might look. Given evidence for T1 and none for
T2, a fluent model will happily produce "T2 lacks the differential
protection that T1 has" - which reads as an engineering finding but is
really a statement about what the project's reviewed knowledge happens to
cover. An engineer acting on it would be commissioning a change on the
strength of a gap in an index. Absence of retrieved evidence is not
evidence of absence, and this is the one place the system can enforce
that rather than merely instruct it.
"""

from __future__ import annotations

from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
)
from app.domain.engineering_response.engineering_response_models import (
    ComparisonAssessment,
    ComparisonOutcome,
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
)
from app.domain.prompt_builder.composition_policy import (
    COMPARISON_OUTCOME_TOKENS,
)

_OUTCOME_BY_TOKEN: dict[str, ComparisonOutcome] = {
    token: ComparisonOutcome(token.lower())
    for token in COMPARISON_OUTCOME_TOKENS
}


def _first_text_line(
    content: tuple[EngineeringResponseSourceContent, ...],
) -> str | None:
    for block in content:
        if not block.is_supported_text or not block.text:
            continue

        for line in block.text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped

        return None

    return None


def read_declared_outcome(
    source: EngineeringResponseSourceEnvelope,
) -> ComparisonOutcome | None:
    """The declared outcome, or ``None`` if the answer's first line is not
    exactly one of the three declared tokens. Tolerates a trailing colon
    or full stop, and nothing else - a token *inside* a sentence is not a
    declared outcome."""

    line = _first_text_line(source.content)
    if line is None:
        return None

    return _OUTCOME_BY_TOKEN.get(line.rstrip(":.").strip().upper())


def assess_comparison(
    comparison: ComparisonContextPackage,
    source: EngineeringResponseSourceEnvelope,
) -> ComparisonAssessment:
    declared = read_declared_outcome(source)
    left_count = comparison.statistics.left_evidence_count
    right_count = comparison.statistics.right_evidence_count

    if not comparison.both_sides_have_evidence:
        return ComparisonAssessment(
            outcome=ComparisonOutcome.INSUFFICIENT_EVIDENCE,
            stated_by_model=declared is not None,
            evidence_bounded=True,
            left_evidence_count=left_count,
            right_evidence_count=right_count,
        )

    return ComparisonAssessment(
        outcome=declared,
        stated_by_model=declared is not None,
        evidence_bounded=False,
        left_evidence_count=left_count,
        right_evidence_count=right_count,
    )
