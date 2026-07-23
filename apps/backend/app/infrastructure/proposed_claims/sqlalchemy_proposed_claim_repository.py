from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    DuplicateEvidenceError,
    DuplicateProposedClaimError,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.models.proposed_claims import (
    EvidenceReferenceRecord,
    ProposedClaimRecord,
)


class SqlAlchemyProposedClaimRepository(ProposedClaimRepository):
    """
    SQLAlchemy adapter for the ``ProposedClaimRepository`` port, backed
    by ``app.models.proposed_claims.ProposedClaimRecord`` and
    ``EvidenceReferenceRecord``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, claim: ProposedClaim) -> ProposedClaim:
        record = ProposedClaimRecord(
            project_id=claim.project_id,
            claim_type=claim.claim_type,
            subject=claim.subject.value,
            predicate=(
                claim.predicate.value
                if claim.predicate is not None
                else None
            ),
            object=(
                claim.object.value if claim.object is not None else None
            ),
            created_at=claim.created_at,
            updated_at=claim.updated_at,
        )
        self._session.add(record)

        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()

            raise DuplicateProposedClaimError(
                claim.project_id,
                claim.claim_type,
                claim.subject.value,
            ) from error

        evidence_records = [
            self._to_evidence_record(record.id, reference)
            for reference in claim.evidence
        ]
        self._session.add_all(evidence_records)

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()

            raise DuplicateEvidenceError(
                claim.evidence[0].engineering_index_entry_id
            ) from error

        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, claim_id: int) -> ProposedClaim | None:
        record = self._session.get(ProposedClaimRecord, claim_id)

        return self._to_domain(record) if record is not None else None

    def find_duplicate(
        self,
        project_id: int,
        claim_type: ClaimType,
        subject: ClaimSubject,
        predicate: ClaimPredicate | None,
        object_: ClaimObject | None,
    ) -> ProposedClaim | None:
        record = (
            self._session.query(ProposedClaimRecord)
            .filter(
                ProposedClaimRecord.project_id == project_id,
                ProposedClaimRecord.claim_type == claim_type,
                ProposedClaimRecord.subject == subject.value,
                ProposedClaimRecord.predicate
                == (predicate.value if predicate is not None else None),
                ProposedClaimRecord.object
                == (object_.value if object_ is not None else None),
            )
            .first()
        )

        return self._to_domain(record) if record is not None else None

    def list_by_project(self, project_id: int) -> list[ProposedClaim]:
        records = (
            self._session.query(ProposedClaimRecord)
            .filter(ProposedClaimRecord.project_id == project_id)
            .order_by(ProposedClaimRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def list_by_document(self, document_id: int) -> list[ProposedClaim]:
        records = (
            self._session.query(ProposedClaimRecord)
            .join(
                EvidenceReferenceRecord,
                EvidenceReferenceRecord.proposed_claim_id
                == ProposedClaimRecord.id,
            )
            .filter(
                EvidenceReferenceRecord.document_id == document_id
            )
            .distinct()
            .order_by(ProposedClaimRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def replace_evidence(
        self,
        claim_id: int,
        evidence: list[EvidenceReference],
    ) -> ProposedClaim:
        self._session.query(EvidenceReferenceRecord).filter(
            EvidenceReferenceRecord.proposed_claim_id == claim_id
        ).delete(synchronize_session=False)

        evidence_records = [
            self._to_evidence_record(claim_id, reference)
            for reference in evidence
        ]
        self._session.add_all(evidence_records)

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()

            raise DuplicateEvidenceError(
                evidence[0].engineering_index_entry_id
            ) from error

        record = self._session.get(ProposedClaimRecord, claim_id)
        self._session.refresh(record)

        return self._to_domain(record)  # type: ignore[arg-type]

    def delete(self, claim_id: int) -> None:
        self._session.query(EvidenceReferenceRecord).filter(
            EvidenceReferenceRecord.proposed_claim_id == claim_id
        ).delete(synchronize_session=False)
        self._session.query(ProposedClaimRecord).filter(
            ProposedClaimRecord.id == claim_id
        ).delete(synchronize_session=False)

        self._session.commit()

    @staticmethod
    def _to_evidence_record(
        proposed_claim_id: int,
        reference: EvidenceReference,
    ) -> EvidenceReferenceRecord:
        return EvidenceReferenceRecord(
            proposed_claim_id=proposed_claim_id,
            engineering_index_entry_id=(
                reference.engineering_index_entry_id
            ),
            document_id=reference.document_id,
            locator_kind=reference.locator.kind,
            locator_value=reference.locator.value,
        )

    def _to_domain(self, record: ProposedClaimRecord) -> ProposedClaim:
        evidence_records = (
            self._session.query(EvidenceReferenceRecord)
            .filter(
                EvidenceReferenceRecord.proposed_claim_id == record.id
            )
            .order_by(EvidenceReferenceRecord.id.asc())
            .all()
        )

        return ProposedClaim(
            id=record.id,
            project_id=record.project_id,
            claim_type=record.claim_type,
            subject=ClaimSubject(value=record.subject),
            predicate=(
                ClaimPredicate(value=record.predicate)
                if record.predicate is not None
                else None
            ),
            object=(
                ClaimObject(value=record.object)
                if record.object is not None
                else None
            ),
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
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
