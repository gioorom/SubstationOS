from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.engineering_evidence.engineering_evidence_repository import (
    EngineeringEvidenceRepository,
)
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringEvidence,
    EngineeringEvidenceSet,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
    SpanReference,
)
from app.models.engineering_evidence import (
    EngineeringEvidenceRecord,
    EngineeringEvidenceSetRecord,
    EngineeringEvidenceSpanRecord,
)


class SqlAlchemyEngineeringEvidenceRepository(EngineeringEvidenceRepository):
    """
    SQLAlchemy adapter over the three engineering-evidence tables.

    Writes only those tables. It holds no reference to the canonical
    text's tables, to the document row, to the Engineering Index or to
    the Knowledge Graph - evidence is derived *from* canonical text, and
    deriving something must never modify what it was derived from.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, evidence_set: EngineeringEvidenceSet) -> None:
        """
        Persists ``OBSERVED`` and ``AMBIGUOUS`` items only.

        ``REJECTED`` candidates are diagnostics of what the extractor
        decided against. Storing them would put items in the evidence
        table that a later reader could mistake for observations.
        """

        persistable = tuple(
            item for item in evidence_set.evidence if item.is_persistable
        )

        record = EngineeringEvidenceSetRecord(
            artifact_identity=evidence_set.artifact_identity,
            upstream_identity=evidence_set.upstream_identity,
            document_id=evidence_set.document_id,
            project_id=evidence_set.project_id,
            content_checksum=evidence_set.content_checksum,
            segmentation_version=evidence_set.segmentation_version,
            extraction_policy_version=(
                evidence_set.extraction_policy_version
            ),
            evidence_count=len(persistable),
        )

        for item in persistable:
            record.evidence.append(_evidence_record(item))

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringEvidenceSet | None:
        record = (
            self._session.query(EngineeringEvidenceSetRecord)
            .filter(
                EngineeringEvidenceSetRecord.document_id == document_id,
                EngineeringEvidenceSetRecord.artifact_identity == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringEvidenceSet | None:
        record = (
            self._session.query(EngineeringEvidenceSetRecord)
            .filter(EngineeringEvidenceSetRecord.document_id == document_id)
            .order_by(EngineeringEvidenceSetRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _evidence_record(
    item: EngineeringEvidence,
) -> EngineeringEvidenceRecord:
    provenance = item.provenance
    quantity = item.quantity

    record = EngineeringEvidenceRecord(
        evidence_key=item.evidence_key,
        evidence_type=item.evidence_type,
        status=item.status,
        observed_text=item.observed_text,
        rule_id=item.rule_id,
        rule_version=item.rule_version,
        quantity_value=quantity.value if quantity is not None else None,
        quantity_unit=quantity.unit if quantity is not None else None,
        quantity_base_value=(
            quantity.base_value if quantity is not None else None
        ),
        quantity_base_unit=(
            quantity.base_unit if quantity is not None else None
        ),
        designation_normalized=(
            item.designation.normalized
            if item.designation is not None
            else None
        ),
        page_number=provenance.page_number,
        section_index=provenance.section_index,
        paragraph_index=provenance.paragraph_index,
        block_reading_order=provenance.block_reading_order,
        line_index=provenance.line_index,
        token_start=provenance.token_start,
        token_end=provenance.token_end,
        source_text=provenance.source_text,
    )

    for span in provenance.spans:
        record.spans.append(
            EngineeringEvidenceSpanRecord(
                span_reading_order=span.span_reading_order,
                character_start=span.character_start,
                character_end=span.character_end,
            )
        )

    return record


def _to_domain(
    record: EngineeringEvidenceSetRecord,
) -> EngineeringEvidenceSet:
    return EngineeringEvidenceSet(
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
        document_id=record.document_id,
        project_id=record.project_id,
        content_checksum=record.content_checksum,
        segmentation_version=record.segmentation_version,
        extraction_policy_version=record.extraction_policy_version,
        evidence=tuple(_to_evidence(item) for item in record.evidence),
    )


def _to_evidence(
    record: EngineeringEvidenceRecord,
) -> EngineeringEvidence:
    return EngineeringEvidence(
        evidence_key=record.evidence_key,
        evidence_type=EvidenceType(record.evidence_type),
        status=EvidenceStatus(record.status),
        observed_text=record.observed_text,
        rule_id=record.rule_id,
        rule_version=record.rule_version,
        quantity=_to_quantity(record),
        designation=(
            DesignationValue(normalized=record.designation_normalized)
            if record.designation_normalized is not None
            else None
        ),
        provenance=EvidenceProvenance(
            page_number=record.page_number,
            section_index=record.section_index,
            paragraph_index=record.paragraph_index,
            block_reading_order=record.block_reading_order,
            line_index=record.line_index,
            token_start=record.token_start,
            token_end=record.token_end,
            spans=tuple(
                SpanReference(
                    span_reading_order=span.span_reading_order,
                    character_start=span.character_start,
                    character_end=span.character_end,
                )
                for span in record.spans
            ),
            source_text=record.source_text,
        ),
    )


def _to_quantity(
    record: EngineeringEvidenceRecord,
) -> EngineeringQuantity | None:
    """
    Values are normalised on the way out.

    SQLite returns a ``Decimal`` whose exponent reflects the column's
    declared scale, so ``Decimal("20")`` stored comes back as
    ``Decimal("20.000000")``. Both are the same number, and
    ``Decimal.__eq__`` agrees - but the value objects compare by
    dataclass equality, which uses ``==`` on each field, so this is
    equality-safe either way. ``normalize()`` is applied so a reader sees
    the number the document wrote rather than the column's padding.
    """

    if record.quantity_value is None or record.quantity_unit is None:
        return None

    return EngineeringQuantity(
        value=_normalized(record.quantity_value),
        unit=record.quantity_unit,
        base_value=(
            _normalized(record.quantity_base_value)
            if record.quantity_base_value is not None
            else None
        ),
        base_unit=record.quantity_base_unit,
    )


def _normalized(value: Decimal) -> Decimal:
    normalized = Decimal(value).normalize()

    # ``normalize`` renders large integers in exponent form
    # (Decimal("630000") -> Decimal("6.3E+5")). Equal as numbers, but
    # surprising to read back, so integral values are restored to plain
    # notation.
    return (
        normalized.quantize(Decimal(1))
        if normalized == normalized.to_integral_value()
        else normalized
    )
