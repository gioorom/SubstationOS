from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_facts.engineering_fact_repository import (
    EngineeringFactRepository,
)
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    EngineeringFact,
    EngineeringFactSet,
    FactConstructionDiagnostic,
    FactStatus,
    FactSupport,
    SupportRole,
)
from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.models.engineering_facts import (
    EngineeringFactRecord,
    EngineeringFactSetRecord,
    EngineeringFactSupportRecord,
    FactConstructionDiagnosticRecord,
)

# Diagnostic candidate keys are stored as a readable list for a human
# deciding what an ambiguous line meant - never joined on, so a simple
# separator is enough and a JSON column would be ceremony.
_KEY_SEPARATOR = ","


class SqlAlchemyEngineeringFactRepository(EngineeringFactRepository):
    """
    SQLAlchemy adapter over the four engineering-fact tables.

    Writes only those tables. It holds no reference to the entity tables,
    the evidence tables, canonical text, the document row or the
    Knowledge Graph - facts are constructed *from* entities, and
    constructing something must never modify what it was constructed
    from.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, fact_set: EngineeringFactSet) -> None:
        record = EngineeringFactSetRecord(
            artifact_identity=fact_set.artifact_identity,
            upstream_identity=fact_set.upstream_identity,
            document_id=fact_set.document_id,
            project_id=fact_set.project_id,
            content_checksum=fact_set.content_checksum,
            extraction_policy_version=(
                fact_set.extraction_policy_version
            ),
            resolution_policy_version=(
                fact_set.resolution_policy_version
            ),
            fact_policy_version=fact_set.fact_policy_version,
            fact_count=fact_set.fact_count,
        )

        for fact in fact_set.facts:
            record.facts.append(_fact_record(fact))

        for diagnostic in fact_set.diagnostics:
            record.diagnostics.append(_diagnostic_record(diagnostic))

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringFactSet | None:
        record = (
            self._session.query(EngineeringFactSetRecord)
            .filter(
                EngineeringFactSetRecord.document_id == document_id,
                EngineeringFactSetRecord.artifact_identity == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringFactSet | None:
        record = (
            self._session.query(EngineeringFactSetRecord)
            .filter(EngineeringFactSetRecord.document_id == document_id)
            .order_by(EngineeringFactSetRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _fact_record(fact: EngineeringFact) -> EngineeringFactRecord:
    record = EngineeringFactRecord(
        fact_key=fact.fact_key,
        subject_entity_key=fact.subject_entity_key,
        predicate=fact.predicate,
        object_entity_key=fact.object_entity_key,
        status=fact.status,
        fact_version=fact.fact_version,
        construction_rule_id=fact.construction_rule_id,
        construction_rule_version=fact.construction_rule_version,
    )

    for reference in fact.support:
        record.support.append(
            EngineeringFactSupportRecord(
                evidence_key=reference.evidence_key,
                role=reference.role,
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


def _diagnostic_record(
    diagnostic: FactConstructionDiagnostic,
) -> FactConstructionDiagnosticRecord:
    return FactConstructionDiagnosticRecord(
        reason=diagnostic.reason,
        page_number=diagnostic.page_number,
        paragraph_index=diagnostic.paragraph_index,
        line_index=diagnostic.line_index,
        subject_entity_keys=_KEY_SEPARATOR.join(
            diagnostic.subject_entity_keys
        ),
        object_entity_keys=_KEY_SEPARATOR.join(
            diagnostic.object_entity_keys
        ),
    )


def _to_domain(record: EngineeringFactSetRecord) -> EngineeringFactSet:
    return EngineeringFactSet(
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
        document_id=record.document_id,
        project_id=record.project_id,
        content_checksum=record.content_checksum,
        extraction_policy_version=record.extraction_policy_version,
        resolution_policy_version=record.resolution_policy_version,
        fact_policy_version=record.fact_policy_version,
        facts=tuple(_to_fact(fact, record) for fact in record.facts),
        diagnostics=tuple(
            _to_diagnostic(diagnostic) for diagnostic in record.diagnostics
        ),
    )


def _to_fact(
    record: EngineeringFactRecord, fact_set: EngineeringFactSetRecord
) -> EngineeringFact:
    return EngineeringFact(
        fact_key=record.fact_key,
        document_id=fact_set.document_id,
        project_id=fact_set.project_id,
        subject_entity_key=record.subject_entity_key,
        predicate=FactPredicate(record.predicate),
        object_entity_key=record.object_entity_key,
        status=FactStatus(record.status),
        fact_version=record.fact_version,
        construction_rule_id=record.construction_rule_id,
        construction_rule_version=record.construction_rule_version,
        support=tuple(
            FactSupport(
                evidence_key=reference.evidence_key,
                role=SupportRole(reference.role),
                evidence_type=EvidenceType(reference.evidence_type),
                observed_text=reference.observed_text,
                page_number=reference.page_number,
                paragraph_index=reference.paragraph_index,
                line_index=reference.line_index,
                token_start=reference.token_start,
                token_end=reference.token_end,
            )
            for reference in record.support
        ),
    )


def _to_diagnostic(
    record: FactConstructionDiagnosticRecord,
) -> FactConstructionDiagnostic:
    return FactConstructionDiagnostic(
        reason=AmbiguityReason(record.reason),
        page_number=record.page_number,
        paragraph_index=record.paragraph_index,
        line_index=record.line_index,
        subject_entity_keys=_split(record.subject_entity_keys),
        object_entity_keys=_split(record.object_entity_keys),
    )


def _split(value: str) -> tuple[str, ...]:
    return tuple(value.split(_KEY_SEPARATOR)) if value else ()
