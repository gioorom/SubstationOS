from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.engineering_semantics.engineering_semantic_repository import (
    EngineeringSemanticRepository,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
    EngineeringSemanticStatement,
    SemanticAmbiguityReason,
    SemanticInterpretationDiagnostic,
    SemanticStatementStatus,
)
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)
from app.models.engineering_semantics import (
    EngineeringSemanticSetRecord,
    EngineeringSemanticStatementRecord,
    SemanticInterpretationDiagnosticRecord,
    SemanticStatementSupportRecord,
)

# Candidate fact keys are stored as a readable list for a human deciding
# what an undecided subject meant - never joined on, so a simple
# separator is enough and a JSON column would be ceremony.
_KEY_SEPARATOR = ","


class SqlAlchemyEngineeringSemanticRepository(
    EngineeringSemanticRepository
):
    """
    SQLAlchemy adapter over the four engineering-semantic tables.

    Writes only those tables. It holds no reference to the fact tables,
    the entity tables, the evidence tables, canonical text, the document
    row or the Knowledge Graph - statements are interpreted *from* facts,
    and interpreting something must never modify what it was interpreted
    from.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, semantic_set: EngineeringSemanticSet) -> None:
        record = EngineeringSemanticSetRecord(
            artifact_identity=semantic_set.artifact_identity,
            upstream_identity=semantic_set.upstream_identity,
            document_id=semantic_set.document_id,
            project_id=semantic_set.project_id,
            content_checksum=semantic_set.content_checksum,
            extraction_policy_version=(
                semantic_set.extraction_policy_version
            ),
            resolution_policy_version=(
                semantic_set.resolution_policy_version
            ),
            fact_policy_version=semantic_set.fact_policy_version,
            semantic_policy_version=(
                semantic_set.semantic_policy_version
            ),
            statement_count=semantic_set.statement_count,
        )

        for statement in semantic_set.statements:
            record.statements.append(_statement_record(statement))

        for diagnostic in semantic_set.diagnostics:
            record.diagnostics.append(_diagnostic_record(diagnostic))

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringSemanticSet | None:
        record = (
            self._session.query(EngineeringSemanticSetRecord)
            .filter(
                EngineeringSemanticSetRecord.document_id == document_id,
                EngineeringSemanticSetRecord.artifact_identity == artifact_identity,
            )
            .one_or_none()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringSemanticSet | None:
        record = (
            self._session.query(EngineeringSemanticSetRecord)
            .filter(
                EngineeringSemanticSetRecord.document_id == document_id
            )
            .order_by(EngineeringSemanticSetRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _statement_record(
    statement: EngineeringSemanticStatement,
) -> EngineeringSemanticStatementRecord:
    record = EngineeringSemanticStatementRecord(
        statement_key=statement.statement_key,
        statement_type=statement.statement_type,
        subject_entity_key=statement.subject_entity_key,
        object_entity_key=statement.object_entity_key,
        status=statement.status,
        semantic_contract_version=statement.semantic_contract_version,
        semantic_rule_id=statement.semantic_rule_id,
        semantic_rule_version=statement.semantic_rule_version,
    )

    for fact_key in statement.supporting_fact_keys:
        record.support.append(
            SemanticStatementSupportRecord(fact_key=fact_key)
        )

    return record


def _diagnostic_record(
    diagnostic: SemanticInterpretationDiagnostic,
) -> SemanticInterpretationDiagnosticRecord:
    return SemanticInterpretationDiagnosticRecord(
        reason=diagnostic.reason,
        subject_entity_key=diagnostic.subject_entity_key,
        candidate_fact_keys=_KEY_SEPARATOR.join(
            diagnostic.candidate_fact_keys
        ),
    )


def _to_domain(
    record: EngineeringSemanticSetRecord,
) -> EngineeringSemanticSet:
    return EngineeringSemanticSet(
        artifact_identity=record.artifact_identity,
        upstream_identity=record.upstream_identity,
        document_id=record.document_id,
        project_id=record.project_id,
        content_checksum=record.content_checksum,
        extraction_policy_version=record.extraction_policy_version,
        resolution_policy_version=record.resolution_policy_version,
        fact_policy_version=record.fact_policy_version,
        semantic_policy_version=record.semantic_policy_version,
        statements=tuple(
            _to_statement(statement, record)
            for statement in record.statements
        ),
        diagnostics=tuple(
            _to_diagnostic(diagnostic)
            for diagnostic in record.diagnostics
        ),
    )


def _to_statement(
    record: EngineeringSemanticStatementRecord,
    semantic_set: EngineeringSemanticSetRecord,
) -> EngineeringSemanticStatement:
    return EngineeringSemanticStatement(
        statement_key=record.statement_key,
        statement_type=SemanticStatementType(record.statement_type),
        document_id=semantic_set.document_id,
        project_id=semantic_set.project_id,
        subject_entity_key=record.subject_entity_key,
        object_entity_key=record.object_entity_key,
        status=SemanticStatementStatus(record.status),
        semantic_contract_version=record.semantic_contract_version,
        semantic_rule_id=record.semantic_rule_id,
        semantic_rule_version=record.semantic_rule_version,
        supporting_fact_keys=tuple(
            reference.fact_key for reference in record.support
        ),
    )


def _to_diagnostic(
    record: SemanticInterpretationDiagnosticRecord,
) -> SemanticInterpretationDiagnostic:
    return SemanticInterpretationDiagnostic(
        reason=SemanticAmbiguityReason(record.reason),
        subject_entity_key=record.subject_entity_key,
        candidate_fact_keys=(
            tuple(record.candidate_fact_keys.split(_KEY_SEPARATOR))
            if record.candidate_fact_keys
            else ()
        ),
    )
