"""
Tests for deterministic evaluation metrics (Milestone 28.2).

The arithmetic is simple; what these tests pin is the *policy* around it -
exact Decimal ratios, and undefined reported as undefined rather than
guessed at.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.evidence_evaluation.evaluation_metrics import (
    EvaluationMetrics,
)


def _metrics(tp: int, fp: int, fn: int) -> EvaluationMetrics:
    return EvaluationMetrics(
        true_positives=tp, false_positives=fp, false_negatives=fn
    )


# --- The three ratios ---------------------------------------------------------


def test_precision_is_correct_of_what_was_claimed() -> None:
    assert _metrics(3, 1, 0).precision == Decimal("0.750000")


def test_recall_is_found_of_what_is_there() -> None:
    assert _metrics(3, 0, 1).recall == Decimal("0.750000")


def test_f1_is_the_harmonic_mean() -> None:
    metrics = _metrics(3, 1, 1)

    assert metrics.precision == Decimal("0.750000")
    assert metrics.recall == Decimal("0.750000")
    assert metrics.f1 == Decimal("0.750000")


def test_f1_penalises_an_imbalance() -> None:
    """Precision 1.0 and recall 0.5 is not 0.75 - the harmonic mean pulls
    towards the worse of the two, which is the point of using it."""

    metrics = _metrics(5, 0, 5)

    assert metrics.precision == Decimal("1.000000")
    assert metrics.recall == Decimal("0.500000")
    assert metrics.f1 == Decimal("0.666667")


def test_a_perfect_run_scores_one() -> None:
    metrics = _metrics(4, 0, 0)

    assert metrics.precision == Decimal("1.000000")
    assert metrics.recall == Decimal("1.000000")
    assert metrics.f1 == Decimal("1.000000")
    assert metrics.is_perfect is True


def test_ratios_are_exact_decimals_never_floats() -> None:
    """Two runs, two machines and two database round-trips must render
    the same string."""

    precision = _metrics(1, 2, 0).precision

    assert isinstance(precision, Decimal)
    assert precision == Decimal("0.333333")
    assert str(precision) == "0.333333"


# --- Undefined is reported as undefined -----------------------------------------


def test_precision_is_undefined_when_nothing_was_claimed() -> None:
    """
    Not 0, and not 1.

    Reporting 0 would claim the extractor was wrong about things it never
    said; reporting 1 would claim it was right about them. Both are
    fabrications, and both would corrupt a regression comparison the
    moment a rule stopped matching anything.
    """

    assert _metrics(0, 0, 3).precision is None


def test_recall_is_undefined_when_nothing_was_expected() -> None:
    assert _metrics(0, 2, 0).recall is None


def test_f1_is_undefined_when_either_input_is() -> None:
    assert _metrics(0, 0, 3).f1 is None
    assert _metrics(0, 2, 0).f1 is None


def test_f1_is_undefined_when_precision_and_recall_are_both_zero(
) -> None:
    """A harmonic mean of nothing is not zero, it is unanswerable."""

    metrics = _metrics(0, 2, 3)

    assert metrics.precision == Decimal("0.000000")
    assert metrics.recall == Decimal("0.000000")
    assert metrics.f1 is None


def test_an_empty_evaluation_reports_everything_undefined() -> None:
    metrics = _metrics(0, 0, 0)

    assert metrics.precision is None
    assert metrics.recall is None
    assert metrics.f1 is None
    assert metrics.is_perfect is False


# --- Counts are the primary record ----------------------------------------------


def test_counts_are_reported_alongside_the_ratios() -> None:
    """"Precision 0.75" says nothing about whether that was 3 of 4 or 300
    of 400."""

    metrics = _metrics(3, 1, 2)

    assert metrics.predicted == 4
    assert metrics.expected == 5


def test_combining_adds_counts_and_recomputes_ratios() -> None:
    """Averaging two precisions would weight a one-item document the same
    as a two-hundred-item one."""

    small = _metrics(1, 0, 0)
    large = _metrics(0, 100, 0)

    combined = small.combined_with(large)

    assert combined.true_positives == 1
    assert combined.false_positives == 100
    assert combined.precision == Decimal("0.009901")
