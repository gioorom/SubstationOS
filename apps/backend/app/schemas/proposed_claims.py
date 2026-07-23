from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
)


def _claim_value_text(value: object) -> object:
    """
    ``ProposedClaim.subject``/``predicate``/``object`` are domain value
    objects (``ClaimSubject``/``ClaimPredicate``/``ClaimObject``), not
    bare strings - unwrap ``.value`` before Pydantic validates the
    field.
    """

    if isinstance(value, (ClaimSubject, ClaimPredicate, ClaimObject)):
        return value.value

    return value


class ProposedClaimCreate(BaseModel):
    claim_type: ClaimType

    subject: str = Field(min_length=1, max_length=255)

    predicate: str | None = Field(default=None, max_length=255)

    object: str | None = Field(default=None, max_length=255)

    engineering_index_entry_ids: list[int] = Field(min_length=1)

    allow_cross_document_evidence: bool = False


class EvidenceReplace(BaseModel):
    engineering_index_entry_ids: list[int] = Field(min_length=1)

    allow_cross_document_evidence: bool = False


class EvidenceReferenceRead(BaseModel):
    engineering_index_entry_id: int
    document_id: int
    locator_kind: IndexEntryLocatorKind
    locator_value: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProposedClaimRead(BaseModel):
    id: int
    project_id: int
    claim_type: ClaimType
    subject: str
    predicate: str | None
    object: str | None
    evidence: list[EvidenceReferenceRead]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_subject = field_validator("subject", mode="before")(
        _claim_value_text
    )
    _unwrap_predicate = field_validator("predicate", mode="before")(
        _claim_value_text
    )
    _unwrap_object = field_validator("object", mode="before")(
        _claim_value_text
    )
