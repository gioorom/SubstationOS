from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.evidence_evaluation.evaluation_models import (
    DocumentEvaluation,
    EvaluationOutcome,
    EvaluationReport,
    EvidenceEvaluationResult,
    MismatchReason,
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.evaluation_policy import (
    EVALUATION_FRAMEWORK_VERSION,
)
from app.domain.evidence_evaluation.evaluation_report_repository import (
    EvaluationReportRepository,
    StoredEvaluationReport,
)
from app.models.evidence_evaluation import (
    DocumentEvaluationRecord,
    EvaluationReportRecord,
    EvaluationRuleVersionRecord,
    EvidenceEvaluationResultRecord,
)


class SqlAlchemyEvaluationReportRepository(EvaluationReportRepository):
    """
    SQLAlchemy adapter over the four evaluation tables.

    Writes only those tables. It holds no reference to the engineering
    evidence tables, to canonical text, or to a corpus file - a
    measurement must not be able to modify what it measured.

    Reports are **insert-only**: there is no update path, because a
    rewritten report would erase the history regression detection is made
    of.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, report: EvaluationReport) -> StoredEvaluationReport:
        metrics = report.metrics
        record = EvaluationReportRecord(
            corpus_id=report.corpus_id,
            corpus_version=report.corpus_version,
            extraction_policy_version=report.extraction_policy_version,
            evaluation_framework_version=EVALUATION_FRAMEWORK_VERSION,
            provenance_policy=report.provenance_policy,
            true_positives=metrics.true_positives,
            false_positives=metrics.false_positives,
            false_negatives=metrics.false_negatives,
        )

        for rule_id, rule_version in report.rule_versions:
            record.rule_versions.append(
                EvaluationRuleVersionRecord(
                    rule_id=rule_id, rule_version=rule_version
                )
            )

        for document in report.documents:
            record.documents.append(_document_record(document))

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        return _to_domain(record)

    def get(self, report_id: int) -> StoredEvaluationReport | None:
        record = self._session.get(EvaluationReportRecord, report_id)

        return _to_domain(record) if record is not None else None

    def list_for_corpus(
        self, corpus_id: str
    ) -> tuple[StoredEvaluationReport, ...]:
        records = (
            self._session.query(EvaluationReportRecord)
            .filter(EvaluationReportRecord.corpus_id == corpus_id)
            .order_by(EvaluationReportRecord.id.desc())
            .all()
        )

        return tuple(_to_domain(record) for record in records)


# --- Mapping ----------------------------------------------------------


def _document_record(
    document: DocumentEvaluation,
) -> DocumentEvaluationRecord:
    record = DocumentEvaluationRecord(
        document_ref=document.document_ref, title=document.title
    )

    for result in document.results:
        page, paragraph, line, token_start, token_end = result.location
        record.results.append(
            EvidenceEvaluationResultRecord(
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
        )

    return record


def _to_domain(record: EvaluationReportRecord) -> StoredEvaluationReport:
    """
    Rebuilds the report value.

    ``expected`` and ``actual`` come back as ``None``: the annotation
    lives in the corpus file and the evidence in the evidence tables, and
    copying either into this table would create a third source of truth
    that could go stale. Everything regression detection compares - the
    identity, the rule, the location, the reason - is stored, and a test
    asserts a comparison over reloaded reports agrees with one over
    in-memory reports.
    """

    return StoredEvaluationReport(
        report_id=record.id,
        created_at=record.created_at.isoformat(),
        report=EvaluationReport(
            corpus_id=record.corpus_id,
            corpus_version=record.corpus_version,
            extraction_policy_version=record.extraction_policy_version,
            provenance_policy=ProvenanceMatchPolicy(
                record.provenance_policy
            ),
            rule_versions=tuple(
                (entry.rule_id, entry.rule_version)
                for entry in record.rule_versions
            ),
            documents=tuple(
                DocumentEvaluation(
                    document_ref=document.document_ref,
                    title=document.title,
                    results=tuple(
                        EvidenceEvaluationResult(
                            outcome=EvaluationOutcome(result.outcome),
                            evidence_type=EvidenceType(result.evidence_type),
                            observed_text=result.observed_text,
                            rule_id=result.rule_id,
                            rule_version=result.rule_version,
                            location=(
                                result.page_number,
                                result.paragraph_index,
                                result.line_index,
                                result.token_start,
                                result.token_end,
                            ),
                            mismatch_reason=(
                                MismatchReason(result.mismatch_reason)
                                if result.mismatch_reason is not None
                                else None
                            ),
                        )
                        for result in document.results
                    ),
                )
                for document in record.documents
            ),
        ),
    )
