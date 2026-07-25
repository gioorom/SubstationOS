from __future__ import annotations

from datetime import datetime

from app.domain.canonicalization.canonicalization_models import (
    CanonicalAttribute,
    CanonicalEntityReference,
    CanonicalFact,
    CanonicalPredicate,
    CanonicalProvenance,
    CanonicalValue,
)
from app.domain.canonicalization.canonicalization_normalizer import (
    normalize_attribute_name,
    normalize_entity_reference,
    normalize_predicate,
    normalize_value,
)
from app.domain.canonicalization.canonicalization_validator import (
    CanonicalizationValidator,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import ProposedClaim
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
)


class CanonicalizationFactory:
    """
    Builds ``CanonicalFact`` instances from an approved
    ``ReviewCandidate`` and the ``ProposedClaim`` it reviews, enforcing
    invariants at construction time (CLAUDE.md SS4.2). Performs
    normalization only - it never reviews, never extracts, and never
    touches the Engineering Index or the Project Knowledge Graph.
    """

    @staticmethod
    def canonicalize_claim(
        *,
        claim: ProposedClaim,
        candidate: ReviewCandidate,
        now: datetime,
    ) -> CanonicalFact:
        CanonicalizationValidator.validate_approved(
            candidate.id,  # type: ignore[arg-type]
            candidate.status,
        )
        CanonicalizationValidator.validate_same_project(
            claim.project_id,
            candidate.project_id,
        )
        CanonicalizationValidator.validate_claim_type_supported(
            claim.claim_type
        )

        subject = normalize_entity_reference(claim.subject.value)

        predicate: CanonicalPredicate | CanonicalAttribute | None
        object_: CanonicalEntityReference | CanonicalValue | None

        if claim.claim_type is ClaimType.RELATIONSHIP:
            predicate = normalize_predicate(
                claim.predicate.value  # type: ignore[union-attr]
            )
            object_ = normalize_entity_reference(
                claim.object.value  # type: ignore[union-attr]
            )
        elif claim.claim_type is ClaimType.ATTRIBUTE:
            predicate = normalize_attribute_name(
                claim.predicate.value  # type: ignore[union-attr]
            )
            object_ = normalize_value(
                claim.object.value  # type: ignore[union-attr]
            )
        else:
            predicate = None
            object_ = None

        provenance = CanonicalProvenance(
            reviewed_by=candidate.reviewed_by,  # type: ignore[arg-type]
            reviewed_at=candidate.reviewed_at,  # type: ignore[arg-type]
        )

        return CanonicalFact(
            id=None,
            project_id=claim.project_id,
            claim_type=claim.claim_type,
            subject=subject,
            predicate=predicate,
            object=object_,
            proposed_claim_id=claim.id,  # type: ignore[arg-type]
            review_candidate_id=candidate.id,  # type: ignore[arg-type]
            evidence=claim.evidence,
            provenance=provenance,
            created_at=now,
        )
