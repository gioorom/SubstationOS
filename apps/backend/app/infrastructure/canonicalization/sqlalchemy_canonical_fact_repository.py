from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.canonicalization.canonicalization_models import (
    CanonicalAttribute,
    CanonicalEntityReference,
    CanonicalFact,
    CanonicalPredicate,
    CanonicalProvenance,
    CanonicalValue,
)
from app.domain.canonicalization.canonicalization_repository import (
    CanonicalFactRepository,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    EvidenceReference,
)
from app.models.canonicalization import (
    CanonicalFactEvidenceRecord,
    CanonicalFactRecord,
)


class SqlAlchemyCanonicalFactRepository(CanonicalFactRepository):
    """
    SQLAlchemy adapter for the ``CanonicalFactRepository`` port, backed
    by ``app.models.canonicalization.CanonicalFactRecord`` and
    ``CanonicalFactEvidenceRecord``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, fact: CanonicalFact) -> CanonicalFact:
        object_entity_type: str | None = None
        object_canonical_id: str | None = None
        object_value: str | None = None

        if isinstance(fact.object, CanonicalEntityReference):
            object_entity_type = fact.object.entity_type
            object_canonical_id = fact.object.canonical_id
        elif isinstance(fact.object, CanonicalValue):
            object_value = fact.object.value

        record = CanonicalFactRecord(
            project_id=fact.project_id,
            claim_type=fact.claim_type,
            subject_entity_type=fact.subject.entity_type,
            subject_canonical_id=fact.subject.canonical_id,
            predicate_value=(
                fact.predicate.value
                if fact.predicate is not None
                else None
            ),
            object_entity_type=object_entity_type,
            object_canonical_id=object_canonical_id,
            object_value=object_value,
            proposed_claim_id=fact.proposed_claim_id,
            review_candidate_id=fact.review_candidate_id,
            reviewed_by=fact.provenance.reviewed_by,
            reviewed_at=fact.provenance.reviewed_at,
            created_at=fact.created_at,
        )
        self._session.add(record)
        self._session.flush()

        evidence_records = [
            self._to_evidence_record(record.id, reference)
            for reference in fact.evidence
        ]
        self._session.add_all(evidence_records)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, fact_id: int) -> CanonicalFact | None:
        record = self._session.get(CanonicalFactRecord, fact_id)

        return self._to_domain(record) if record is not None else None

    def get_by_review_candidate(
        self,
        review_candidate_id: int,
    ) -> CanonicalFact | None:
        record = (
            self._session.query(CanonicalFactRecord)
            .filter(
                CanonicalFactRecord.review_candidate_id
                == review_candidate_id
            )
            .first()
        )

        return self._to_domain(record) if record is not None else None

    def list_by_project(self, project_id: int) -> list[CanonicalFact]:
        records = (
            self._session.query(CanonicalFactRecord)
            .filter(CanonicalFactRecord.project_id == project_id)
            .order_by(CanonicalFactRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def list_by_document(self, document_id: int) -> list[CanonicalFact]:
        records = (
            self._session.query(CanonicalFactRecord)
            .join(
                CanonicalFactEvidenceRecord,
                CanonicalFactEvidenceRecord.canonical_fact_id
                == CanonicalFactRecord.id,
            )
            .filter(
                CanonicalFactEvidenceRecord.document_id == document_id
            )
            .distinct()
            .order_by(CanonicalFactRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_evidence_record(
        canonical_fact_id: int,
        reference: EvidenceReference,
    ) -> CanonicalFactEvidenceRecord:
        return CanonicalFactEvidenceRecord(
            canonical_fact_id=canonical_fact_id,
            engineering_index_entry_id=(
                reference.engineering_index_entry_id
            ),
            document_id=reference.document_id,
            locator_kind=reference.locator.kind,
            locator_value=reference.locator.value,
        )

    def _to_domain(self, record: CanonicalFactRecord) -> CanonicalFact:
        evidence_records = (
            self._session.query(CanonicalFactEvidenceRecord)
            .filter(
                CanonicalFactEvidenceRecord.canonical_fact_id
                == record.id
            )
            .order_by(CanonicalFactEvidenceRecord.id.asc())
            .all()
        )

        predicate: CanonicalPredicate | CanonicalAttribute | None
        object_: CanonicalEntityReference | CanonicalValue | None

        if record.claim_type is ClaimType.RELATIONSHIP:
            predicate = (
                CanonicalPredicate(value=record.predicate_value)
                if record.predicate_value is not None
                else None
            )
            object_ = (
                CanonicalEntityReference(
                    entity_type=record.object_entity_type,
                    canonical_id=record.object_canonical_id,
                )
                if record.object_entity_type is not None
                and record.object_canonical_id is not None
                else None
            )
        elif record.claim_type is ClaimType.ATTRIBUTE:
            predicate = (
                CanonicalAttribute(value=record.predicate_value)
                if record.predicate_value is not None
                else None
            )
            object_ = (
                CanonicalValue(value=record.object_value)
                if record.object_value is not None
                else None
            )
        else:
            predicate = None
            object_ = None

        return CanonicalFact(
            id=record.id,
            project_id=record.project_id,
            claim_type=record.claim_type,
            subject=CanonicalEntityReference(
                entity_type=record.subject_entity_type,
                canonical_id=record.subject_canonical_id,
            ),
            predicate=predicate,
            object=object_,
            proposed_claim_id=record.proposed_claim_id,
            review_candidate_id=record.review_candidate_id,
            evidence=tuple(
                EvidenceReference(
                    engineering_index_entry_id=(
                        evidence_record.engineering_index_entry_id
                    ),
                    document_id=evidence_record.document_id,
                    locator=IndexEntryLocator(
                        kind=evidence_record.locator_kind,
                        value=evidence_record.locator_value,
                    ),
                )
                for evidence_record in evidence_records
            ),
            provenance=CanonicalProvenance(
                reviewed_by=record.reviewed_by,
                reviewed_at=record.reviewed_at,
            ),
            created_at=record.created_at,
        )
