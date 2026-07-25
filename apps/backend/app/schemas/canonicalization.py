from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.proposed_claims.claim_type import ClaimType
from app.schemas.proposed_claims import EvidenceReferenceRead


class CanonicalizeReviewCandidateRequest(BaseModel):
    review_candidate_id: int


class CanonicalEntityReferenceRead(BaseModel):
    entity_type: str
    canonical_id: str
    value: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class CanonicalFactRead(BaseModel):
    id: int
    project_id: int
    claim_type: ClaimType
    subject: CanonicalEntityReferenceRead
    predicate_value: str | None
    object_entity: CanonicalEntityReferenceRead | None
    object_value: str | None
    proposed_claim_id: int
    review_candidate_id: int
    evidence: list[EvidenceReferenceRead]
    reviewed_by: str
    reviewed_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class CanonicalizationResultRead(BaseModel):
    fact: CanonicalFactRead
    created: bool

    model_config = ConfigDict(
        from_attributes=True,
    )
