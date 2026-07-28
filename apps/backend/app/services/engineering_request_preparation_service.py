"""
Application service for Engineering Request Preparation (EPIC 5,
Milestone 23B.3) - the one seam that turns a **raw engineering request**
into an **explicit engine execution request**, closing the gap this
milestone exists to close:

    raw request text
        -> Engineering Request Classification   (Milestone 22)
        -> Classification-to-Retrieval Bridge   (Milestone 23B.3)
        -> EngineeringEngineExecutionRequest    (the engine's own input)

It orchestrates two existing pure domain capabilities and assembles their
outputs. It contains **no classification logic, no mapping logic and no
retrieval logic of its own** - the classifier decides the intent, the
bridge derives the criteria, and this module only carries values across.

Deliberately it does **not** execute anything: it returns a prepared
request, and the Engineering Engine is invoked separately with that
request. The engine therefore keeps receiving an explicit, fully-formed
execution request and never parses natural language - preparation is a
stage *before* the engine, not a behaviour inside it.

Performs no persistence and no I/O of any kind. ``now`` is supplied by the
caller so the whole preparation stays reproducible (CLAUDE.md §16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.engineering_engine.engineering_engine_models import (
    ComparisonOperandCriteria,
    EngineeringEngineExecutionRequest,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.comparison_bridge import (
    derive_comparison_configuration,
)
from app.domain.retrieval_bridge.comparison_models import (
    ComparisonBridgeResult,
    ComparisonOperand,
)
from app.domain.retrieval_bridge.retrieval_bridge import (
    derive_retrieval_configuration,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    RetrievalBridgeResult,
)
from app.services import engineering_intent_service


def _operand_criteria(operand: ComparisonOperand) -> ComparisonOperandCriteria:
    """Maps one prepared operand onto the engine's own restatement. The
    bridge and the engine never import each other; this is the single
    place the two vocabularies meet, exactly as the single-operand path
    already works."""

    configuration = operand.configuration

    return ComparisonOperandCriteria(
        designation=operand.text,
        retrieval_limit=configuration.limit,
        retrieval_include_neighborhood=configuration.include_neighborhood,
        retrieval_neighborhood_depth=configuration.neighborhood_depth,
        retrieval_entity_type=configuration.entity_type,
        retrieval_canonical_entity_id=configuration.canonical_entity_id,
        retrieval_attribute_name=configuration.attribute_name,
        retrieval_lexical_terms=configuration.lexical_terms,
    )


@dataclass(frozen=True, slots=True)
class PreparedEngineeringRequest:
    """
    The full, auditable outcome of one preparation.

    On ``prepared=True`` an ``execution_request`` is present and the
    bridge resolved; otherwise ``execution_request`` is ``None`` and
    ``bridge.failure`` says why - never both, never neither. The
    ``intent`` and ``bridge`` results are always carried, so a refusal is
    as inspectable as a success: an engineer can see what was classified,
    which designations were found, and which rule declined.
    """

    prepared: bool
    project_id: int
    intent: EngineeringIntent
    bridge: RetrievalBridgeResult | None = None
    comparison_bridge: ComparisonBridgeResult | None = None
    execution_request: EngineeringEngineExecutionRequest | None = None


def prepare_engineering_request(
    *,
    project_id: int,
    engineering_session_id: str,
    conversation_id: str,
    turn_id: str,
    request_text: str,
    now: datetime,
    provider_id: str | None = None,
    model_identifier: str | None = None,
    request_correlation_id: str | None = None,
    working_memory_has_open_question: bool = False,
    working_memory_active_response_count: int = 0,
) -> PreparedEngineeringRequest:
    """
    Classifies the request, derives its retrieval configuration, and
    assembles the engine's execution request.

    **No retrieval criteria are accepted from the caller** - deriving
    them is the entire point of this stage. The only caller-supplied
    parameters are request provenance and the runtime selection the
    engine already exposes; there is deliberately no way to pass prompt
    instructions, a workflow name, or a retrieval override through here.
    """

    classification = engineering_intent_service.classify(
        project_id=project_id,
        engineering_session_id=engineering_session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_text=request_text,
        classified_at=now,
        working_memory_has_open_question=working_memory_has_open_question,
        working_memory_active_response_count=(
            working_memory_active_response_count
        ),
    )
    intent = classification.intent

    if intent.intent_type is EngineeringIntentType.ENGINEERING_COMPARISON:
        return _prepare_comparison(
            intent=intent,
            project_id=project_id,
            engineering_session_id=engineering_session_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_text=request_text,
            now=now,
            provider_id=provider_id,
            model_identifier=model_identifier,
            request_correlation_id=request_correlation_id,
            working_memory_has_open_question=(
                working_memory_has_open_question
            ),
            working_memory_active_response_count=(
                working_memory_active_response_count
            ),
        )

    bridge = derive_retrieval_configuration(intent, derived_at=now)

    if not bridge.resolved:
        return PreparedEngineeringRequest(
            prepared=False,
            project_id=project_id,
            intent=intent,
            bridge=bridge,
        )

    configuration = bridge.configuration

    return PreparedEngineeringRequest(
        prepared=True,
        project_id=project_id,
        intent=intent,
        bridge=bridge,
        execution_request=EngineeringEngineExecutionRequest(
            project_id=project_id,
            engineering_session_id=engineering_session_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_text=request_text,
            engineering_intent_id=intent.engineering_intent_id.value,
            intent_type=intent.intent_type,
            executed_at=now,
            retrieval_limit=configuration.limit,
            retrieval_include_neighborhood=(
                configuration.include_neighborhood
            ),
            retrieval_neighborhood_depth=configuration.neighborhood_depth,
            retrieval_entity_type=configuration.entity_type,
            retrieval_canonical_entity_id=configuration.canonical_entity_id,
            retrieval_attribute_name=configuration.attribute_name,
            retrieval_lexical_terms=configuration.lexical_terms,
            provider_id=provider_id,
            model_identifier=model_identifier,
            request_correlation_id=request_correlation_id,
            working_memory_has_open_question=(
                working_memory_has_open_question
            ),
            working_memory_active_response_count=(
                working_memory_active_response_count
            ),
        ),
    )


def _prepare_comparison(
    *,
    intent: EngineeringIntent,
    project_id: int,
    engineering_session_id: str,
    conversation_id: str,
    turn_id: str,
    request_text: str,
    now: datetime,
    provider_id: str | None,
    model_identifier: str | None,
    request_correlation_id: str | None,
    working_memory_has_open_question: bool,
    working_memory_active_response_count: int,
) -> PreparedEngineeringRequest:
    """
    The comparison arm (Milestone 24.2).

    Structurally identical to the single-operand path - classify, derive,
    assemble - but the derivation produces **two** typed operands, and the
    execution request carries them in named ``comparison_left`` /
    ``comparison_right`` fields rather than in the flat single-operand
    ``retrieval_*`` configuration. The flat fields are deliberately left
    at their defaults: a comparison has no single retrieval configuration,
    and filling them with one side's would make that side look like the
    whole request.
    """

    comparison = derive_comparison_configuration(intent, derived_at=now)

    if not comparison.resolved:
        return PreparedEngineeringRequest(
            prepared=False,
            project_id=project_id,
            intent=intent,
            comparison_bridge=comparison,
        )

    configuration = comparison.configuration

    return PreparedEngineeringRequest(
        prepared=True,
        project_id=project_id,
        intent=intent,
        comparison_bridge=comparison,
        execution_request=EngineeringEngineExecutionRequest(
            project_id=project_id,
            engineering_session_id=engineering_session_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            request_text=request_text,
            engineering_intent_id=intent.engineering_intent_id.value,
            intent_type=intent.intent_type,
            executed_at=now,
            provider_id=provider_id,
            model_identifier=model_identifier,
            request_correlation_id=request_correlation_id,
            working_memory_has_open_question=(
                working_memory_has_open_question
            ),
            working_memory_active_response_count=(
                working_memory_active_response_count
            ),
            comparison_left=_operand_criteria(configuration.left),
            comparison_right=_operand_criteria(configuration.right),
        ),
    )
