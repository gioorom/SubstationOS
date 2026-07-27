"""
Application service for the LLM Invocation Runtime (EPIC 4, Milestone
17). Orchestrates: runtime enablement, credential presence (never the
credential's own value - see below), request preparation (delegated to
Milestone 16's own ``llm_request_service.prepare_llm_request``, never
re-derived here), adapter resolution, invocation-policy construction,
and running the attempt/retry loop
(``app.application.services.llm_runtime.run_invocation``). No
persistence, no provider fallback, no model fallback, no engineering
interpretation of the response.

**Credential handling:** this service never reads an environment
variable and never sees a credential's actual value. The caller (the
composition root, ``app/routers/llm_provider.py``) checks whether a
credential is configured (via
``app.application.config.llm_configuration.read_provider_credential``)
and passes only a boolean (``credential_present``) plus the
environment variable's *name* (for a helpful, secret-free error
message) - keeping this service fully testable for the "missing
credential" scenario without ever handling a real secret.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from datetime import datetime

from app.application.config.llm_configuration import (
    PROVIDER_ABSTRACTION_VERSION,
    REQUEST_PREPARATION_POLICY_VERSION,
)
from app.application.models.llm_exceptions import (
    LLMRuntimeDisabledError,
    MissingCredentialError,
)
from app.application.models.llm_invocation import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMInvocationPolicy,
    LLMInvocationResult,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRetryPolicy,
    LLMRuntimeConfiguration,
    LLMTimeoutPolicy,
)
from app.application.policies.llm_retry_policy import RETRY_POLICY_VERSION
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.application.services.llm_request_service import prepare_llm_request
from app.application.services.llm_runtime import run_invocation
from app.domain.prompt_builder.prompt_builder_models import PromptPackage

Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


def _build_policy(runtime_configuration: LLMRuntimeConfiguration) -> LLMInvocationPolicy:
    return LLMInvocationPolicy(
        retry_policy=LLMRetryPolicy(
            version=RETRY_POLICY_VERSION,
            max_attempts=runtime_configuration.max_attempts,
            base_delay_seconds=runtime_configuration.retry_base_delay_seconds,
            max_delay_seconds=runtime_configuration.retry_max_delay_seconds,
            jitter_enabled=runtime_configuration.retry_jitter_enabled,
        ),
        timeout_policy=LLMTimeoutPolicy(
            connect_timeout_seconds=runtime_configuration.connect_timeout_seconds,
            read_timeout_seconds=runtime_configuration.read_timeout_seconds,
            total_deadline_seconds=runtime_configuration.total_deadline_seconds,
        ),
        runtime_version=PROVIDER_ABSTRACTION_VERSION,
    )


async def invoke_llm(
    *,
    registry: LLMProviderRegistry,
    runtime_configuration: LLMRuntimeConfiguration,
    credential_present: bool,
    credential_environment_variable_name: str,
    prompt_package: PromptPackage,
    project_id: int,
    provider_selection: LLMProviderSelection | None = None,
    model_selection: LLMModelSelection | None = None,
    generation_parameters: LLMGenerationParameters | None = None,
    capability_requirements: LLMCapabilityRequirements | None = None,
    request_correlation_id: str,
    clock: Clock,
    sleeper: Sleeper,
    random_source: random.Random,
    now: datetime,
) -> LLMInvocationResult:
    if not runtime_configuration.enabled:
        raise LLMRuntimeDisabledError()

    provider_selection = provider_selection or LLMProviderSelection(
        provider_id=runtime_configuration.provider_id
    )

    if not credential_present:
        raise MissingCredentialError(
            provider_selection.provider_id, credential_environment_variable_name
        )

    model_selection = model_selection or LLMModelSelection(
        model_identifier=runtime_configuration.model_identifier
    )

    preparation = prepare_llm_request(
        registry=registry,
        prompt_package=prompt_package,
        project_id=project_id,
        provider_selection=provider_selection,
        model_selection=model_selection,
        generation_parameters=generation_parameters,
        capability_requirements=capability_requirements,
        request_correlation_id=request_correlation_id,
        request_preparation_policy_version=REQUEST_PREPARATION_POLICY_VERSION,
        now=now,
    )

    adapter = registry.resolve(provider_selection.provider_id)
    policy = _build_policy(runtime_configuration)

    return await run_invocation(
        adapter=adapter,
        request=preparation.request,
        prepared_request=preparation.prepared_request,
        policy=policy,
        request_correlation_id=request_correlation_id,
        clock=clock,
        sleeper=sleeper,
        random_source=random_source,
    )
