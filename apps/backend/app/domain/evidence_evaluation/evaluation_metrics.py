"""
Deterministic evaluation metrics (Milestone 28.2).

Counts in, exact ratios out. ``Decimal`` throughout, never ``float``: two
runs of the same evaluation must produce byte-identical numbers, and
binary floating point makes that a matter of luck on the last digit.

## Undefined is reported as undefined

Precision is ``TP / (TP + FP)``. When the extractor made **no
predictions at all**, that denominator is zero and precision is not a
number - it is a question that was never asked.

This module returns ``None`` there, rather than 0 or 1. Reporting 0 would
claim the extractor was wrong about things it never said; reporting 1
would claim it was right about them. Both are fabrications, and both
would corrupt a regression comparison the moment a rule stopped matching
anything.

The same holds for recall with no expectations, and for F1 when either
input is undefined.

## No probabilistic metrics

No confidence intervals, no significance tests, no sampling. A
deterministic extractor over a fixed corpus produces the same counts
every time; there is no distribution to reason about, and dressing exact
counts in statistics would suggest an uncertainty that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

# Ratios are quantised so two runs, two machines and two database
# round-trips all render the same string. Six places is far finer than
# any corpus this system will hold and still short enough to read.
METRIC_PRECISION = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """
    The three counts, and the ratios derived from them.

    Counts are the primary record; the ratios are conveniences computed
    from them. Storing a ratio without its counts would make an
    evaluation unauditable - "precision 0.75" says nothing about whether
    that was 3 of 4 or 300 of 400.
    """

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def predicted(self) -> int:
        """Everything the extractor claimed."""

        return self.true_positives + self.false_positives

    @property
    def expected(self) -> int:
        """Everything the corpus says is there."""

        return self.true_positives + self.false_negatives

    @property
    def precision(self) -> Decimal | None:
        """Of what the extractor claimed, how much was right.

        ``None`` when it claimed nothing - see the module docstring."""

        return _ratio(self.true_positives, self.predicted)

    @property
    def recall(self) -> Decimal | None:
        """Of what is there, how much the extractor found.

        ``None`` when the corpus expects nothing."""

        return _ratio(self.true_positives, self.expected)

    @property
    def f1(self) -> Decimal | None:
        """
        The harmonic mean of precision and recall.

        Computed **from the counts** as ``2·TP / (2·TP + FP + FN)``,
        which is algebraically the harmonic mean and avoids rounding
        twice: deriving it from already-quantised precision and recall
        loses a digit, and two evaluations that differ only in that digit
        would read as a regression.

        ``None`` when either input is undefined, or when both are zero -
        a harmonic mean of nothing is not zero, it is unanswerable.
        """

        if self.predicted == 0 or self.expected == 0:
            return None

        if self.true_positives == 0:
            return None

        doubled = Decimal(2 * self.true_positives)

        return _quantize(
            doubled
            / (doubled + Decimal(self.false_positives + self.false_negatives))
        )

    @property
    def is_perfect(self) -> bool:
        """Everything expected was found and nothing else was
        claimed."""

        return (
            self.false_positives == 0
            and self.false_negatives == 0
            and self.true_positives > 0
        )

    def combined_with(self, other: "EvaluationMetrics") -> "EvaluationMetrics":
        """Counts add. Ratios are always recomputed from the totals -
        averaging two precisions would weight a one-item document the
        same as a two-hundred-item one."""

        return EvaluationMetrics(
            true_positives=self.true_positives + other.true_positives,
            false_positives=self.false_positives + other.false_positives,
            false_negatives=self.false_negatives + other.false_negatives,
        )


def _ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None

    return _quantize(Decimal(numerator) / Decimal(denominator))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(METRIC_PRECISION, rounding=ROUND_HALF_EVEN)
