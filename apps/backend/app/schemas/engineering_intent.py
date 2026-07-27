from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentConfidence,
    EngineeringIntentEvidenceType,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
)

# --- Request -----------------------------------------------------------


class EngineeringIntentClassifyRequestBody(BaseModel):
    """
    A classification request. ``project_id`` is deliberately absent -
    the path's own ``{project_id}`` is authoritative.

    **Never accepts a caller-supplied classification result** - no
    intent type, confidence, evidence, or secondary match field exists
    on this body; the classifier alone decides those.

    ``working_memory_has_open_question``/
    ``working_memory_active_response_count`` are optional, purely
    structural Working Memory signals a caller may pass through from a
    prior ``/working-memory/build`` call - never a route into hidden
    semantic inference (see ADR-0019).
    """

    engineering_session_id: str
    conversation_id: str
    turn_id: str
    request_text: str
    working_memory_has_open_question: bool = False
    working_memory_active_response_count: int = 0


# --- Response ------------------------------------------------------------


class EngineeringIntentEvidenceRead(BaseModel):
    evidence_type: EngineeringIntentEvidenceType
    matched_rule_id: str
    matched_text: str
    token_index: int
    candidate_intent_type: EngineeringIntentType
    strength: EngineeringIntentRuleStrength
    description_code: str
    sequence: int

    model_config = ConfigDict(from_attributes=True)


class EngineeringIntentMetadataRead(BaseModel):
    engineering_intent_version: str
    classification_policy_version: str
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    original_request_text: str
    normalized_request_text: str
    classified_at: datetime
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringIntentStatisticsRead(BaseModel):
    evaluated_rule_count: int
    matched_rule_count: int
    strong_match_count: int
    weak_match_count: int
    unique_candidate_intent_count: int
    secondary_intent_count: int

    model_config = ConfigDict(from_attributes=True)


class EngineeringIntentVersionRead(BaseModel):
    engineering_intent_version: str
    classification_policy_version: str
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringIntentRead(BaseModel):
    """
    Deliberately exposes only deterministic, provider-independent
    classification fields - no provider-specific field, no model name,
    no probability score, and no hidden reasoning of any kind.
    """

    engineering_intent_id: str
    project_id: int
    intent_type: EngineeringIntentType
    confidence: EngineeringIntentConfidence
    evidence: list[EngineeringIntentEvidenceRead]
    secondary_intent_types: list[EngineeringIntentType]
    metadata: EngineeringIntentMetadataRead
    statistics: EngineeringIntentStatisticsRead
    version: EngineeringIntentVersionRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, intent) -> "EngineeringIntentRead":
        return cls(
            engineering_intent_id=intent.engineering_intent_id.value,
            project_id=intent.project_id,
            intent_type=intent.intent_type,
            confidence=intent.confidence,
            evidence=[
                EngineeringIntentEvidenceRead.model_validate(item)
                for item in intent.evidence
            ],
            secondary_intent_types=list(intent.secondary_intent_types),
            metadata=EngineeringIntentMetadataRead.model_validate(intent.metadata),
            statistics=EngineeringIntentStatisticsRead.model_validate(
                intent.statistics
            ),
            version=EngineeringIntentVersionRead.model_validate(intent.version),
        )


class EngineeringIntentValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class EngineeringIntentClassificationResultRead(BaseModel):
    project_id: int
    intent: EngineeringIntentRead
    validation: EngineeringIntentValidationResultRead

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "EngineeringIntentClassificationResultRead":
        return cls(
            project_id=result.project_id,
            intent=EngineeringIntentRead.from_domain(result.intent),
            validation=EngineeringIntentValidationResultRead.model_validate(
                result.validation
            ),
        )


__all__ = [
    "EngineeringIntentClassifyRequestBody",
    "EngineeringIntentClassificationResultRead",
]
