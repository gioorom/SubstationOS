"""
Regression detection between two evaluations (Milestone 28.2).

Pure comparison of two ``EvaluationReport`` values. It answers the
question a rule change actually raises: *did this make anything worse,
and which items?*

## Why items, not just numbers

"Precision fell from 0.94 to 0.91" is not actionable. "These three
observations became false positives, all from rule
``designation_generic`` at version 1.1, all on page 4" is. A regression
report therefore names the exact items on both sides of every change.

## Comparability

Two reports are comparable when they evaluated the **same corpus at the
same version**. Comparing across corpus versions is still permitted and
still reported - it is how you see the effect of adding annotations - but
the comparison is flagged, because a metric that moved when the corpus
grew has not told you anything about the rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationOutcome,
    EvaluationReport,
    EvidenceEvaluationResult,
)


class RegressionKind(str, Enum):
    """What kind of change was detected."""

    PRECISION_DECREASED = "precision_decreased"
    RECALL_DECREASED = "recall_decreased"
    F1_DECREASED = "f1_decreased"
    NEW_FALSE_POSITIVES = "new_false_positives"
    NEW_FALSE_NEGATIVES = "new_false_negatives"


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """
    One metric's movement.

    ``None`` on either side means the metric was undefined there - no
    predictions, or no expectations. A delta against an undefined value
    is itself undefined rather than treated as zero: "precision went from
    nothing to 0.9" is not an improvement of 0.9, it is a different
    question being answerable for the first time.
    """

    name: str
    baseline: Decimal | None
    candidate: Decimal | None

    @property
    def delta(self) -> Decimal | None:
        if self.baseline is None or self.candidate is None:
            return None

        return self.candidate - self.baseline

    @property
    def decreased(self) -> bool:
        delta = self.delta

        return delta is not None and delta < 0


@dataclass(frozen=True, slots=True)
class RegressionReport:
    """
    What changed between two evaluations, and which items changed it.

    ``comparable`` is ``False`` when the two reports evaluated different
    corpora or different corpus versions. The comparison is still
    produced - it is often what you want - but the flag stops a metric
    movement caused by new annotations being read as a rule regression.
    """

    corpus_id: str
    comparable: bool
    baseline_corpus_version: str
    candidate_corpus_version: str
    baseline_policy_version: str
    candidate_policy_version: str
    metric_deltas: tuple[MetricDelta, ...] = ()
    new_false_positives: tuple[EvidenceEvaluationResult, ...] = ()
    new_false_negatives: tuple[EvidenceEvaluationResult, ...] = ()
    resolved_false_positives: tuple[EvidenceEvaluationResult, ...] = ()
    resolved_false_negatives: tuple[EvidenceEvaluationResult, ...] = ()
    rule_version_changes: tuple[tuple[str, str, str], ...] = ()

    @property
    def regressions(self) -> tuple[RegressionKind, ...]:
        """Every regression detected, in a fixed order."""

        detected: list[RegressionKind] = []
        by_name = {delta.name: delta for delta in self.metric_deltas}

        for name, kind in (
            ("precision", RegressionKind.PRECISION_DECREASED),
            ("recall", RegressionKind.RECALL_DECREASED),
            ("f1", RegressionKind.F1_DECREASED),
        ):
            delta = by_name.get(name)

            if delta is not None and delta.decreased:
                detected.append(kind)

        if self.new_false_positives:
            detected.append(RegressionKind.NEW_FALSE_POSITIVES)

        if self.new_false_negatives:
            detected.append(RegressionKind.NEW_FALSE_NEGATIVES)

        return tuple(detected)

    @property
    def has_regression(self) -> bool:
        return bool(self.regressions)

    @property
    def improved(self) -> bool:
        """Something got better and nothing got worse - the state a rule
        change is aiming for."""

        return not self.has_regression and bool(
            self.resolved_false_positives or self.resolved_false_negatives
        )


def detect_regressions(
    baseline: EvaluationReport, candidate: EvaluationReport
) -> RegressionReport:
    """Compare two evaluations of the same corpus."""

    baseline_metrics = baseline.metrics
    candidate_metrics = candidate.metrics

    baseline_fp = _by_identity(baseline, EvaluationOutcome.FALSE_POSITIVE)
    candidate_fp = _by_identity(candidate, EvaluationOutcome.FALSE_POSITIVE)
    baseline_fn = _by_identity(baseline, EvaluationOutcome.FALSE_NEGATIVE)
    candidate_fn = _by_identity(candidate, EvaluationOutcome.FALSE_NEGATIVE)

    return RegressionReport(
        corpus_id=candidate.corpus_id,
        comparable=(
            baseline.corpus_id == candidate.corpus_id
            and baseline.corpus_version == candidate.corpus_version
        ),
        baseline_corpus_version=baseline.corpus_version,
        candidate_corpus_version=candidate.corpus_version,
        baseline_policy_version=baseline.extraction_policy_version,
        candidate_policy_version=candidate.extraction_policy_version,
        metric_deltas=(
            MetricDelta(
                "precision",
                baseline_metrics.precision,
                candidate_metrics.precision,
            ),
            MetricDelta(
                "recall", baseline_metrics.recall, candidate_metrics.recall
            ),
            MetricDelta("f1", baseline_metrics.f1, candidate_metrics.f1),
        ),
        new_false_positives=_only_in(candidate_fp, baseline_fp),
        new_false_negatives=_only_in(candidate_fn, baseline_fn),
        resolved_false_positives=_only_in(baseline_fp, candidate_fp),
        resolved_false_negatives=_only_in(baseline_fn, candidate_fn),
        rule_version_changes=_rule_changes(baseline, candidate),
    )


def _by_identity(
    report: EvaluationReport, outcome: EvaluationOutcome
) -> dict[tuple, EvidenceEvaluationResult]:
    return {
        result.identity: result
        for result in report.results
        if result.outcome is outcome
    }


def _only_in(
    left: dict[tuple, EvidenceEvaluationResult],
    right: dict[tuple, EvidenceEvaluationResult],
) -> tuple[EvidenceEvaluationResult, ...]:
    """Sorted by identity, so a regression report reads the same way
    twice."""

    return tuple(
        left[identity]
        for identity in sorted(set(left) - set(right), key=str)
    )


def _rule_changes(
    baseline: EvaluationReport, candidate: EvaluationReport
) -> tuple[tuple[str, str, str], ...]:
    """
    Which rules moved version between the two evaluations, as
    ``(rule_id, baseline_version, candidate_version)``.

    A rule absent from one side is reported with ``-`` for that side: a
    rule that was added or withdrawn is exactly the kind of change a
    reviewer needs to see beside a metric movement.
    """

    before = dict(baseline.rule_versions)
    after = dict(candidate.rule_versions)

    return tuple(
        (rule_id, before.get(rule_id, "-"), after.get(rule_id, "-"))
        for rule_id in sorted(set(before) | set(after))
        if before.get(rule_id) != after.get(rule_id)
    )
