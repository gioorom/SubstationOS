from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.engineering_entities.engineering_entity_repository import (
    EngineeringEntityRepository,
)
from app.domain.engineering_entities.entity_models import (
    EngineeringEntity,
    EngineeringEntitySet,
    EntityStatus,
    EntityType,
    EvidenceReference,
)
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceType,
)
from app.models.engineering_entities import (
    EngineeringEntityEvidenceRecord,
    EngineeringEntityRecord,
    EngineeringEntitySetRecord,
)


class SqlAlchemyEngineeringEntityRepository(EngineeringEntityRepository):
    """
    SQLAlchemy adapter over the three engineering-entity tables.

    Writes only those tables. It holds no reference to the engineering
    evidence tables, to canonical text, to the document row or to the
    Knowledge Graph - entities are resolved *from* evidence, and
    resolving something must never modify what it was resolved from.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, entity_set: EngineeringEntitySet) -> None:
        record = EngineeringEntitySetRecord(
            artifact_identity=entity_set.artifact_identity,
            upstream_identity=entity_set.upstream_identity,
            document_id=entity_set.document_id,
            project_id=entity_set.project_id,
            content_checksum=entity_set.content_checksum,
            extraction_policy_version=(
                entity_set.extraction_policy_version
            ),
            resolution_policy_version=(
                entity_set.resolution_policy_version
            ),
            entity_count=entity_set.entity_count,
        )

        for entity in entity_set.entities:
            record.entities.append(_entity_record(entity))

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringEntitySet | None:
        record = (
            self._session.query(EngineeringEntitySetRecord)
            .filter(
                EngineeringEntitySetRecord.document_id == document_id,
                EngineeringEntitySetRecord.artifact_identity == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringEntitySet | None:
        record = (
            self._session.query(EngineeringEntitySetRecord)
            .filter(EngineeringEntitySetRecord.document_id == document_id)
            .order_by(EngineeringEntitySetRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _entity_record(entity: EngineeringEntity) -> EngineeringEntityRecord:
    quantity = entity.quantity

    record = EngineeringEntityRecord(
        entity_key=entity.entity_key,
        entity_type=entity.entity_type,
        status=entity.status,
        entity_version=entity.entity_version,
        resolution_rule_id=entity.resolution_rule_id,
        resolution_rule_version=entity.resolution_rule_version,
        designation_normalized=(
            entity.designation.normalized
            if entity.designation is not None
            else None
        ),
        quantity_value=quantity.value if quantity is not None else None,
        quantity_unit=quantity.unit if quantity is not None else None,
        quantity_base_value=(
            quantity.base_value if quantity is not None else None
        ),
        quantity_base_unit=(
            quantity.base_unit if quantity is not None else None
        ),
    )

    for reference in entity.evidence:
        record.evidence.append(
            EngineeringEntityEvidenceRecord(
                evidence_key=reference.evidence_key,
                evidence_type=reference.evidence_type,
                observed_text=reference.observed_text,
                page_number=reference.page_number,
                paragraph_index=reference.paragraph_index,
                line_index=reference.line_index,
                token_start=reference.token_start,
                token_end=reference.token_end,
            )
        )

    return record


def _to_domain(
    record: EngineeringEntitySetRecord,
) -> EngineeringEntitySet:
    return EngineeringEntitySet(
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
        document_id=record.document_id,
        project_id=record.project_id,
        content_checksum=record.content_checksum,
        extraction_policy_version=record.extraction_policy_version,
        resolution_policy_version=record.resolution_policy_version,
        entities=tuple(
            _to_entity(entity, record.document_id)
            for entity in record.entities
        ),
    )


def _to_entity(
    record: EngineeringEntityRecord, document_id: int
) -> EngineeringEntity:
    return EngineeringEntity(
        entity_key=record.entity_key,
        entity_type=EntityType(record.entity_type),
        status=EntityStatus(record.status),
        document_id=document_id,
        entity_version=record.entity_version,
        resolution_rule_id=record.resolution_rule_id,
        resolution_rule_version=record.resolution_rule_version,
        designation=(
            DesignationValue(normalized=record.designation_normalized)
            if record.designation_normalized is not None
            else None
        ),
        quantity=_to_quantity(record),
        evidence=tuple(
            EvidenceReference(
                evidence_key=reference.evidence_key,
                evidence_type=EvidenceType(reference.evidence_type),
                observed_text=reference.observed_text,
                page_number=reference.page_number,
                paragraph_index=reference.paragraph_index,
                line_index=reference.line_index,
                token_start=reference.token_start,
                token_end=reference.token_end,
            )
            for reference in record.evidence
        ),
    )


def _to_quantity(
    record: EngineeringEntityRecord,
) -> EngineeringQuantity | None:
    """Values are normalised on the way out, so a reader sees the number
    the document wrote rather than the column's declared scale."""

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

    return (
        normalized.quantize(Decimal(1))
        if normalized == normalized.to_integral_value()
        else normalized
    )
