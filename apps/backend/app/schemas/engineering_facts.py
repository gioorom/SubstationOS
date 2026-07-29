from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_facts.fact_failures import (
    FactConstructionFailureCode,
)
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    FactStatus,
    SupportRole,
)
from app.domain.engineering_facts.fact_predicates import FactPredicate

# --- Response ------------------------------------------------------------


class FactSupportRead(BaseModel):
    """
    One observation supporting a fact.

    ``evidence_key`` points at the authoritative evidence record, which
    carries the full character-level provenance. The location is here so
    a same-line association can be re-checked without a second lookup.
    """

    evidence_key: str
    role: SupportRole
    evidence_type: EvidenceType
    observed_text: str
    page_number: int
    paragraph_index: int
    line_index: int
    token_start: int
    token_end: int

    model_config = ConfigDict(from_attributes=True)


class EngineeringFactRead(BaseModel):
    """
    One deterministic association.

    `HAS_ASSOCIATED_QUANTITY` says the subject and object appeared
    together under a declared rule. It does **not** say the quantity is
    the subject's rated power, voltage or current - no rule here proves a
    role, and the evidence type is exposed on the support rather than
    promoted into the predicate.
    """

    fact_key: str
    subject_entity_key: str
    predicate: FactPredicate
    object_entity_key: str
    status: FactStatus
    fact_version: str
    construction_rule_id: str
    construction_rule_version: str
    support: tuple[FactSupportRead, ...]

    model_config = ConfigDict(from_attributes=True)


class FactDiagnosticRead(BaseModel):
    """
    A line that held candidates and produced no fact.

    Deliberately not shaped like a fact: it names no subject and no
    object, because which is which is exactly what could not be
    determined.
    """

    reason: AmbiguityReason
    page_number: int
    paragraph_index: int
    line_index: int
    subject_entity_keys: tuple[str, ...]
    object_entity_keys: tuple[str, ...]

    model_config = ConfigDict(from_attributes=True)


class FactSetSummaryRead(BaseModel):
    """What a fact set *is*, without its facts."""

    document_id: int
    project_id: int | None
    content_checksum: str
    resolution_policy_version: str
    fact_policy_version: str
    fact_count: int
    has_ambiguities: bool

    model_config = ConfigDict(from_attributes=True)


class FactSetRead(FactSetSummaryRead):
    """The full set: every fact with its support, and every diagnostic."""

    facts: tuple[EngineeringFactRead, ...]
    diagnostics: tuple[FactDiagnosticRead, ...]

    model_config = ConfigDict(from_attributes=True)


class FactConstructionFailureRead(BaseModel):
    code: FactConstructionFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class FactConstructionResultRead(BaseModel):
    """
    The five outcomes a caller must be able to tell apart.

    | `succeeded` | `reused` | `found_facts` | `has_ambiguities` | Means |
    |---|---|---|---|---|
    | true | false | true | false | facts constructed |
    | true | false | true | true | constructed, with ambiguities declined |
    | true | false | false | either | no supported facts found |
    | true | true | either | either | an existing set was reused |
    | false | - | - | - | construction failed; `failure` says why |
    """

    succeeded: bool
    reused: bool
    found_facts: bool
    has_ambiguities: bool
    fact_set: FactSetSummaryRead | None
    failure: FactConstructionFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "FactConstructionResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            found_facts=result.found_facts,
            has_ambiguities=result.has_ambiguities,
            fact_set=(
                None
                if result.fact_set is None
                else FactSetSummaryRead.model_validate(result.fact_set)
            ),
            failure=(
                None
                if result.failure is None
                else FactConstructionFailureRead.model_validate(
                    result.failure
                )
            ),
        )
