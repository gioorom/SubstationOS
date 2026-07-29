from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.evidence_evaluation.evaluation_failures import (
    EvaluationFailureCode,
)
from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationOutcome,
    MismatchReason,
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.regression_detector import RegressionKind

# --- Metrics ---------------------------------------------------------------


class MetricsRead(BaseModel):
    """
    Counts first, ratios derived.

    Ratios are ``null`` when undefined - no predictions, or no
    expectations. Reporting 0 would claim the extractor was wrong about
    things it never said; reporting 1 would claim it was right about
    them.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    predicted: int
    expected: int
    precision: Decimal | None
    recall: Decimal | None
    f1: Decimal | None

    model_config = ConfigDict(from_attributes=True)


# --- Report ----------------------------------------------------------------


class EvidenceEvaluationResultRead(BaseModel):
    """One item's verdict, with the location that identifies it."""

    outcome: EvaluationOutcome
    evidence_type: EvidenceType
    observed_text: str
    rule_id: str
    rule_version: str
    mismatch_reason: MismatchReason | None
    page_number: int
    paragraph_index: int
    line_index: int
    token_start: int
    token_end: int

    @classmethod
    def from_domain(cls, result) -> "EvidenceEvaluationResultRead":
        page, paragraph, line, token_start, token_end = result.location

        return cls(
            outcome=result.outcome,
            evidence_type=result.evidence_type,
            observed_text=result.observed_text,
            rule_id=result.rule_id,
            rule_version=result.rule_version,
            mismatch_reason=result.mismatch_reason,
            page_number=page,
            paragraph_index=paragraph,
            line_index=line,
            token_start=token_start,
            token_end=token_end,
        )


class DocumentEvaluationRead(BaseModel):
    document_ref: str
    title: str
    metrics: MetricsRead
    results: tuple[EvidenceEvaluationResultRead, ...]

    @classmethod
    def from_domain(cls, document) -> "DocumentEvaluationRead":
        return cls(
            document_ref=document.document_ref,
            title=document.title,
            metrics=MetricsRead.model_validate(document.metrics),
            results=tuple(
                EvidenceEvaluationResultRead.from_domain(result)
                for result in document.results
            ),
        )


class RuleVersionRead(BaseModel):
    rule_id: str
    rule_version: str


class EvaluationReportSummaryRead(BaseModel):
    """What an evaluation *is*, and how it scored - without the
    per-item detail."""

    report_id: int
    created_at: str
    corpus_id: str
    corpus_version: str
    extraction_policy_version: str
    provenance_policy: ProvenanceMatchPolicy
    rule_versions: tuple[RuleVersionRead, ...]
    metrics: MetricsRead

    @classmethod
    def from_domain(cls, stored) -> "EvaluationReportSummaryRead":
        report = stored.report

        return cls(
            report_id=stored.report_id,
            created_at=stored.created_at,
            corpus_id=report.corpus_id,
            corpus_version=report.corpus_version,
            extraction_policy_version=report.extraction_policy_version,
            provenance_policy=report.provenance_policy,
            rule_versions=tuple(
                RuleVersionRead(rule_id=rule_id, rule_version=version)
                for rule_id, version in report.rule_versions
            ),
            metrics=MetricsRead.model_validate(report.metrics),
        )


class EvaluationReportRead(EvaluationReportSummaryRead):
    """The full report: per-document, per-evidence-type and per-rule
    breakdowns, and every item's verdict."""

    metrics_by_evidence_type: dict[str, MetricsRead]
    metrics_by_rule: dict[str, MetricsRead]
    documents: tuple[DocumentEvaluationRead, ...]

    @classmethod
    def from_domain(cls, stored) -> "EvaluationReportRead":
        report = stored.report
        summary = EvaluationReportSummaryRead.from_domain(stored)

        return cls(
            **summary.model_dump(),
            metrics_by_evidence_type={
                name: MetricsRead.model_validate(metrics)
                for name, metrics in report.metrics_by_evidence_type.items()
            },
            metrics_by_rule={
                name: MetricsRead.model_validate(metrics)
                for name, metrics in report.metrics_by_rule.items()
            },
            documents=tuple(
                DocumentEvaluationRead.from_domain(document)
                for document in report.documents
            ),
        )


class EvaluationFailureRead(BaseModel):
    code: EvaluationFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunResultRead(BaseModel):
    succeeded: bool
    report: EvaluationReportRead | None
    failure: EvaluationFailureRead | None

    @classmethod
    def from_domain(cls, result) -> "EvaluationRunResultRead":
        return cls(
            succeeded=result.succeeded,
            report=(
                None
                if result.stored is None
                else EvaluationReportRead.from_domain(result.stored)
            ),
            failure=(
                None
                if result.failure is None
                else EvaluationFailureRead.model_validate(result.failure)
            ),
        )


# --- Regression ---------------------------------------------------------------


class MetricDeltaRead(BaseModel):
    """``delta`` is ``null`` when either side was undefined - a movement
    from "unanswerable" to 0.9 is not an improvement of 0.9."""

    name: str
    baseline: Decimal | None
    candidate: Decimal | None
    delta: Decimal | None
    decreased: bool

    model_config = ConfigDict(from_attributes=True)


class RuleVersionChangeRead(BaseModel):
    rule_id: str
    baseline_version: str
    candidate_version: str


class RegressionReportRead(BaseModel):
    """
    What changed between two evaluations, naming the exact items.

    ``comparable`` is ``false`` when the two reports evaluated different
    corpora or corpus versions - the comparison is still produced,
    because it is often what you want, but a metric movement caused by
    new annotations must not be read as a rule regression.
    """

    corpus_id: str
    comparable: bool
    has_regression: bool
    improved: bool
    regressions: tuple[RegressionKind, ...]
    baseline_corpus_version: str
    candidate_corpus_version: str
    baseline_policy_version: str
    candidate_policy_version: str
    metric_deltas: tuple[MetricDeltaRead, ...]
    rule_version_changes: tuple[RuleVersionChangeRead, ...]
    new_false_positives: tuple[EvidenceEvaluationResultRead, ...]
    new_false_negatives: tuple[EvidenceEvaluationResultRead, ...]
    resolved_false_positives: tuple[EvidenceEvaluationResultRead, ...]
    resolved_false_negatives: tuple[EvidenceEvaluationResultRead, ...]

    @classmethod
    def from_domain(cls, regression) -> "RegressionReportRead":
        return cls(
            corpus_id=regression.corpus_id,
            comparable=regression.comparable,
            has_regression=regression.has_regression,
            improved=regression.improved,
            regressions=regression.regressions,
            baseline_corpus_version=regression.baseline_corpus_version,
            candidate_corpus_version=regression.candidate_corpus_version,
            baseline_policy_version=regression.baseline_policy_version,
            candidate_policy_version=regression.candidate_policy_version,
            metric_deltas=tuple(
                MetricDeltaRead.model_validate(delta)
                for delta in regression.metric_deltas
            ),
            rule_version_changes=tuple(
                RuleVersionChangeRead(
                    rule_id=rule_id,
                    baseline_version=before,
                    candidate_version=after,
                )
                for rule_id, before, after in regression.rule_version_changes
            ),
            new_false_positives=_results(regression.new_false_positives),
            new_false_negatives=_results(regression.new_false_negatives),
            resolved_false_positives=_results(
                regression.resolved_false_positives
            ),
            resolved_false_negatives=_results(
                regression.resolved_false_negatives
            ),
        )


def _results(items) -> tuple[EvidenceEvaluationResultRead, ...]:
    return tuple(
        EvidenceEvaluationResultRead.from_domain(item) for item in items
    )
