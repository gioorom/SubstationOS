"""
Small in-memory corpora for the evaluation framework's own unit tests.

These are **not** reference corpora. The reference corpus is a
version-controlled YAML file and is never written in a test - that rule
exists so nobody can quietly make the extractor look good by editing the
expectations beside the assertion.

What these build is the *input to the matcher*: two hand-made sides,
constructed so a single property of the comparison can be isolated. A
test that needed a real document to prove precision arithmetic would be
testing three things at once.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringEvidence,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
    SpanReference,
)
from app.domain.evidence_evaluation.corpus_models import (
    ExpectedObservation,
    ReferenceCorpus,
    ReferenceDocument,
)

RULE_FOR_TYPE = {
    EvidenceType.DESIGNATION: "designation_generic",
    EvidenceType.VOLTAGE_VALUE: "voltage_value",
    EvidenceType.CURRENT_VALUE: "current_value",
    EvidenceType.POWER_VALUE: "power_value",
    EvidenceType.CABLE_SECTION_VALUE: "cable_section_value",
}


def provenance(
    *,
    line: int = 0,
    token_start: int = 0,
    token_end: int = 1,
    page: int = 1,
    paragraph: int = 0,
    span: int = 0,
    character_start: int = 0,
    character_end: int = 5,
    source_text: str = "T1",
) -> EvidenceProvenance:
    return EvidenceProvenance(
        page_number=page,
        section_index=page - 1,
        paragraph_index=paragraph,
        block_reading_order=paragraph,
        line_index=line,
        token_start=token_start,
        token_end=token_end,
        spans=(
            SpanReference(
                span_reading_order=span,
                character_start=character_start,
                character_end=character_end,
            ),
        ),
        source_text=source_text,
    )


def expected(
    *,
    evidence_type: EvidenceType = EvidenceType.DESIGNATION,
    observed_text: str = "T1",
    status: EvidenceStatus = EvidenceStatus.OBSERVED,
    quantity: EngineeringQuantity | None = None,
    designation: str | None = "T1",
    rule_version: str = "1.0",
    **provenance_kwargs,
) -> ExpectedObservation:
    return ExpectedObservation(
        evidence_type=evidence_type,
        observed_text=observed_text,
        status=status,
        rule_id=RULE_FOR_TYPE[evidence_type],
        rule_version=rule_version,
        quantity=quantity,
        designation=(
            DesignationValue(normalized=designation)
            if designation is not None
            else None
        ),
        provenance=provenance(
            source_text=observed_text, **provenance_kwargs
        ),
    )


def extracted(
    *,
    evidence_type: EvidenceType = EvidenceType.DESIGNATION,
    observed_text: str = "T1",
    status: EvidenceStatus = EvidenceStatus.OBSERVED,
    quantity: EngineeringQuantity | None = None,
    designation: str | None = "T1",
    rule_version: str = "1.0",
    **provenance_kwargs,
) -> EngineeringEvidence:
    return EngineeringEvidence(
        evidence_key=f"key-{observed_text}-{provenance_kwargs}",
        evidence_type=evidence_type,
        status=status,
        observed_text=observed_text,
        rule_id=RULE_FOR_TYPE[evidence_type],
        rule_version=rule_version,
        quantity=quantity,
        designation=(
            DesignationValue(normalized=designation)
            if designation is not None
            else None
        ),
        provenance=provenance(
            source_text=observed_text, **provenance_kwargs
        ),
    )


def voltage(value: str = "20") -> EngineeringQuantity:
    return EngineeringQuantity(
        value=Decimal(value),
        unit="kV",
        base_value=Decimal(value) * 1000,
        base_unit="V",
    )


def document(
    *expectations: ExpectedObservation, document_ref: str = "doc"
) -> ReferenceDocument:
    return ReferenceDocument(
        document_ref=document_ref,
        title="A reference document",
        lines=("Trasformatore T1 20 kV",),
        expected=expectations,
    )


def corpus(
    *documents: ReferenceDocument,
    corpus_version: str = "1.0",
    corpus_id: str = "unit_corpus",
) -> ReferenceCorpus:
    return ReferenceCorpus(
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        description="Built in memory for a framework unit test.",
        annotated_against_policy_version="1.0",
        annotated_rule_versions=(("designation_generic", "1.0"),),
        documents=documents,
    )
