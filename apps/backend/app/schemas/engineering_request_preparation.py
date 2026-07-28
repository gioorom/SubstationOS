from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RetrievalBridgeFailureCode,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)
from app.schemas.engineering_engine import (
    ComparisonOperandCriteriaBody,
    EngineeringEngineExecuteRequestBody,
)
from app.schemas.engineering_intent import EngineeringIntentRead

# --- Request -----------------------------------------------------------


class EngineeringRequestPrepareRequestBody(BaseModel):
    """
    A raw engineering request, as an engineer would actually type it.

    **Carries no retrieval configuration at all** - deriving it is this
    endpoint's entire purpose, and accepting an override would reopen the
    gap this stage exists to close. There is likewise no field for a
    prompt, an instruction, a workflow name, or an intent type: the
    classifier decides the intent and the bridge derives the criteria.

    ``working_memory_*`` are the same optional, purely structural signals
    ``/engineering-intents/classify`` already accepts (ADR-0019).
    """

    engineering_session_id: str
    conversation_id: str
    turn_id: str
    request_text: str

    provider_id: str | None = None
    model_identifier: str | None = None
    request_correlation_id: str | None = None

    working_memory_has_open_question: bool = False
    working_memory_active_response_count: int = 0


# --- Response ------------------------------------------------------------


class RequestDesignationRead(BaseModel):
    text: str
    token_index: int
    resolution: DesignationResolution
    entity_type: str | None
    canonical_id: str | None
    canonical_reference: str | None

    model_config = ConfigDict(from_attributes=True)


class RetrievalConfigurationRead(BaseModel):
    mode: RetrievalMode
    limit: int
    include_neighborhood: bool
    neighborhood_depth: int
    lexical_terms: list[str]
    canonical_entity_id: str | None
    entity_type: str | None
    attribute_name: str | None

    model_config = ConfigDict(from_attributes=True)


class RetrievalBridgeFailureRead(BaseModel):
    code: RetrievalBridgeFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class RetrievalBridgeMetadataRead(BaseModel):
    retrieval_bridge_version: str
    bridge_policy_version: str
    project_id: int
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    derived_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetrievalBridgeStatisticsRead(BaseModel):
    designation_count: int
    canonical_reference_count: int
    lexical_term_count: int

    model_config = ConfigDict(from_attributes=True)


class RetrievalBridgeResultRead(BaseModel):
    """The bridge's own auditable outcome. ``designations`` is populated
    even when the bridge declines, so a refusal is as inspectable as a
    success."""

    resolved: bool
    metadata: RetrievalBridgeMetadataRead
    statistics: RetrievalBridgeStatisticsRead
    designations: list[RequestDesignationRead]
    configuration: RetrievalConfigurationRead | None
    failure: RetrievalBridgeFailureRead | None

    model_config = ConfigDict(from_attributes=True)


class ComparisonOperandRead(BaseModel):
    designation: RequestDesignationRead
    configuration: RetrievalConfigurationRead

    model_config = ConfigDict(from_attributes=True)


class ComparisonScopeRead(BaseModel):
    project_id: int
    both_operands_resolved_canonically: bool

    model_config = ConfigDict(from_attributes=True)


class ComparisonConfigurationRead(BaseModel):
    """The two prepared operands, in the order the request named them.
    Named fields rather than a list: "compare A with B" and "compare B
    with A" are different questions, so the ordering is structural."""

    left: ComparisonOperandRead
    right: ComparisonOperandRead
    scope: ComparisonScopeRead

    model_config = ConfigDict(from_attributes=True)


class ComparisonBridgeStatisticsRead(BaseModel):
    designation_count: int
    required_operand_count: int
    canonical_reference_count: int

    model_config = ConfigDict(from_attributes=True)


class ComparisonBridgeResultRead(BaseModel):
    """The comparison arm's own auditable outcome. ``designations`` is
    populated even when preparation declines, so a refusal for naming one
    subject or four is as inspectable as a success."""

    resolved: bool
    metadata: RetrievalBridgeMetadataRead
    statistics: ComparisonBridgeStatisticsRead
    designations: list[RequestDesignationRead]
    configuration: ComparisonConfigurationRead | None
    failure: RetrievalBridgeFailureRead | None

    model_config = ConfigDict(from_attributes=True)


class PreparedEngineeringRequestRead(BaseModel):
    """
    The prepared stage's output. ``execution_request`` is exactly the
    ``EngineeringEngineExecuteRequestBody`` shape
    ``/engineering-engine/execute`` accepts - the same "reuse the
    upstream response shape as the next stage's request shape" pattern
    every other stage in this pipeline follows, so a caller posts it on
    unchanged.

    On ``prepared=false`` it is ``null`` and ``bridge.failure`` says why.
    An under-specified request is answered honestly rather than executed
    against broadened criteria.
    """

    prepared: bool
    project_id: int
    intent: EngineeringIntentRead
    bridge: RetrievalBridgeResultRead | None = None
    comparison_bridge: ComparisonBridgeResultRead | None = None
    execution_request: EngineeringEngineExecuteRequestBody | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, prepared) -> "PreparedEngineeringRequestRead":
        request = prepared.execution_request

        return cls(
            prepared=prepared.prepared,
            project_id=prepared.project_id,
            intent=EngineeringIntentRead.from_domain(prepared.intent),
            bridge=(
                None
                if prepared.bridge is None
                else RetrievalBridgeResultRead.model_validate(prepared.bridge)
            ),
            comparison_bridge=(
                None
                if prepared.comparison_bridge is None
                else ComparisonBridgeResultRead.model_validate(
                    prepared.comparison_bridge
                )
            ),
            execution_request=(
                None
                if request is None
                else EngineeringEngineExecuteRequestBody(
                    engineering_session_id=request.engineering_session_id,
                    conversation_id=request.conversation_id,
                    turn_id=request.turn_id,
                    request_text=request.request_text,
                    engineering_intent_id=request.engineering_intent_id,
                    intent_type=request.intent_type,
                    retrieval_limit=request.retrieval_limit,
                    retrieval_include_neighborhood=(
                        request.retrieval_include_neighborhood
                    ),
                    retrieval_neighborhood_depth=(
                        request.retrieval_neighborhood_depth
                    ),
                    retrieval_entity_type=request.retrieval_entity_type,
                    retrieval_canonical_entity_id=(
                        request.retrieval_canonical_entity_id
                    ),
                    retrieval_attribute_name=(
                        request.retrieval_attribute_name
                    ),
                    retrieval_lexical_terms=list(
                        request.retrieval_lexical_terms
                    ),
                    provider_id=request.provider_id,
                    model_identifier=request.model_identifier,
                    request_correlation_id=request.request_correlation_id,
                    working_memory_has_open_question=(
                        request.working_memory_has_open_question
                    ),
                    working_memory_active_response_count=(
                        request.working_memory_active_response_count
                    ),
                    comparison_left=(
                        None
                        if request.comparison_left is None
                        else ComparisonOperandCriteriaBody.model_validate(
                            request.comparison_left
                        )
                    ),
                    comparison_right=(
                        None
                        if request.comparison_right is None
                        else ComparisonOperandCriteriaBody.model_validate(
                            request.comparison_right
                        )
                    ),
                )
            ),
        )


__all__ = [
    "EngineeringRequestPrepareRequestBody",
    "PreparedEngineeringRequestRead",
    "RetrievalBridgeResultRead",
    "RetrievalConfigurationRead",
]
