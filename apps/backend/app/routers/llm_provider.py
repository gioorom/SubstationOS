"""
Request-preparation and invocation endpoints for the LLM Provider
Abstraction Layer (EPIC 4, Milestones 16-17). This router is the
composition root that wires a concrete ``AnthropicAdapter`` (and, for
real invocation, an injected ``AsyncAnthropic`` client) into an
``LLMProviderRegistry`` from runtime configuration - the
provider-neutral application layer (``app/application/**``) itself
never imports a concrete adapter or reads a credential.
``/prepare-request`` (Milestone 16) never invokes anything and remains
unchanged; ``/invoke`` (Milestone 17) is the first endpoint in this
codebase that may perform a real external network call, and only when
``LLM_RUNTIME_ENABLED=true`` and a credential is configured.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.application.config.llm_configuration import (
    LLMConfiguration,
    PROVIDER_CREDENTIAL_ENV_VARS,
    load_llm_configuration_from_env,
    load_llm_runtime_configuration_from_env,
    read_provider_credential,
)
from app.application.models.llm_exceptions import LLMProviderAbstractionError
from app.application.models.llm_invocation import (
    LLMInvocationResult,
    LLMRuntimeConfiguration,
)
from app.application.models.llm_request import (
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequestPreparationResult,
)
from app.application.services.llm_invocation_service import invoke_llm
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.application.services.llm_request_service import prepare_llm_request
from app.application.services.llm_runtime_metrics import RUNTIME_METRICS
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.anthropic.anthropic_client import build_anthropic_client
from app.schemas.llm_provider import (
    LLMInvocationResultRead,
    LLMInvokeRequestBody,
    LLMPrepareRequestBody,
    LLMRequestPreparationResultRead,
)
from app.schemas.prompt_builder import prompt_package_from_schema

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["LLM Provider"],
)


def _build_registry_for_preparation(
    configuration: LLMConfiguration,
) -> LLMProviderRegistry:
    registry = LLMProviderRegistry()
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(
            model_identifier=configuration.model_identifier,
            default_max_output_tokens=configuration.default_max_output_tokens,
        ),
    )

    return registry


def _build_registry_for_invocation(
    runtime_configuration: LLMRuntimeConfiguration, api_key: str | None
) -> LLMProviderRegistry:
    """
    Constructs a real ``AsyncAnthropic`` client only when a credential
    is actually present - never eagerly, never unconditionally. When
    ``api_key`` is ``None`` (runtime disabled or credential missing),
    the registered adapter still exists (so preparation-only paths and
    ``validate_configuration`` remain inspectable) but carries no
    client; calling its ``invoke()`` in that state fails loudly rather
    than silently, per ``AnthropicAdapter.invoke``'s own contract.
    """

    registry = LLMProviderRegistry()
    client = (
        build_anthropic_client(
            api_key=api_key,
            connect_timeout_seconds=runtime_configuration.connect_timeout_seconds,
            read_timeout_seconds=runtime_configuration.read_timeout_seconds,
        )
        if api_key
        else None
    )
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(
            model_identifier=runtime_configuration.model_identifier,
            default_max_output_tokens=runtime_configuration.default_max_output_tokens,
            client=client,
        ),
    )

    return registry


@router.post(
    "/projects/{project_id}/llm/prepare-request",
    response_model=LLMRequestPreparationResultRead,
    summary="Prepare a provider-native LLM request from a PromptPackage "
    "without invoking any provider",
)
def prepare_request(
    project_id: int,
    body: LLMPrepareRequestBody,
) -> LLMRequestPreparationResult:
    configuration = load_llm_configuration_from_env()
    registry = _build_registry_for_preparation(configuration)

    prompt_package = prompt_package_from_schema(body.prompt_package)

    provider_selection = LLMProviderSelection(
        provider_id=body.provider_id or configuration.provider_id
    )
    model_selection = LLMModelSelection(
        model_identifier=body.model_identifier or configuration.model_identifier
    )

    generation_input = body.generation_parameters
    generation_parameters = LLMGenerationParameters(
        max_output_tokens=(
            generation_input.max_output_tokens if generation_input else None
        ),
        temperature=generation_input.temperature if generation_input else None,
        stop_sequences=(
            tuple(generation_input.stop_sequences) if generation_input else ()
        ),
        deterministic_preference=(
            generation_input.deterministic_preference
            if generation_input
            else False
        ),
    )

    try:
        return prepare_llm_request(
            registry=registry,
            prompt_package=prompt_package,
            project_id=project_id,
            provider_selection=provider_selection,
            model_selection=model_selection,
            generation_parameters=generation_parameters,
            request_correlation_id=str(uuid.uuid4()),
            request_preparation_policy_version=(
                configuration.request_preparation_policy_version
            ),
            now=datetime.utcnow(),
        )
    except LLMProviderAbstractionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/projects/{project_id}/llm/invoke",
    response_model=LLMInvocationResultRead,
    summary="Invoke the configured LLM provider with a PromptPackage and "
    "return a normalized LLMResponseEnvelope or terminal provider error",
)
async def invoke(
    project_id: int,
    body: LLMInvokeRequestBody,
) -> LLMInvocationResult:
    runtime_configuration = load_llm_runtime_configuration_from_env()
    provider_id = body.provider_id or runtime_configuration.provider_id
    credential = read_provider_credential(provider_id)
    credential_env_var_name = PROVIDER_CREDENTIAL_ENV_VARS.get(provider_id, "")

    registry = _build_registry_for_invocation(runtime_configuration, credential)
    prompt_package = prompt_package_from_schema(body.prompt_package)

    provider_selection = LLMProviderSelection(provider_id=provider_id)
    model_selection = LLMModelSelection(
        model_identifier=(
            body.model_identifier or runtime_configuration.model_identifier
        )
    )

    generation_input = body.generation_parameters
    generation_parameters = LLMGenerationParameters(
        max_output_tokens=(
            generation_input.max_output_tokens if generation_input else None
        ),
        temperature=generation_input.temperature if generation_input else None,
        stop_sequences=(
            tuple(generation_input.stop_sequences) if generation_input else ()
        ),
        deterministic_preference=(
            generation_input.deterministic_preference
            if generation_input
            else False
        ),
    )

    request_correlation_id = body.request_correlation_id or str(uuid.uuid4())

    logger.info(
        "llm invoke endpoint received request project_id=%s provider=%s "
        "correlation_id=%s",
        project_id,
        provider_id,
        request_correlation_id,
    )

    try:
        result = await invoke_llm(
            registry=registry,
            runtime_configuration=runtime_configuration,
            credential_present=credential is not None,
            credential_environment_variable_name=credential_env_var_name,
            prompt_package=prompt_package,
            project_id=project_id,
            provider_selection=provider_selection,
            model_selection=model_selection,
            generation_parameters=generation_parameters,
            request_correlation_id=request_correlation_id,
            clock=lambda: datetime.utcnow(),
            sleeper=asyncio.sleep,
            random_source=random.Random(),
            now=datetime.utcnow(),
        )
    except LLMProviderAbstractionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    RUNTIME_METRICS.record_result(result)

    return result
