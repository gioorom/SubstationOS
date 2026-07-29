from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_entities.entity_failures import (
    EntityResolutionFailureCode,
)
from app.domain.engineering_entities.entity_models import (
    EntityStatus,
    EntityType,
)
from app.domain.engineering_evidence.evidence_models import EvidenceType

# --- Response ------------------------------------------------------------


class EvidenceReferenceRead(BaseModel):
    """
    One contributing observation.

    ``evidence_key`` points at the authoritative evidence record, which
    carries the full character-level provenance. The location is here so
    an entity can be read without a second lookup.
    """

    evidence_key: str
    evidence_type: EvidenceType
    observed_text: str
    page_number: int
    paragraph_index: int
    line_index: int
    token_start: int
    token_end: int

    model_config = ConfigDict(from_attributes=True)


class EngineeringQuantityRead(BaseModel):
    """``Decimal`` on the wire, serialised as a JSON string rather than a
    float."""

    value: Decimal
    unit: str
    base_value: Decimal | None
    base_unit: str | None

    model_config = ConfigDict(from_attributes=True)


class DesignationValueRead(BaseModel):
    normalized: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringEntityRead(BaseModel):
    """
    One deterministic grouping of observations.

    It says these observations refer to one object. It does **not** say
    what that object is, what it does, what it belongs to, or what its
    properties are - and there is no field here in which any of that
    could be written.
    """

    entity_key: str
    entity_type: EntityType
    status: EntityStatus
    entity_version: str
    resolution_rule_id: str
    resolution_rule_version: str
    label: str
    evidence_count: int
    designation: DesignationValueRead | None
    quantity: EngineeringQuantityRead | None
    evidence: tuple[EvidenceReferenceRead, ...]

    model_config = ConfigDict(from_attributes=True)


class EntitySetSummaryRead(BaseModel):
    """What an entity set *is*, without its entities."""

    document_id: int
    project_id: int | None
    content_checksum: str
    extraction_policy_version: str
    resolution_policy_version: str
    entity_count: int

    model_config = ConfigDict(from_attributes=True)


class EntitySetRead(EntitySetSummaryRead):
    """The full set, every entity with its contributing evidence."""

    entities: tuple[EngineeringEntityRead, ...]

    model_config = ConfigDict(from_attributes=True)


class EntityResolutionFailureRead(BaseModel):
    code: EntityResolutionFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class EntityResolutionResultRead(BaseModel):
    """
    The four outcomes a caller must be able to tell apart.

    | `succeeded` | `reused` | `found_entities` | Means |
    |---|---|---|---|
    | true | false | true | resolution completed |
    | true | false | false | completed, and nothing resolved |
    | true | true | either | an existing set was reused |
    | false | - | - | resolution failed; `failure` says why |
    """

    succeeded: bool
    reused: bool
    found_entities: bool
    entity_set: EntitySetSummaryRead | None
    failure: EntityResolutionFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "EntityResolutionResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            found_entities=result.found_entities,
            entity_set=(
                None
                if result.entity_set is None
                else EntitySetSummaryRead.model_validate(result.entity_set)
            ),
            failure=(
                None
                if result.failure is None
                else EntityResolutionFailureRead.model_validate(
                    result.failure
                )
            ),
        )
