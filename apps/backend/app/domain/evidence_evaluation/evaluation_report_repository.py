"""
The persistence port for evaluation reports (Milestone 28.2).

**Evaluation never modifies engineering evidence, and never writes a
corpus.** This port stores reports and reads them back, and there is
nothing else on it - a method that could touch an evidence set would let
a measurement change the thing it is measuring.

A new rule version produces a **new** report. There is deliberately no
``update``: overwriting a report would destroy the history that
regression detection is made of.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.evidence_evaluation.evaluation_models import EvaluationReport


@dataclass(frozen=True, slots=True)
class StoredEvaluationReport:
    """
    A report with the identity storage gave it.

    The identity is kept **beside** the report rather than on it, so the
    report itself stays a pure value that two runs can compare equal.
    ``created_at`` is here for the same reason.
    """

    report_id: int
    created_at: str
    report: EvaluationReport


class EvaluationReportRepository(ABC):
    """Stores and retrieves evaluation reports."""

    @abstractmethod
    def save(self, report: EvaluationReport) -> StoredEvaluationReport:
        """Insert a report and return it with its storage identity."""

        raise NotImplementedError

    @abstractmethod
    def get(self, report_id: int) -> StoredEvaluationReport | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_corpus(
        self, corpus_id: str
    ) -> tuple[StoredEvaluationReport, ...]:
        """Every report for a corpus, newest first - the history a
        reviewer compares across."""

        raise NotImplementedError
