"""
Reading the verdict of an engineering verification (Milestone 24.1).

This is the **only** place in SubstationOS that reads meaning out of a
provider's returned text, and it is deliberately not prose
interpretation:

- Prompt Builder's ``VERIFICATION_INSTRUCTIONS`` asks the model to open
  its answer with exactly one of four declared tokens on its own first
  line. This module matches that first line against those four literals,
  imported from Prompt Builder rather than restated, so the question asked
  and the answer read cannot drift apart.
- A first line matching none of them yields **no verdict** - never a
  verdict inferred from the surrounding sentences. Guessing would be
  inventing an engineering finding.
- Nothing after the first line is examined. There is no keyword search,
  no sentiment, no negation handling, and no scoring.

That distinction matters: Milestone 18's rule is that this context
performs "no semantic parsing of the provider's own returned text", and
reading a token the prompt explicitly requested is the same kind of
operation as reading ``finish_reason`` off the envelope - a declared
field, not an interpretation.

**One structural override.** When no project evidence was retrieved, the
outcome is ``INSUFFICIENT_EVIDENCE`` whatever the model wrote. With an
empty context there was, by construction, nothing to support or
contradict the statement with, so a ``SUPPORTED`` verdict could only have
come from the model's general knowledge - exactly what a verification must
never rest on. This is the one case where the builder does not take the
model at its word, and it is a structural fact rather than a judgement.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    VerificationAssessment,
    VerificationOutcome,
)
from app.domain.prompt_builder.composition_policy import (
    VERIFICATION_VERDICT_TOKENS,
)

# The declared token -> domain outcome map, built from Prompt Builder's own
# vocabulary so a token this system asks for always has somewhere to land.
# A KeyError here would mean the two contexts had drifted, which a test
# asserts cannot happen.
_OUTCOME_BY_TOKEN: dict[str, VerificationOutcome] = {
    token: VerificationOutcome(token.lower())
    for token in VERIFICATION_VERDICT_TOKENS
}


def _first_text_line(
    content: tuple[EngineeringResponseSourceContent, ...],
) -> str | None:
    """The first line of the first supported text block, or ``None`` when
    the response carries no usable text at all."""

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
) -> VerificationOutcome | None:
    """
    The declared verdict, or ``None`` if the answer's first line is not
    exactly one of the four declared tokens.

    Matching is on the stripped first line only, case-insensitively, and
    tolerates a single trailing colon or full stop - a model writing
    "SUPPORTED:" has plainly complied with the protocol, and refusing that
    would discard a real verdict on a formatting technicality. It does
    **not** search the line for a token, so "probably SUPPORTED" and
    "NOT_SUPPORTED, though SUPPORTED in part" are read as no verdict at
    all, which is the honest reading of both.
    """

    line = _first_text_line(source.content)
    if line is None:
        return None

    candidate = line.rstrip(":.").strip().upper()

    return _OUTCOME_BY_TOKEN.get(candidate)


def assess_verification(
    context_package: ContextPackage,
    source: EngineeringResponseSourceEnvelope,
) -> VerificationAssessment:
    """
    The full assessment: what the model declared, whether an empty
    evidence set overrode it, and how much evidence the verdict rests on.
    """

    declared = read_declared_outcome(source)
    evidence_count = len(context_package.selected_items)

    if evidence_count == 0:
        return VerificationAssessment(
            outcome=VerificationOutcome.INSUFFICIENT_EVIDENCE,
            stated_by_model=declared is not None,
            evidence_bounded=True,
            evidence_reference_count=0,
        )

    return VerificationAssessment(
        outcome=declared,
        stated_by_model=declared is not None,
        evidence_bounded=False,
        evidence_reference_count=evidence_count,
    )
