"""
Tests for regression detection (Milestone 28.2).

A regression report exists to answer "what did this rule change break,
and which items?". These tests pin both halves - the detection and the
naming.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.evidence_evaluation.evaluation_models import (
    DocumentEvaluation,
    EvaluationOutcome,
    EvaluationReport,
    EvidenceEvaluationResult,
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.regression_detector import (
    RegressionKind,
    detect_regressions,
)


def _result(
    outcome: EvaluationOutcome,
    text: str,
    *,
    line: int = 0,
    rule_version: str = "1.0",
) -> EvidenceEvaluationResult:
    return EvidenceEvaluationResult(
        outcome=outcome,
        evidence_type=EvidenceType.DESIGNATION,
        observed_text=text,
        rule_id="designation_generic",
        rule_version=rule_version,
        location=(1, 0, line, 0, 1),
    )


def _report(
    *results: EvidenceEvaluationResult,
    corpus_version: str = "1.0",
    policy_version: str = "1.0",
    rule_versions: tuple[tuple[str, str], ...] = (
        ("designation_generic", "1.0"),
    ),
) -> EvaluationReport:
    return EvaluationReport(
        corpus_id="unit_corpus",
        corpus_version=corpus_version,
        extraction_policy_version=policy_version,
        provenance_policy=ProvenanceMatchPolicy.EXACT,
        rule_versions=rule_versions,
        documents=(
            DocumentEvaluation(
                document_ref="doc", title="doc", results=results
            ),
        ),
    )


# --- Nothing changed ---------------------------------------------------------


def test_comparing_a_report_with_itself_finds_no_regression() -> None:
    report = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.FALSE_NEGATIVE, "T2", line=1),
    )

    regression = detect_regressions(report, report)

    assert regression.has_regression is False
    assert regression.regressions == ()
    assert regression.new_false_positives == ()
    assert regression.new_false_negatives == ()


# --- Regressions -------------------------------------------------------------


def test_a_new_false_positive_is_a_regression_and_is_named() -> None:
    """"Precision fell" is not actionable. The item is."""

    baseline = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.FALSE_POSITIVE, "AT", line=2),
    )

    regression = detect_regressions(baseline, candidate)

    assert RegressionKind.NEW_FALSE_POSITIVES in regression.regressions
    assert [
        item.observed_text for item in regression.new_false_positives
    ] == ["AT"]
    assert regression.new_false_positives[0].location == (1, 0, 2, 0, 1)


def test_a_new_false_negative_is_a_regression_and_is_named() -> None:
    baseline = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))
    candidate = _report(_result(EvaluationOutcome.FALSE_NEGATIVE, "T1"))

    regression = detect_regressions(baseline, candidate)

    assert RegressionKind.NEW_FALSE_NEGATIVES in regression.regressions
    assert [
        item.observed_text for item in regression.new_false_negatives
    ] == ["T1"]


def test_a_precision_decrease_is_detected() -> None:
    baseline = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.FALSE_POSITIVE, "AT", line=2),
    )

    regression = detect_regressions(baseline, candidate)
    delta = {d.name: d for d in regression.metric_deltas}["precision"]

    assert RegressionKind.PRECISION_DECREASED in regression.regressions
    assert delta.baseline == Decimal("1.000000")
    assert delta.candidate == Decimal("0.500000")
    assert delta.delta == Decimal("-0.500000")


def test_a_recall_decrease_is_detected() -> None:
    baseline = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.TRUE_POSITIVE, "T2", line=1),
    )
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.FALSE_NEGATIVE, "T2", line=1),
    )

    regression = detect_regressions(baseline, candidate)

    assert RegressionKind.RECALL_DECREASED in regression.regressions
    assert RegressionKind.F1_DECREASED in regression.regressions


# --- Improvements ------------------------------------------------------------


def test_a_resolved_false_negative_is_reported_as_an_improvement(
) -> None:
    """The state a rule change is aiming for: something got better and
    nothing got worse."""

    baseline = _report(_result(EvaluationOutcome.FALSE_NEGATIVE, "TR-1"))
    candidate = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "TR-1"))

    regression = detect_regressions(baseline, candidate)

    assert regression.has_regression is False
    assert regression.improved is True
    assert [
        item.observed_text
        for item in regression.resolved_false_negatives
    ] == ["TR-1"]


def test_a_mixed_change_reports_both_sides() -> None:
    """A rule that fixes one case and breaks another is not an
    improvement, and the report says so while naming both items."""

    baseline = _report(
        _result(EvaluationOutcome.FALSE_NEGATIVE, "TR-1"),
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1", line=1),
    )
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "TR-1"),
        _result(EvaluationOutcome.FALSE_NEGATIVE, "T1", line=1),
    )

    regression = detect_regressions(baseline, candidate)

    assert regression.has_regression is True
    assert regression.improved is False
    assert len(regression.resolved_false_negatives) == 1
    assert len(regression.new_false_negatives) == 1


# --- Versions ------------------------------------------------------------------


def test_rule_version_changes_are_reported_beside_the_metrics() -> None:
    """"Which rule changed?" must be answerable from two reports
    alone."""

    baseline = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        rule_versions=(("designation_generic", "1.0"),),
    )
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        rule_versions=(
            ("designation_generic", "1.1"),
            ("voltage_value", "1.0"),
        ),
    )

    regression = detect_regressions(baseline, candidate)

    assert regression.rule_version_changes == (
        ("designation_generic", "1.0", "1.1"),
        ("voltage_value", "-", "1.0"),
    )


def test_a_policy_version_change_is_recorded_on_both_sides() -> None:
    baseline = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        policy_version="1.0",
    )
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        policy_version="1.1",
    )

    regression = detect_regressions(baseline, candidate)

    assert regression.baseline_policy_version == "1.0"
    assert regression.candidate_policy_version == "1.1"


def test_a_corpus_version_change_marks_the_comparison_incomparable(
) -> None:
    """
    The comparison is still produced - it is often what you want - but a
    metric movement caused by new annotations must not be read as a rule
    regression.
    """

    baseline = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        corpus_version="1.0",
    )
    candidate = _report(
        _result(EvaluationOutcome.TRUE_POSITIVE, "T1"),
        _result(EvaluationOutcome.FALSE_NEGATIVE, "T9", line=8),
        corpus_version="1.1",
    )

    regression = detect_regressions(baseline, candidate)

    assert regression.comparable is False
    assert regression.baseline_corpus_version == "1.0"
    assert regression.candidate_corpus_version == "1.1"
    assert regression.new_false_negatives


def test_the_same_corpus_version_is_comparable() -> None:
    report = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))

    assert detect_regressions(report, report).comparable is True


# --- Undefined metrics ------------------------------------------------------------


def test_a_delta_against_an_undefined_metric_is_undefined() -> None:
    """"Precision went from nothing to 0.9" is not an improvement of 0.9,
    it is a different question being answerable for the first time."""

    baseline = _report(_result(EvaluationOutcome.FALSE_NEGATIVE, "T1"))
    candidate = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))

    regression = detect_regressions(baseline, candidate)
    delta = {d.name: d for d in regression.metric_deltas}["precision"]

    assert delta.baseline is None
    assert delta.candidate == Decimal("1.000000")
    assert delta.delta is None
    assert delta.decreased is False


def test_detection_is_deterministic() -> None:
    baseline = _report(_result(EvaluationOutcome.TRUE_POSITIVE, "T1"))
    candidate = _report(
        _result(EvaluationOutcome.FALSE_POSITIVE, "AT", line=2),
        _result(EvaluationOutcome.FALSE_POSITIVE, "MT", line=1),
    )

    assert detect_regressions(baseline, candidate) == detect_regressions(
        baseline, candidate
    )
