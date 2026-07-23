from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_validator import (
    ProposedClaimValidator,
)


class EvidenceReferenceFactory:
    """
    Builds an ``EvidenceReference`` by snapshotting the
    document/locator of a live Engineering Index ``IndexEntry`` - the
    only place this bounded context reads Engineering Index shape, kept
    to exactly the two fields a claim needs to cite its evidence without
    a join.
    """

    @staticmethod
    def from_index_entry(entry: IndexEntry) -> EvidenceReference:
        return EvidenceReference(
            engineering_index_entry_id=entry.id,  # type: ignore[arg-type]
            document_id=entry.document_id,
            locator=entry.locator,
        )


class ProposedClaimFactory:
    """
    Builds and evolves ``ProposedClaim`` instances, enforcing invariants
    at construction time (CLAUDE.md SS4.2). Because ``ProposedClaim`` is
    frozen, replacing its evidence does not mutate it -
    ``with_evidence`` returns a new instance.
    """

    @staticmethod
    def create(
        *,
        project_id: int,
        claim_type: ClaimType,
        subject: ClaimSubject,
        predicate: ClaimPredicate | None,
        object_: ClaimObject | None,
        evidence: tuple[EvidenceReference, ...],
        now: datetime,
    ) -> ProposedClaim:
        ProposedClaimValidator.validate_subject(subject)
        ProposedClaimValidator.validate_predicate(predicate)
        ProposedClaimValidator.validate_object(object_)
        ProposedClaimValidator.validate_shape(
            claim_type,
            predicate,
            object_,
        )
        ProposedClaimValidator.validate_evidence_not_empty(evidence)
        ProposedClaimValidator.validate_no_duplicate_evidence(evidence)

        return ProposedClaim(
            id=None,
            project_id=project_id,
            claim_type=claim_type,
            subject=subject,
            predicate=predicate,
            object=object_,
            evidence=evidence,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def with_evidence(
        claim: ProposedClaim,
        evidence: tuple[EvidenceReference, ...],
        now: datetime,
    ) -> ProposedClaim:
        ProposedClaimValidator.validate_evidence_not_empty(evidence)
        ProposedClaimValidator.validate_no_duplicate_evidence(evidence)

        return replace(
            claim,
            evidence=evidence,
            updated_at=now,
        )
