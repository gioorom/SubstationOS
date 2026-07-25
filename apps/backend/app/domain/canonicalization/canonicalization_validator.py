from __future__ import annotations

from app.domain.canonicalization.canonicalization_exceptions import (
    CrossProjectCanonicalizationError,
    ReviewCandidateNotApprovedError,
    UnsupportedClaimTypeError,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.review_workflow.review_status import ReviewStatus


class CanonicalizationValidator:
    """
    Stateless precondition checks for Canonicalization, shared by the
    factory (at construction) and the service (which needs to validate
    before performing repository lookups).
    """

    @staticmethod
    def validate_approved(
        review_candidate_id: int,
        status: ReviewStatus,
    ) -> None:
        if status is not ReviewStatus.APPROVED:
            raise ReviewCandidateNotApprovedError(
                review_candidate_id,
                status,
            )

    @staticmethod
    def validate_same_project(
        claim_project_id: int,
        candidate_project_id: int,
    ) -> None:
        if claim_project_id != candidate_project_id:
            raise CrossProjectCanonicalizationError(
                claim_project_id,
                candidate_project_id,
            )

    @staticmethod
    def validate_claim_type_supported(claim_type: ClaimType) -> None:
        if claim_type not in ClaimType:
            raise UnsupportedClaimTypeError(claim_type)
