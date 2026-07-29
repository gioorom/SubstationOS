from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationOutcome,
    MismatchReason,
    ProvenanceMatchPolicy,
)


class EvaluationReportRecord(Base):
    """
    One evaluation of one corpus under one rule catalogue
    (Milestone 28.2).

    Stored **independently of engineering evidence**, which it never
    modifies, and of the reference corpora, which are files and are never
    written at runtime.

    A new rule version produces a new report; nothing is overwritten.
    That is the whole basis of regression detection: the history is the
    comparison.
    """

    __tablename__ = "evidence_evaluation_reports"

    __table_args__ = (
        Index(
            "ix_evidence_evaluation_reports_corpus_created",
            "corpus_id",
            "created_at",
        ),
        Index(
            "ix_evidence_evaluation_reports_policy",
            "corpus_id",
            "extraction_policy_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    corpus_id: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    corpus_version: Mapped[str] = mapped_column(String(20), nullable=False)

    extraction_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    evaluation_framework_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    provenance_policy: Mapped[ProvenanceMatchPolicy] = mapped_column(
        SqlEnum(ProvenanceMatchPolicy),
        nullable=False,
    )

    true_positives: Mapped[int] = mapped_column(Integer, nullable=False)

    false_positives: Mapped[int] = mapped_column(Integer, nullable=False)

    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    rule_versions: Mapped[list["EvaluationRuleVersionRecord"]] = relationship(
        "EvaluationRuleVersionRecord",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="EvaluationRuleVersionRecord.rule_id",
    )

    documents: Mapped[list["DocumentEvaluationRecord"]] = relationship(
        "DocumentEvaluationRecord",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="DocumentEvaluationRecord.id",
    )


class EvaluationRuleVersionRecord(Base):
    """
    One rule and its version at evaluation time.

    A child table rather than a serialised map, because "which rule
    changed between these two reports?" is a query, and the answer must
    not require parsing a blob.
    """

    __tablename__ = "evidence_evaluation_rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    report_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_evaluation_reports.id"),
        nullable=False,
        index=True,
    )

    rule_id: Mapped[str] = mapped_column(String(60), nullable=False)

    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)

    report: Mapped["EvaluationReportRecord"] = relationship(
        "EvaluationReportRecord",
        back_populates="rule_versions",
    )


class DocumentEvaluationRecord(Base):
    """One reference document's results within a report."""

    __tablename__ = "evidence_evaluation_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    report_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_evaluation_reports.id"),
        nullable=False,
        index=True,
    )

    document_ref: Mapped[str] = mapped_column(String(120), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    report: Mapped["EvaluationReportRecord"] = relationship(
        "EvaluationReportRecord",
        back_populates="documents",
    )

    results: Mapped[list["EvidenceEvaluationResultRecord"]] = relationship(
        "EvidenceEvaluationResultRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="EvidenceEvaluationResultRecord.id",
    )


class EvidenceEvaluationResultRecord(Base):
    """
    One item's verdict.

    ## What is stored, and what is not

    The **identifying** fields are stored: outcome, evidence type,
    observed text, rule and version, the location, and why a pair
    disagreed. Those are exactly what regression detection compares, so a
    comparison between two reloaded reports gives the same answer as one
    between two in-memory ones.

    The full expected and extracted value objects are **not** stored. The
    annotation lives in the corpus file and the evidence lives in the
    evidence tables; copying both here would duplicate two sources of
    truth into a third, which would then be the one that went stale.
    """

    __tablename__ = "evidence_evaluation_results"

    __table_args__ = (
        Index(
            "ix_evidence_evaluation_results_outcome",
            "document_evaluation_id",
            "outcome",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_evaluation_documents.id"),
        nullable=False,
        index=True,
    )

    outcome: Mapped[EvaluationOutcome] = mapped_column(
        SqlEnum(EvaluationOutcome),
        nullable=False,
    )

    evidence_type: Mapped[EvidenceType] = mapped_column(
        SqlEnum(EvidenceType),
        nullable=False,
    )

    observed_text: Mapped[str] = mapped_column(Text, nullable=False)

    rule_id: Mapped[str] = mapped_column(String(60), nullable=False)

    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)

    mismatch_reason: Mapped[MismatchReason | None] = mapped_column(
        SqlEnum(MismatchReason),
        nullable=True,
    )

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    token_start: Mapped[int] = mapped_column(Integer, nullable=False)

    token_end: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped["DocumentEvaluationRecord"] = relationship(
        "DocumentEvaluationRecord",
        back_populates="results",
    )
