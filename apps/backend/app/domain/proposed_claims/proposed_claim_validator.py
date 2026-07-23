from __future__ import annotations

from app.domain.proposed_claims.claim_type import (
    ClaimType,
    requires_predicate_and_object,
)
from app.domain.proposed_claims.proposed_claim_exceptions import (
    ClaimObjectRequiredError,
    ClaimPredicateRequiredError,
    CrossDocumentEvidenceNotAllowedError,
    CrossProjectEvidenceError,
    DuplicateEvidenceError,
    EmptyEvidenceError,
    InvalidClaimObjectError,
    InvalidClaimPredicateError,
    InvalidClaimSubjectError,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
)


class ProposedClaimValidator:
    """
    Stateless validation rules for Proposed Claims, shared by the
    factory (at construction) and the service (which needs to validate
    evidence against live Engineering Index/Document lookups before any
    ``ProposedClaim`` is built).
    """

    @staticmethod
    def validate_subject(subject: ClaimSubject) -> None:
        if not subject.value or not subject.value.strip():
            raise InvalidClaimSubjectError(subject.value)

    @staticmethod
    def validate_predicate(predicate: ClaimPredicate | None) -> None:
        if predicate is not None and not predicate.value.strip():
            raise InvalidClaimPredicateError(predicate.value)

    @staticmethod
    def validate_object(object_: ClaimObject | None) -> None:
        if object_ is not None and not object_.value.strip():
            raise InvalidClaimObjectError(object_.value)

    @staticmethod
    def validate_shape(
        claim_type: ClaimType,
        predicate: ClaimPredicate | None,
        object_: ClaimObject | None,
    ) -> None:
        if not requires_predicate_and_object(claim_type):
            return

        if predicate is None:
            raise ClaimPredicateRequiredError(claim_type)

        if object_ is None:
            raise ClaimObjectRequiredError(claim_type)

    @staticmethod
    def validate_evidence_not_empty(
        evidence: tuple[EvidenceReference, ...],
    ) -> None:
        if not evidence:
            raise EmptyEvidenceError()

    @staticmethod
    def validate_no_duplicate_evidence(
        evidence: tuple[EvidenceReference, ...],
    ) -> None:
        seen: set[int] = set()

        for reference in evidence:
            if reference.engineering_index_entry_id in seen:
                raise DuplicateEvidenceError(
                    reference.engineering_index_entry_id
                )

            seen.add(reference.engineering_index_entry_id)

    @staticmethod
    def validate_evidence_same_project(
        evidence_project_ids: list[int],
    ) -> None:
        distinct = frozenset(evidence_project_ids)

        if len(distinct) > 1:
            raise CrossProjectEvidenceError(distinct)

    @staticmethod
    def validate_evidence_documents(
        document_ids: list[int],
        *,
        allow_cross_document_evidence: bool,
    ) -> None:
        distinct = frozenset(document_ids)

        if len(distinct) > 1 and not allow_cross_document_evidence:
            raise CrossDocumentEvidenceNotAllowedError(distinct)
