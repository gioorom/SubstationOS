"""
Tests for evidence matching and classification (Milestone 28.2).

Pure domain tests. Each isolates one property of the comparison, because
a test that needed a real document to prove precision arithmetic would be
testing three things at once.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.engineering_evidence.evidence_models import (
    EngineeringQuantity,
    EvidenceStatus,
    EvidenceType,
)
from app.domain.evidence_evaluation.evaluation_matcher import (
    evaluate_document,
    provenance_matches,
)
from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationOutcome,
    MismatchReason,
    ProvenanceMatchPolicy,
)
from tests.domain._evaluation_support import (
    document,
    expected,
    extracted,
    provenance,
    voltage,
)


def _outcomes(evaluation):
    return [result.outcome for result in evaluation.results]


# --- Exact matches ----------------------------------------------------------


def test_an_identical_observation_is_a_true_positive() -> None:
    evaluation = evaluate_document(
        document(expected()), (extracted(),)
    )

    assert _outcomes(evaluation) == [EvaluationOutcome.TRUE_POSITIVE]
    assert evaluation.metrics.true_positives == 1


def test_a_matching_quantity_is_a_true_positive() -> None:
    evaluation = evaluate_document(
        document(
            expected(
                evidence_type=EvidenceType.VOLTAGE_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage(),
            )
        ),
        (
            extracted(
                evidence_type=EvidenceType.VOLTAGE_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage(),
            ),
        ),
    )

    assert _outcomes(evaluation) == [EvaluationOutcome.TRUE_POSITIVE]


def test_several_matching_observations_all_count() -> None:
    evaluation = evaluate_document(
        document(
            expected(observed_text="T1", token_start=1, token_end=2),
            expected(observed_text="T2", token_start=3, token_end=4),
        ),
        (
            extracted(observed_text="T1", token_start=1, token_end=2),
            extracted(observed_text="T2", token_start=3, token_end=4),
        ),
    )

    assert evaluation.metrics.true_positives == 2
    assert evaluation.metrics.false_positives == 0
    assert evaluation.metrics.false_negatives == 0


# --- False positives and negatives -------------------------------------------


def test_an_unexpected_observation_is_a_false_positive() -> None:
    evaluation = evaluate_document(document(), (extracted(),))

    assert _outcomes(evaluation) == [EvaluationOutcome.FALSE_POSITIVE]
    assert evaluation.results[0].mismatch_reason is MismatchReason.UNPAIRED


def test_a_missing_observation_is_a_false_negative() -> None:
    evaluation = evaluate_document(document(expected()), ())

    assert _outcomes(evaluation) == [EvaluationOutcome.FALSE_NEGATIVE]
    assert evaluation.results[0].mismatch_reason is MismatchReason.UNPAIRED


def test_a_document_expecting_nothing_and_finding_nothing_is_clean(
) -> None:
    evaluation = evaluate_document(document(), ())

    assert evaluation.results == ()
    assert evaluation.metrics.true_positives == 0


# --- Disagreement at the same location ----------------------------------------


def test_the_wrong_text_is_both_a_false_positive_and_a_false_negative(
) -> None:
    """
    Not a "near miss".

    The extractor said something that is not so *and* failed to say
    something that is. One softer outcome would let a rule that reads the
    wrong characters look almost right.
    """

    evaluation = evaluate_document(
        document(expected(observed_text="T1")),
        (extracted(observed_text="T2", designation="T2"),),
    )

    assert set(_outcomes(evaluation)) == {
        EvaluationOutcome.FALSE_POSITIVE,
        EvaluationOutcome.FALSE_NEGATIVE,
    }
    assert evaluation.metrics.true_positives == 0


def test_the_wrong_evidence_type_does_not_match() -> None:
    """A voltage recorded as a current is wrong, not close."""

    evaluation = evaluate_document(
        document(
            expected(
                evidence_type=EvidenceType.VOLTAGE_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage(),
            )
        ),
        (
            extracted(
                evidence_type=EvidenceType.CURRENT_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage(),
            ),
        ),
    )

    assert evaluation.metrics.true_positives == 0
    assert (
        evaluation.results[0].mismatch_reason
        is MismatchReason.EVIDENCE_TYPE
    )


def test_the_wrong_value_does_not_match() -> None:
    """20 kV and 200 kV differ by an order of magnitude. Equal text is
    not equal meaning."""

    evaluation = evaluate_document(
        document(
            expected(
                evidence_type=EvidenceType.VOLTAGE_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage("20"),
            )
        ),
        (
            extracted(
                evidence_type=EvidenceType.VOLTAGE_VALUE,
                observed_text="20 kV",
                designation=None,
                quantity=voltage("200"),
            ),
        ),
    )

    assert evaluation.metrics.true_positives == 0
    assert evaluation.results[0].mismatch_reason is MismatchReason.QUANTITY


def test_a_different_status_does_not_match() -> None:
    """``AMBIGUOUS`` and ``OBSERVED`` are different claims about how much
    is known."""

    evaluation = evaluate_document(
        document(
            expected(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="1.250 kVA",
                status=EvidenceStatus.AMBIGUOUS,
                designation=None,
            )
        ),
        (
            extracted(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="1.250 kVA",
                status=EvidenceStatus.OBSERVED,
                designation=None,
                quantity=EngineeringQuantity(
                    value=Decimal("1250"), unit="kVA"
                ),
            ),
        ),
    )

    assert evaluation.metrics.true_positives == 0
    assert evaluation.results[0].mismatch_reason is MismatchReason.STATUS


# --- Provenance validation ------------------------------------------------------


def test_correct_text_in_the_wrong_place_is_not_a_match() -> None:
    """
    The rule the whole framework rests on.

    A consumer that trusted the location would be reading the wrong part
    of the document, and the value of this pipeline is that a claim can
    be traced to the characters that support it.
    """

    evaluation = evaluate_document(
        document(expected(line=0, token_start=1, token_end=2)),
        (extracted(line=4, token_start=1, token_end=2),),
    )

    assert set(_outcomes(evaluation)) == {
        EvaluationOutcome.FALSE_POSITIVE,
        EvaluationOutcome.FALSE_NEGATIVE,
    }


def test_the_wrong_character_range_is_not_an_exact_match() -> None:
    """Same tokens, different characters inside the span - the
    observation points at text it did not read."""

    evaluation = evaluate_document(
        document(expected(character_start=0, character_end=2)),
        (extracted(character_start=3, character_end=5),),
    )

    assert evaluation.metrics.true_positives == 0
    assert (
        evaluation.results[0].mismatch_reason is MismatchReason.PROVENANCE
    )


def test_the_location_only_policy_accepts_differing_character_ranges(
) -> None:
    """A declared, coarser policy - for a corpus annotated before span
    offsets were recorded. It has to be passed explicitly, and the report
    records which policy was used."""

    evaluation = evaluate_document(
        document(expected(character_start=0, character_end=2)),
        (extracted(character_start=3, character_end=5),),
        provenance_policy=ProvenanceMatchPolicy.LOCATION_ONLY,
    )

    assert evaluation.metrics.true_positives == 1


def test_the_location_only_policy_still_requires_the_same_location(
) -> None:
    """Coarser is not permissive: the page, paragraph, line and token
    range must still agree."""

    assert not provenance_matches(
        provenance(line=0),
        provenance(line=3),
        ProvenanceMatchPolicy.LOCATION_ONLY,
    )


def test_the_exact_policy_compares_the_whole_chain() -> None:
    assert provenance_matches(
        provenance(), provenance(), ProvenanceMatchPolicy.EXACT
    )
    assert not provenance_matches(
        provenance(page=1),
        provenance(page=2),
        ProvenanceMatchPolicy.EXACT,
    )


# --- Determinism -----------------------------------------------------------------


def test_evaluating_the_same_input_twice_is_equal() -> None:
    reference = document(
        expected(observed_text="T1", token_start=1, token_end=2),
        expected(observed_text="T2", token_start=5, token_end=6),
    )
    items = (
        extracted(observed_text="T2", token_start=5, token_end=6),
        extracted(observed_text="T1", token_start=1, token_end=2),
    )

    assert evaluate_document(reference, items) == evaluate_document(
        reference, items
    )


def test_results_are_ordered_by_location_regardless_of_input_order(
) -> None:
    """So two reports diff cleanly and a reviewer sees only real
    changes."""

    reference = document(
        expected(observed_text="T1", token_start=1, token_end=2),
        expected(observed_text="T2", token_start=5, token_end=6),
    )
    forwards = evaluate_document(
        reference,
        (
            extracted(observed_text="T1", token_start=1, token_end=2),
            extracted(observed_text="T2", token_start=5, token_end=6),
        ),
    )
    backwards = evaluate_document(
        reference,
        (
            extracted(observed_text="T2", token_start=5, token_end=6),
            extracted(observed_text="T1", token_start=1, token_end=2),
        ),
    )

    assert forwards == backwards
