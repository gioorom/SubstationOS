"""
Domain tests for reading an engineering verification's verdict (Milestone
24.1).

Two properties matter most here, and both are about refusing to invent:

1. **A non-compliant answer yields no verdict**, never one inferred from
   the surrounding prose.
2. **An empty evidence set forces INSUFFICIENT_EVIDENCE**, whatever the
   model wrote - a verification cannot come back SUPPORTED from a project
   with nothing in it.

Pure and fast: no I/O, no database, no provider.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    EngineeringSourceFinishReason,
    VerificationOutcome,
)
from app.domain.engineering_response.engineering_response_verification import (
    assess_verification,
    read_declared_outcome,
)
from app.domain.prompt_builder.composition_policy import (
    VERIFICATION_VERDICT_TOKENS,
)
from app.services import context_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    results_for,
)

PROJECT_ID = 3
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _context_package(count: int):
    """A governed context holding ``count`` approved protection
    designations."""

    return context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=results_for(
            tuple(
                asset_item(
                    f"node-87t-{index}",
                    f"87T-{index}",
                    statement_key=f"statement-{index}",
                    project_id=PROJECT_ID,
                )
                for index in range(count)
            ),
            project_id=PROJECT_ID,
        ),
        now=NOW,
    ).package


def _envelope(text: str, *, supported: bool = True):
    return EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="fake-model",
        returned_model_identifier="fake-model",
        content=(
            EngineeringResponseSourceContent(
                sequence_index=0,
                is_supported_text=supported,
                text=text,
                provider_block_type=None,
            ),
        ),
        finish_reason=EngineeringSourceFinishReason.COMPLETED,
        request_correlation_id="corr-1",
        attempt_count=1,
        warnings=(),
        input_tokens=10,
        output_tokens=5,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )


# --- Reading the declared verdict -------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("SUPPORTED", VerificationOutcome.SUPPORTED),
        ("NOT_SUPPORTED", VerificationOutcome.NOT_SUPPORTED),
        (
            "INSUFFICIENT_EVIDENCE",
            VerificationOutcome.INSUFFICIENT_EVIDENCE,
        ),
        (
            "CONFLICTING_EVIDENCE",
            VerificationOutcome.CONFLICTING_EVIDENCE,
        ),
    ],
)
def test_each_declared_token_is_read_as_its_outcome(
    token: str, expected: VerificationOutcome
) -> None:
    envelope = _envelope(f"{token}\nBecause candidate c1 says so.")

    assert read_declared_outcome(envelope) is expected


def test_a_lowercase_verdict_is_still_read() -> None:
    assert read_declared_outcome(_envelope("supported\nc1.")) is (
        VerificationOutcome.SUPPORTED
    )


def test_a_trailing_colon_or_period_is_tolerated() -> None:
    """A model writing "SUPPORTED:" has plainly complied; discarding a real
    verdict on a formatting technicality would be worse than reading it."""

    assert read_declared_outcome(_envelope("SUPPORTED:\nc1.")) is (
        VerificationOutcome.SUPPORTED
    )
    assert read_declared_outcome(_envelope("NOT_SUPPORTED.\nc1.")) is (
        VerificationOutcome.NOT_SUPPORTED
    )


def test_leading_blank_lines_are_skipped() -> None:
    assert read_declared_outcome(_envelope("\n\nSUPPORTED\nc1.")) is (
        VerificationOutcome.SUPPORTED
    )


def test_prose_containing_a_token_is_not_read_as_a_verdict() -> None:
    """The whole point of a declared protocol: a token *inside* a sentence
    is not a verdict, and guessing that it is would be inventing an
    engineering finding."""

    assert read_declared_outcome(_envelope("probably SUPPORTED\nc1.")) is None
    assert (
        read_declared_outcome(
            _envelope("NOT_SUPPORTED, though SUPPORTED in part.")
        )
        is None
    )


def test_an_answer_with_no_verdict_line_yields_no_verdict() -> None:
    assert read_declared_outcome(_envelope("It all looks fine to me.")) is None


def test_only_the_first_line_is_examined() -> None:
    """No keyword search over the body - a verdict buried on line four is
    not a declared verdict."""

    envelope = _envelope("Here is my analysis.\nSUPPORTED\nc1.")

    assert read_declared_outcome(envelope) is None


def test_an_envelope_with_no_usable_text_yields_no_verdict() -> None:
    assert read_declared_outcome(_envelope("", supported=False)) is None


def test_the_token_vocabulary_matches_the_outcome_enum() -> None:
    """Prompt Builder asks for these tokens and Engineering Response reads
    them. Drift between the two would silently stop verdicts being read at
    all, so it is asserted rather than assumed."""

    assert {token.lower() for token in VERIFICATION_VERDICT_TOKENS} == {
        outcome.value for outcome in VerificationOutcome
    }


# --- The assessment ----------------------------------------------------------


def test_a_declared_verdict_with_evidence_is_reported_as_stated() -> None:
    assessment = assess_verification(
        _context_package(2), _envelope("SUPPORTED\nc1.")
    )

    assert assessment.outcome is VerificationOutcome.SUPPORTED
    assert assessment.stated_by_model is True
    assert assessment.evidence_bounded is False
    assert assessment.evidence_reference_count == 2


def test_no_declared_verdict_with_evidence_reports_no_outcome() -> None:
    assessment = assess_verification(
        _context_package(1), _envelope("Looks fine.")
    )

    assert assessment.outcome is None
    assert assessment.stated_by_model is False
    assert assessment.evidence_bounded is False


@pytest.mark.parametrize(
    "text",
    [
        "SUPPORTED\nc1 shows it.",
        "NOT_SUPPORTED\nc1 contradicts it.",
        "CONFLICTING_EVIDENCE\nboth.",
        "Looks fine to me.",
    ],
)
def test_empty_evidence_forces_insufficient_evidence(text: str) -> None:
    """The structural override, and the safety property that matters most:
    with nothing retrieved there was nothing to support or contradict the
    statement, so a SUPPORTED verdict could only have come from the
    model's general knowledge."""

    assessment = assess_verification(_context_package(0), _envelope(text))

    assert assessment.outcome is (
        VerificationOutcome.INSUFFICIENT_EVIDENCE
    )
    assert assessment.evidence_bounded is True
    assert assessment.evidence_reference_count == 0


def test_the_override_still_records_whether_the_model_spoke() -> None:
    """A reader needs to know the model claimed SUPPORTED and was
    overruled - that is a different situation from a model that said
    nothing."""

    overruled = assess_verification(
        _context_package(0), _envelope("SUPPORTED\nc1.")
    )
    silent = assess_verification(_context_package(0), _envelope("Hmm."))

    assert overruled.stated_by_model is True
    assert silent.stated_by_model is False
    assert overruled.outcome is silent.outcome


def test_assessment_is_deterministic() -> None:
    package = _context_package(2)
    envelope = _envelope("SUPPORTED\nc1.")

    assert assess_verification(package, envelope) == assess_verification(
        package, envelope
    )


def test_the_outcome_set_is_exactly_four_values() -> None:
    """No fifth category is invented; "no verdict" is ``None``, which is a
    different and honest state."""

    assert len(VerificationOutcome) == 4
