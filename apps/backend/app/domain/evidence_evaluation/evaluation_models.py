"""
Evaluation report models (Milestone 28.2).

```
EvaluationReport            one corpus, one rule catalogue, one run
  └─ DocumentEvaluation     one reference document
       └─ EvidenceEvaluationResult   one expected or extracted item
```

Every level is immutable, and **nothing carries a timestamp**: two runs
of the same evaluation over the same corpus and the same rule catalogue
must compare equal, and a timestamp would make that impossible. When a
report was produced is a fact about the stored row.

## Only exact matches count

A true positive requires the extractor's item and the corpus's
expectation to agree on *everything*: evidence type, observed text,
status, typed value, and provenance. An observation with the right text
in the wrong place is **not** a match - it is a false positive and a
false negative, because a downstream consumer that trusted its location
would be reading the wrong part of the document.

Approximate matching is deliberately absent. If it is ever introduced it
must be a named, versioned policy recorded on the report, exactly as the
provenance policy already is - a fuzzy match nobody declared would
silently inflate every metric in this system.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidence,
    EvidenceType,
)
from app.domain.evidence_evaluation.corpus_models import ExpectedObservation
from app.domain.evidence_evaluation.evaluation_metrics import (
    EvaluationMetrics,
)


class EvaluationOutcome(str, Enum):
    """
    What happened to one item.

    Three outcomes, and deliberately no fourth: there is no "partial"
    and no "near miss". A near miss is a false positive paired with a
    false negative, and reporting it as anything softer would let a rule
    that puts values in the wrong place look almost right.
    """

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class MismatchReason(str, Enum):
    """
    Why an extracted item and an expectation at the same location failed
    to match.

    Diagnostic only - it never changes the outcome. Its job is to turn
    "recall dropped" into "recall dropped because provenance moved",
    which is the difference between a usable regression report and a
    number nobody can act on.
    """

    # Nothing was expected at that location at all, or nothing was
    # extracted where something was expected.
    UNPAIRED = "unpaired"
    EVIDENCE_TYPE = "evidence_type"
    OBSERVED_TEXT = "observed_text"
    STATUS = "status"
    QUANTITY = "quantity"
    DESIGNATION = "designation"
    PROVENANCE = "provenance"


class ProvenanceMatchPolicy(str, Enum):
    """
    How strictly provenance must agree.

    Declared, named and recorded on every report, so a comparison between
    two evaluations can never be a comparison between two different
    definitions of "match".

    ``EXACT`` is the default and the only one that verifies the full
    chain. ``LOCATION_ONLY`` exists for a real case - a corpus annotated
    before span character offsets were recorded - and is deliberately
    coarser: it checks page, paragraph, line and token range, and accepts
    any character ranges. It must never become the default by accident,
    which is why it has to be passed explicitly.
    """

    EXACT = "exact"
    LOCATION_ONLY = "location_only"


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationResult:
    """
    One item's verdict.

    Both sides are kept. A false positive carries what the extractor
    produced; a false negative carries what the corpus expected; a true
    positive carries both. Keeping them is what lets a regression report
    name the exact items involved rather than a count.
    """

    outcome: EvaluationOutcome
    evidence_type: EvidenceType
    observed_text: str
    rule_id: str
    rule_version: str
    location: tuple[int, int, int, int, int]
    expected: ExpectedObservation | None = None
    actual: EngineeringEvidence | None = None
    mismatch_reason: MismatchReason | None = None

    @property
    def is_correct(self) -> bool:
        return self.outcome is EvaluationOutcome.TRUE_POSITIVE

    @property
    def identity(self) -> tuple:
        """
        A stable identity for comparing one evaluation against another.

        Location, type and text - not the evidence key, which encodes the
        document checksum and would make two corpus versions of the same
        document incomparable.
        """

        return (
            self.evidence_type.value,
            self.observed_text,
            self.location,
        )


@dataclass(frozen=True, slots=True)
class DocumentEvaluation:
    """One reference document's results and its own metrics."""

    document_ref: str
    title: str
    results: tuple[EvidenceEvaluationResult, ...] = ()

    @property
    def metrics(self) -> EvaluationMetrics:
        return _metrics_of(self.results)

    def with_outcome(
        self, outcome: EvaluationOutcome
    ) -> tuple[EvidenceEvaluationResult, ...]:
        return tuple(
            result for result in self.results if result.outcome is outcome
        )


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """
    One evaluation of one corpus under one rule catalogue.

    The four version fields are what make a historical report meaningful:
    which corpus, at which version, evaluated against which extraction
    policy, with which provenance policy. A report missing any of them
    could not be compared with another honestly.

    ``rule_versions`` records the version of every rule in the catalogue
    at evaluation time, so "which rule changed?" is answerable from two
    reports alone.
    """

    corpus_id: str
    corpus_version: str
    extraction_policy_version: str
    provenance_policy: ProvenanceMatchPolicy
    rule_versions: tuple[tuple[str, str], ...]
    documents: tuple[DocumentEvaluation, ...] = ()

    @property
    def results(self) -> tuple[EvidenceEvaluationResult, ...]:
        return tuple(
            result
            for document in self.documents
            for result in document.results
        )

    @property
    def metrics(self) -> EvaluationMetrics:
        return _metrics_of(self.results)

    @property
    def metrics_by_evidence_type(self) -> dict[str, EvaluationMetrics]:
        return _grouped(
            self.results, lambda result: result.evidence_type.value
        )

    @property
    def metrics_by_rule(self) -> dict[str, EvaluationMetrics]:
        return _grouped(
            self.results,
            lambda result: f"{result.rule_id}@{result.rule_version}",
        )

    @property
    def metrics_by_document(self) -> dict[str, EvaluationMetrics]:
        return {
            document.document_ref: document.metrics
            for document in self.documents
        }


def _metrics_of(
    results: tuple[EvidenceEvaluationResult, ...],
) -> EvaluationMetrics:
    return EvaluationMetrics(
        true_positives=sum(
            1
            for result in results
            if result.outcome is EvaluationOutcome.TRUE_POSITIVE
        ),
        false_positives=sum(
            1
            for result in results
            if result.outcome is EvaluationOutcome.FALSE_POSITIVE
        ),
        false_negatives=sum(
            1
            for result in results
            if result.outcome is EvaluationOutcome.FALSE_NEGATIVE
        ),
    )


def _grouped(results, key) -> dict[str, EvaluationMetrics]:
    """Grouped in first-appearance order, so a report renders the same
    way twice."""

    grouped: dict[str, list] = {}

    for result in results:
        grouped.setdefault(key(result), []).append(result)

    return {
        name: _metrics_of(tuple(group)) for name, group in grouped.items()
    }
