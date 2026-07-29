"""
Application service for Engineering Evidence Evaluation (EPIC 2,
Milestone 28.2).

    Reference corpus              (files, through its own port)
        -> Materialise documents   canonical text, through the real segmenter
        -> Execute the extractor   the same pure function production uses
        -> Match and classify      exact matches only
        -> Persist the report      never overwriting an earlier one

This is a **permanent product capability**, not a test harness. Every new
extraction rule is evaluated against the reference corpus before it
becomes part of the supported deterministic pipeline, and every rule
change is compared against the previous evaluation to see what it broke.

It reads no stored engineering evidence and writes none. An evaluation
against stored evidence would measure what was stored on some past day,
not what the current rules produce - which is the only question worth
asking of a rule catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_evidence.evidence_policy import (
    EXTRACTION_POLICY_VERSION,
)
from app.domain.evidence_evaluation.corpus_models import ReferenceCorpus
from app.domain.evidence_evaluation.corpus_repository import (
    ReferenceCorpusRepository,
)
from app.domain.evidence_evaluation.evaluation_engine import run_evaluation
from app.domain.evidence_evaluation.evaluation_failures import (
    EvaluationFailure,
    EvaluationFailureCode,
)
from app.domain.evidence_evaluation.evaluation_models import (
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.evaluation_policy import (
    DEFAULT_PROVENANCE_POLICY,
)
from app.domain.evidence_evaluation.evaluation_report_repository import (
    EvaluationReportRepository,
    StoredEvaluationReport,
)
from app.domain.evidence_evaluation.regression_detector import (
    RegressionReport,
    detect_regressions,
)

# Reference documents are not rows in the documents table. They are given
# a synthetic identity so the extractor - which records the document id
# and checksum on every observation - has something consistent to record.
# Deliberately a constant: it makes an evaluation reproducible, and no
# stored evidence is ever written under it.
REFERENCE_DOCUMENT_ID = 0
REFERENCE_CHECKSUM = "reference-corpus"


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    """What one evaluation run concluded."""

    succeeded: bool
    stored: StoredEvaluationReport | None = None
    corpus: ReferenceCorpus | None = None
    failure: EvaluationFailure | None = None


@dataclass(frozen=True, slots=True)
class RegressionComparisonResult:
    """What one comparison between two reports concluded."""

    succeeded: bool
    regression: RegressionReport | None = None
    failure: EvaluationFailure | None = None


def evaluate_corpus(
    corpus_repository: ReferenceCorpusRepository,
    report_repository: EvaluationReportRepository,
    *,
    corpus_id: str,
    provenance_policy: ProvenanceMatchPolicy = DEFAULT_PROVENANCE_POLICY,
    extraction_policy_version: str = EXTRACTION_POLICY_VERSION,
) -> EvaluationRunResult:
    """
    Evaluate one corpus and store the report.

    Checks run in order and the first failure is returned: there is no
    point running an extractor over a corpus that could not be read.
    """

    try:
        corpus = corpus_repository.load(corpus_id)
    except Exception as error:  # noqa: BLE001 - see below
        # A malformed corpus is refused loudly rather than partially
        # read. A corpus is the definition of "correct"; a half-read one
        # would quietly redefine it for every rule in the system.
        return _failed(
            EvaluationFailureCode.INVALID_CORPUS,
            f"Corpus '{corpus_id}' could not be read.",
            detail=f"{type(error).__name__}: {error}",
        )

    if corpus is None:
        return _failed(
            EvaluationFailureCode.CORPUS_NOT_FOUND,
            f"No reference corpus '{corpus_id}' exists.",
            detail="Corpora are version-controlled files in the "
            "repository; they are never created at runtime.",
        )

    try:
        canonical_texts = {
            document.document_ref: corpus_repository.materialize(
                document,
                document_id=REFERENCE_DOCUMENT_ID,
                content_checksum=REFERENCE_CHECKSUM,
            )
            for document in corpus.documents
        }
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            EvaluationFailureCode.REFERENCE_DOCUMENT_UNUSABLE,
            f"A document in corpus '{corpus_id}' could not be turned "
            "into canonical text.",
            detail=f"{type(error).__name__}: {error}",
        )

    try:
        report = run_evaluation(
            corpus,
            canonical_texts,
            provenance_policy=provenance_policy,
            extraction_policy_version=extraction_policy_version,
        )
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            EvaluationFailureCode.EXTRACTION_FAILURE,
            f"The extractor failed while evaluating corpus "
            f"'{corpus_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    try:
        stored = report_repository.save(report)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            EvaluationFailureCode.REPORT_PERSISTENCE_FAILURE,
            f"The evaluation of corpus '{corpus_id}' completed and could "
            "not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return EvaluationRunResult(succeeded=True, stored=stored, corpus=corpus)


def get_report(
    report_repository: EvaluationReportRepository, report_id: int
) -> StoredEvaluationReport | None:
    return report_repository.get(report_id)


def list_reports(
    report_repository: EvaluationReportRepository, corpus_id: str
) -> tuple[StoredEvaluationReport, ...]:
    return report_repository.list_for_corpus(corpus_id)


def compare_reports(
    report_repository: EvaluationReportRepository,
    *,
    baseline_report_id: int,
    candidate_report_id: int,
) -> RegressionComparisonResult:
    """
    Compare two stored evaluations.

    Comparing a report with itself is permitted and yields no
    regressions - which is a useful thing to be able to assert.
    """

    baseline = report_repository.get(baseline_report_id)
    candidate = report_repository.get(candidate_report_id)

    missing = [
        report_id
        for report_id, report in (
            (baseline_report_id, baseline),
            (candidate_report_id, candidate),
        )
        if report is None
    ]

    if missing:
        return RegressionComparisonResult(
            succeeded=False,
            failure=EvaluationFailure(
                code=EvaluationFailureCode.REPORT_NOT_FOUND,
                message="No evaluation report with id "
                + ", ".join(str(report_id) for report_id in missing)
                + ".",
            ),
        )

    return RegressionComparisonResult(
        succeeded=True,
        regression=detect_regressions(baseline.report, candidate.report),
    )


def _failed(
    code: EvaluationFailureCode, message: str, *, detail: str | None = None
) -> EvaluationRunResult:
    return EvaluationRunResult(
        succeeded=False,
        failure=EvaluationFailure(code=code, message=message, detail=detail),
    )
