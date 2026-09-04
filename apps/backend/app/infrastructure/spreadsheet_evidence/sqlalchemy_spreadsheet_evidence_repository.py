from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceStatus,
    EvidenceType,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    CellEvidenceProvenance,
    SpreadsheetEvidence,
    SpreadsheetEvidenceSet,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_repository import (
    SpreadsheetEvidenceRepository,
)
from app.models.spreadsheet_evidence import (
    SpreadsheetEvidenceRecord,
    SpreadsheetEvidenceSetRecord,
)


class SqlAlchemySpreadsheetEvidenceRepository(SpreadsheetEvidenceRepository):
    """
    SQLAlchemy adapter over the two spreadsheet-evidence tables.

    Writes only those tables. It holds no reference to the canonical
    workbook's tables, to the document row, to the Engineering Index or
    to the Knowledge Graph - evidence is derived *from* a workbook, and
    deriving something must never modify what it was derived from. It
    writes no graph node, no graph edge, no index entry and no entity,
    because there is no such table in its reach.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, evidence_set: SpreadsheetEvidenceSet) -> None:
        """
        Persists ``OBSERVED`` and ``AMBIGUOUS`` items only.

        ``REJECTED`` candidates are diagnostics of what the extractor
        decided against. Storing them would put items in the evidence
        table that a later reader could mistake for observations.
        """

        persistable = tuple(
            item for item in evidence_set.evidence if item.is_persistable
        )

        record = SpreadsheetEvidenceSetRecord(
            artifact_identity=evidence_set.artifact_identity,
            upstream_identity=evidence_set.upstream_identity,
            document_id=evidence_set.document_id,
            project_id=evidence_set.project_id,
            content_checksum=evidence_set.content_checksum,
            representation_version=evidence_set.representation_version,
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
    ) -> SpreadsheetEvidenceSet | None:
        record = (
            self._session.query(SpreadsheetEvidenceSetRecord)
            .filter(
                SpreadsheetEvidenceSetRecord.document_id == document_id,
                SpreadsheetEvidenceSetRecord.artifact_identity
                == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> SpreadsheetEvidenceSet | None:
        record = (
            self._session.query(SpreadsheetEvidenceSetRecord)
            .filter(SpreadsheetEvidenceSetRecord.document_id == document_id)
            .order_by(SpreadsheetEvidenceSetRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _evidence_record(item: SpreadsheetEvidence) -> SpreadsheetEvidenceRecord:
    provenance = item.provenance
    quantity = item.quantity

    return SpreadsheetEvidenceRecord(
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
        worksheet_index=provenance.worksheet_index,
        worksheet_name=provenance.worksheet_name,
        row_number=provenance.row_number,
        column_number=provenance.column_number,
        column_label=provenance.column_label,
        character_start=provenance.character_start,
        character_end=provenance.character_end,
        source_text=provenance.source_text,
    )


def _to_domain(
    record: SpreadsheetEvidenceSetRecord,
) -> SpreadsheetEvidenceSet:
    return SpreadsheetEvidenceSet(
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
        document_id=record.document_id,
        project_id=record.project_id,
        content_checksum=record.content_checksum,
        representation_version=record.representation_version,
        extraction_policy_version=record.extraction_policy_version,
        evidence=tuple(_to_evidence(item) for item in record.evidence),
    )


def _to_evidence(record: SpreadsheetEvidenceRecord) -> SpreadsheetEvidence:
    return SpreadsheetEvidence(
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
        provenance=CellEvidenceProvenance(
            worksheet_index=record.worksheet_index,
            worksheet_name=record.worksheet_name,
            row_number=record.row_number,
            column_number=record.column_number,
            column_label=record.column_label,
            character_start=record.character_start,
            character_end=record.character_end,
            source_text=record.source_text,
        ),
    )


def _to_quantity(
    record: SpreadsheetEvidenceRecord,
) -> EngineeringQuantity | None:
    """
    Values are normalised on the way out.

    A numeric column returns a ``Decimal`` whose exponent reflects the
    column's declared scale, so ``Decimal("630")`` stored comes back as
    ``Decimal("630.000000")``. Both are the same number and
    ``Decimal.__eq__`` agrees, so the value objects compare equal either
    way - ``normalize`` is applied so a reader sees the number the
    register wrote rather than the column's padding.
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
