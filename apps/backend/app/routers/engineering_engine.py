"""
The Engineering Engine API (Milestone 23A; DOCUMENT_LOOKUP added in
23B.1).

This router is the composition root for one engine execution: it wires
the concrete governed knowledge reader (EPIC 31.2 - engineering
retrieval reads the Governed Knowledge Graph and nothing else), the
Engineering Index repository and document metadata adapter, the LLM provider registry (with a real
Anthropic client only when a credential is present), and runtime
configuration into ``build_engineering_engine`` - the engine itself
never constructs a concrete dependency.

Adding DOCUMENT_LOOKUP changed exactly two things here: the three lines
that wire its two repositories, and this docstring. The endpoint, the
request body and the response shape are unchanged - a caller selects a
workflow only by supplying a classified intent type, never by naming a
workflow.

**Unsupported intents return HTTP 200 with ``status="unsupported"``**,
not a client error: the request was well-formed and the engine answered
it correctly ("no workflow is registered for this intent yet"). This
matches how the LLM Invocation Runtime already reports expected
provider failures as data rather than exceptions (ADR-0014), and keeps
`422` meaning exactly one thing across this codebase - a structurally
invalid request.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.config.llm_configuration import (
    PROVIDER_CREDENTIAL_ENV_VARS,
    load_llm_runtime_configuration_from_env,
    read_provider_credential,
)
from app.application.models.llm_invocation import LLMRuntimeConfiguration
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.database.database import SessionLocal
from app.domain.engineering_engine.engineering_engine_models import (
    ComparisonOperandCriteria,
    EngineeringEngineExecutionRequest,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (  # noqa: E501
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.governed_retrieval.sqlalchemy_governed_knowledge_reader import (  # noqa: E501
    SqlAlchemyGovernedKnowledgeReader,
)
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.anthropic.anthropic_client import (
    build_anthropic_client,
)
from app.schemas.engineering_engine import (
    EngineeringEngineExecuteRequestBody,
    EngineeringEngineExecutionResultRead,
)
from app.services.engineering_engine.composition import (
    build_engineering_engine,
)

router = APIRouter(
    tags=["Engineering Engine"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _build_provider_registry(
    runtime_configuration: LLMRuntimeConfiguration, api_key: str | None
) -> LLMProviderRegistry:
    """Constructs a real ``AsyncAnthropic`` client only when a credential
    is actually present - the same discipline
    ``app/routers/llm_provider.py`` already established."""

    registry = LLMProviderRegistry()
    client = (
        build_anthropic_client(
            api_key=api_key,
            connect_timeout_seconds=(
                runtime_configuration.connect_timeout_seconds
            ),
            read_timeout_seconds=runtime_configuration.read_timeout_seconds,
        )
        if api_key
        else None
    )
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(
            model_identifier=runtime_configuration.model_identifier,
            default_max_output_tokens=(
                runtime_configuration.default_max_output_tokens
            ),
            client=client,
        ),
    )

    return registry


def _operand(body) -> ComparisonOperandCriteria | None:
    """Maps one comparison operand from the request body. ``None`` for
    every workflow that is not a comparison."""

    if body is None:
        return None

    return ComparisonOperandCriteria(
        designation=body.designation,
        retrieval_limit=body.retrieval_limit,
        retrieval_include_neighborhood=body.retrieval_include_neighborhood,
        retrieval_neighborhood_depth=body.retrieval_neighborhood_depth,
        retrieval_entity_type=body.retrieval_entity_type,
        retrieval_canonical_entity_id=body.retrieval_canonical_entity_id,
        retrieval_attribute_name=body.retrieval_attribute_name,
        retrieval_lexical_terms=tuple(body.retrieval_lexical_terms),
    )


@router.post(
    "/projects/{project_id}/engineering-engine/execute",
    response_model=EngineeringEngineExecutionResultRead,
    summary="Select, plan and execute an engineering workflow for a "
    "classified request (KNOWLEDGE_QUERY and DOCUMENT_LOOKUP are "
    "registered; every other intent type returns status='unsupported')",
)
async def execute_engineering_workflow(
    project_id: int,
    body: EngineeringEngineExecuteRequestBody,
    db: Session = Depends(get_db),
) -> EngineeringEngineExecutionResultRead:
    if project_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid project id: '{project_id}'.",
        )

    runtime_configuration = load_llm_runtime_configuration_from_env()
    provider_id = body.provider_id or runtime_configuration.provider_id
    credential = read_provider_credential(provider_id)
    credential_env_var_name = PROVIDER_CREDENTIAL_ENV_VARS.get(provider_id, "")

    engine = build_engineering_engine(
        governed_knowledge_reader=SqlAlchemyGovernedKnowledgeReader(db),
        engineering_index_repository=SqlAlchemyEngineeringIndexRepository(db),
        document_metadata_port=SqlAlchemyDocumentMetadataRepository(db),
        provider_registry=_build_provider_registry(
            runtime_configuration, credential
        ),
        runtime_configuration=runtime_configuration,
        credential_present=credential is not None,
        credential_environment_variable_name=credential_env_var_name,
        clock=lambda: datetime.utcnow(),
        sleeper=asyncio.sleep,
    )

    execution_request = EngineeringEngineExecutionRequest(
        project_id=project_id,
        engineering_session_id=body.engineering_session_id,
        conversation_id=body.conversation_id,
        turn_id=body.turn_id,
        request_text=body.request_text,
        engineering_intent_id=body.engineering_intent_id,
        intent_type=body.intent_type,
        executed_at=datetime.utcnow(),
        retrieval_limit=body.retrieval_limit,
        retrieval_include_neighborhood=body.retrieval_include_neighborhood,
        retrieval_neighborhood_depth=body.retrieval_neighborhood_depth,
        retrieval_entity_type=body.retrieval_entity_type,
        retrieval_canonical_entity_id=body.retrieval_canonical_entity_id,
        retrieval_attribute_name=body.retrieval_attribute_name,
        retrieval_lexical_terms=tuple(body.retrieval_lexical_terms),
        provider_id=body.provider_id,
        model_identifier=body.model_identifier,
        request_correlation_id=body.request_correlation_id,
        working_memory_has_open_question=(
            body.working_memory_has_open_question
        ),
        working_memory_active_response_count=(
            body.working_memory_active_response_count
        ),
        comparison_left=_operand(body.comparison_left),
        comparison_right=_operand(body.comparison_right),
    )

    result = await engine.execute(execution_request)

    return EngineeringEngineExecutionResultRead.from_domain(result)
