"""
Service tests for Engineering Evidence Evaluation (Milestone 28.2),
against a real (in-memory) database through the real adapters and the
real reference corpus.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.evidence_evaluation.evaluation_failures import (
    EvaluationFailureCode,
)
from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationOutcome,
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.evaluation_report_repository import (
    EvaluationReportRepository,
)
from app.domain.evidence_evaluation.regression_detector import (
    detect_regressions,
)
from app.infrastructure.evidence_evaluation.sqlalchemy_evaluation_report_repository import (  # noqa: E501
    SqlAlchemyEvaluationReportRepository,
)
from app.infrastructure.evidence_evaluation.yaml_reference_corpus_repository import (  # noqa: E501
    YamlReferenceCorpusRepository,
)
from app.models.engineering_evidence import EngineeringEvidenceSetRecord
from app.models.evidence_evaluation import EvaluationReportRecord
from app.services import evidence_evaluation_service

REFERENCE_CORPUS = "substation_reference"


def _evaluate(db: Session, corpus_id: str = REFERENCE_CORPUS, **kwargs):
    return evidence_evaluation_service.evaluate_corpus(
        kwargs.pop("corpus_repository", YamlReferenceCorpusRepository()),
        kwargs.pop(
            "report_repository", SqlAlchemyEvaluationReportRepository(db)
        ),
        corpus_id=corpus_id,
        **kwargs,
    )


# --- Running an evaluation ------------------------------------------------------


def test_the_reference_corpus_evaluates_and_is_recorded(
    db_session: Session,
) -> None:
    result = _evaluate(db_session)

    assert result.succeeded
    assert result.stored.report_id > 0
    assert (
        db_session.query(EvaluationReportRecord).count() == 1
    )


def test_the_report_records_every_version_it_ran_under(
    db_session: Session,
) -> None:
    """A report missing any of them could not be compared with another
    honestly."""

    report = _evaluate(db_session).stored.report

    assert report.corpus_id == REFERENCE_CORPUS
    assert report.corpus_version == "3.1"
    assert report.extraction_policy_version == "2.0"
    assert report.provenance_policy is ProvenanceMatchPolicy.EXACT
    assert dict(report.rule_versions)["designation_generic"] == "2.0"
    assert len(report.rule_versions) == 6


def test_the_measured_metrics_are_exact(db_session: Session) -> None:
    report = _evaluate(db_session).stored.report
    metrics = report.metrics

    assert (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
    ) == (33, 3, 1)
    assert metrics.precision == Decimal("0.916667")
    assert metrics.recall == Decimal("0.970588")
    assert metrics.f1 == Decimal("0.942857")


def test_metrics_are_broken_down_by_document_type_and_rule(
    db_session: Session,
) -> None:
    report = _evaluate(db_session).stored.report

    assert set(report.metrics_by_document) == {
        "bay_data_sheet",
        "cable_schedule",
        "descriptive_prose",
        "ambiguous_ratings",
        "designation_variants",
        # EPIC 32.E2 - transcribed from a single Italian DSO's drawings.
        "real_linee_at_terminal_blocks",
        "real_tr_terminal_blocks",
        "real_gas_alarm_prose",
    }
    assert report.metrics_by_evidence_type["designation"].false_negatives == 1
    assert (
        report.metrics_by_rule["designation_generic@2.0"].false_negatives
        == 1
    )
    assert report.metrics_by_document["descriptive_prose"].predicted == 0


def test_the_prose_document_produces_no_false_positives(
    db_session: Session,
) -> None:
    """The document that exists to catch over-eager rules."""

    report = _evaluate(db_session).stored.report

    assert report.metrics_by_document["descriptive_prose"].false_positives == 0


def test_evaluation_is_deterministic(db_session: Session) -> None:
    first = _evaluate(db_session).stored.report
    second = _evaluate(db_session).stored.report

    assert first == second


def test_a_coarser_provenance_policy_is_recorded_on_the_report(
    db_session: Session,
) -> None:
    """It has to be passed explicitly, and the report says which policy
    produced the numbers."""

    result = _evaluate(
        db_session,
        provenance_policy=ProvenanceMatchPolicy.LOCATION_ONLY,
    )

    assert (
        result.stored.report.provenance_policy
        is ProvenanceMatchPolicy.LOCATION_ONLY
    )


# --- Evaluation never touches evidence ----------------------------------------------


def test_evaluation_writes_no_engineering_evidence(
    db_session: Session,
) -> None:
    """A measurement must not modify the thing it measures."""

    _evaluate(db_session)

    assert db_session.query(EngineeringEvidenceSetRecord).count() == 0


def test_evaluation_needs_no_stored_document(db_session: Session) -> None:
    """The corpus is self-contained: no upload, no ingestion, no
    canonical text row. That is what lets an evaluation run in CI and
    mean the same thing next year."""

    from app.models.document import Document as DocumentRecord

    result = _evaluate(db_session)

    assert result.succeeded
    assert db_session.query(DocumentRecord).count() == 0


# --- History and regression ----------------------------------------------------------


def test_each_run_is_its_own_record(db_session: Session) -> None:
    """Nothing is overwritten - the history is what regression detection
    compares across."""

    first = _evaluate(db_session).stored
    second = _evaluate(db_session).stored

    assert first.report_id != second.report_id
    assert (
        len(
            evidence_evaluation_service.list_reports(
                SqlAlchemyEvaluationReportRepository(db_session),
                REFERENCE_CORPUS,
            )
        )
        == 2
    )


def test_reports_are_listed_newest_first(db_session: Session) -> None:
    _evaluate(db_session)
    latest = _evaluate(db_session).stored

    reports = evidence_evaluation_service.list_reports(
        SqlAlchemyEvaluationReportRepository(db_session), REFERENCE_CORPUS
    )

    assert reports[0].report_id == latest.report_id


def test_comparing_two_identical_runs_finds_no_regression(
    db_session: Session,
) -> None:
    baseline = _evaluate(db_session).stored
    candidate = _evaluate(db_session).stored

    comparison = evidence_evaluation_service.compare_reports(
        SqlAlchemyEvaluationReportRepository(db_session),
        baseline_report_id=baseline.report_id,
        candidate_report_id=candidate.report_id,
    )

    assert comparison.succeeded
    assert comparison.regression.has_regression is False
    assert comparison.regression.comparable is True


def test_comparing_reloaded_reports_agrees_with_the_in_memory_comparison(
    db_session: Session,
) -> None:
    """
    The persistence contract that matters.

    Reloaded reports carry the identifying fields rather than the full
    value objects, so this proves the stored form is sufficient for
    regression detection - the purpose the reports exist for.
    """

    in_memory = _evaluate(db_session).stored.report
    reloaded = SqlAlchemyEvaluationReportRepository(db_session).get(
        1
    ).report

    from_memory = detect_regressions(in_memory, in_memory)
    from_storage = detect_regressions(reloaded, reloaded)

    assert from_memory.has_regression == from_storage.has_regression
    assert [
        item.identity for item in from_memory.new_false_negatives
    ] == [item.identity for item in from_storage.new_false_negatives]


def test_comparing_a_missing_report_fails_honestly(
    db_session: Session,
) -> None:
    stored = _evaluate(db_session).stored

    comparison = evidence_evaluation_service.compare_reports(
        SqlAlchemyEvaluationReportRepository(db_session),
        baseline_report_id=stored.report_id,
        candidate_report_id=9999,
    )

    assert comparison.succeeded is False
    assert comparison.failure.code is (
        EvaluationFailureCode.REPORT_NOT_FOUND
    )
    assert "9999" in comparison.failure.message


# --- Persistence round-trip ------------------------------------------------------------


def test_the_report_survives_a_round_trip(db_session: Session) -> None:
    stored = _evaluate(db_session).stored

    reloaded = SqlAlchemyEvaluationReportRepository(db_session).get(
        stored.report_id
    )

    assert reloaded.report.metrics == stored.report.metrics
    assert reloaded.report.rule_versions == stored.report.rule_versions
    assert len(reloaded.report.documents) == len(stored.report.documents)


def test_the_stored_results_name_the_item_that_failed(
    db_session: Session,
) -> None:
    stored = _evaluate(db_session).stored

    reloaded = SqlAlchemyEvaluationReportRepository(db_session).get(
        stored.report_id
    )
    misses = [
        result
        for result in reloaded.report.results
        if result.outcome is EvaluationOutcome.FALSE_NEGATIVE
    ]

    assert [result.observed_text for result in misses] == ["TR-1"]
    assert misses[0].rule_id == "designation_generic"
    assert misses[0].location[2] == 1


# --- Typed failures ---------------------------------------------------------------------


def test_an_unknown_corpus_fails_honestly(db_session: Session) -> None:
    result = _evaluate(db_session, corpus_id="no_such_corpus")

    assert result.succeeded is False
    assert result.failure.code is EvaluationFailureCode.CORPUS_NOT_FOUND


def test_a_malformed_corpus_fails_as_invalid(
    db_session: Session, tmp_path: Path
) -> None:
    (tmp_path / "broken.yaml").write_text(
        "corpus_id: broken\n", encoding="utf-8"
    )

    result = _evaluate(
        db_session,
        corpus_id="broken",
        corpus_repository=YamlReferenceCorpusRepository(tmp_path),
    )

    assert result.failure.code is EvaluationFailureCode.INVALID_CORPUS


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(EvaluationReportRepository):
        def save(self, report):
            raise RuntimeError("the disk is full")

        def get(self, report_id):
            return None

        def list_for_corpus(self, corpus_id):
            return ()

    result = _evaluate(db_session, report_repository=FailingRepository())

    assert result.failure.code is (
        EvaluationFailureCode.REPORT_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    result = _evaluate(db_session, corpus_id="no_such_corpus")

    assert result.failure.message
    assert result.stored is None
