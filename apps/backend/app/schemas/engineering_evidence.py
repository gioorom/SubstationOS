from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_evidence.evidence_failures import (
    EvidenceFailureCode,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)

# --- Response ------------------------------------------------------------


class SpanReferenceRead(BaseModel):
    """One canonical span, and the characters of it this observation
    used."""

    span_reading_order: int
    character_start: int
    character_end: int

    model_config = ConfigDict(from_attributes=True)


class EvidenceProvenanceRead(BaseModel):
    """
    Everything needed to re-read an observation without searching for it:
    which page, paragraph and line, which tokens, and which characters of
    which spans.
    """

    page_number: int
    section_index: int
    paragraph_index: int
    block_reading_order: int
    line_index: int
    token_start: int
    token_end: int
    spans: tuple[SpanReferenceRead, ...]
    source_text: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringQuantityRead(BaseModel):
    """
    ``Decimal`` on the wire, serialised as a JSON string rather than a
    float - a rated voltage must not acquire a rounding error on its way
    to a client.

    ``base_value``/``base_unit`` appear only where the unit catalogue
    declares an exact conversion.
    """

    value: Decimal
    unit: str
    base_value: Decimal | None
    base_unit: str | None

    model_config = ConfigDict(from_attributes=True)


class DesignationValueRead(BaseModel):
    normalized: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringEvidenceRead(BaseModel):
    """
    One observation.

    It says a pattern was seen at a place, under a named rule at a named
    version. It does **not** say what entity it belongs to, and there is
    no field here in which it could.
    """

    evidence_key: str
    evidence_type: EvidenceType
    status: EvidenceStatus
    observed_text: str
    rule_id: str
    rule_version: str
    quantity: EngineeringQuantityRead | None
    designation: DesignationValueRead | None
    provenance: EvidenceProvenanceRead

    model_config = ConfigDict(from_attributes=True)


class EvidenceSetSummaryRead(BaseModel):
    """What an evidence set *is*, without its contents - which canonical
    source, and under which rule catalogue."""

    document_id: int
    project_id: int | None
    content_checksum: str
    segmentation_version: str
    extraction_policy_version: str
    evidence_count: int

    model_config = ConfigDict(from_attributes=True)


class EvidenceSetRead(EvidenceSetSummaryRead):
    """The full set, every observation with its provenance."""

    evidence: tuple[EngineeringEvidenceRead, ...]

    model_config = ConfigDict(from_attributes=True)


class EvidenceFailureRead(BaseModel):
    code: EvidenceFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class EvidenceExtractionResultRead(BaseModel):
    """
    The four outcomes a caller must be able to tell apart.

    | `succeeded` | `reused` | `found_evidence` | Means |
    |---|---|---|---|
    | true | false | true | extraction completed |
    | true | false | false | completed, and nothing supported was found |
    | true | true | either | an existing set was reused |
    | false | - | - | extraction failed; `failure` says why |

    ``rejected_count`` reports candidates the rules decided against.
    They are diagnostics and are never stored.
    """

    succeeded: bool
    reused: bool
    found_evidence: bool
    rejected_count: int
    evidence_set: EvidenceSetSummaryRead | None
    failure: EvidenceFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "EvidenceExtractionResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            found_evidence=result.found_evidence,
            rejected_count=result.rejected_count,
            evidence_set=(
                None
                if result.evidence_set is None
                else EvidenceSetSummaryRead.model_validate(
                    result.evidence_set
                )
            ),
            failure=(
                None
                if result.failure is None
                else EvidenceFailureRead.model_validate(result.failure)
            ),
        )
