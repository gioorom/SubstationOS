from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMProviderCapabilities,
)
from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationAttempt,
    LLMInvocationAttemptStatus,
    LLMInvocationStatus,
    LLMProviderError,
    LLMProviderErrorCategory,
    LLMProviderErrorDetails,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMTimeoutPhase,
    LLMUsage,
)
from app.application.models.llm_request import LLMContentType, LLMMessageRole
from app.schemas.prompt_builder import (
    PromptEvidenceReferenceRead,
    PromptPackageRead,
)

# --- Request -----------------------------------------------------------


class LLMGenerationParametersInput(BaseModel):
    """
    Every field is optional; an omitted field is simply not sent to
    the provider (never silently defaulted to a specific numeric
    value the caller did not ask for, aside from ``max_output_tokens``
    falling back to the adapter's own configured default when the
    provider requires *some* value structurally - see
    ``anthropic_mapper.py``).
    """

    max_output_tokens: int | None = None
    temperature: float | None = None
    stop_sequences: list[str] = Field(default_factory=list)
    deterministic_preference: bool = False


class LLMPrepareRequestBody(BaseModel):
    """
    A request-preparation request. ``project_id`` is deliberately
    absent - the path's own ``{project_id}`` is authoritative.
    ``prompt_package`` is the ``PromptPackage`` a prior call to
    ``/prompt-builder/build`` returned (its ``package`` field) - the
    LLM Provider Abstraction Layer never calls Prompt Builder itself.
    ``provider_id``/``model_identifier`` are optional; when omitted,
    the application's own runtime configuration
    (``LLM_PROVIDER``/``LLM_MODEL``) supplies them.
    """

    prompt_package: PromptPackageRead
    provider_id: str | None = None
    model_identifier: str | None = None
    generation_parameters: LLMGenerationParametersInput | None = None


# --- Response ------------------------------------------------------------


class LLMContentBlockRead(BaseModel):
    content_type: LLMContentType
    text: str

    model_config = ConfigDict(from_attributes=True)


class LLMMessageRead(BaseModel):
    role: LLMMessageRole
    section_type: str
    content_blocks: list[LLMContentBlockRead]

    model_config = ConfigDict(from_attributes=True)


class LLMGenerationParametersRead(BaseModel):
    max_output_tokens: int | None
    temperature: float | None
    stop_sequences: list[str]
    deterministic_preference: bool

    model_config = ConfigDict(from_attributes=True)


class LLMProviderSelectionRead(BaseModel):
    provider_id: str

    model_config = ConfigDict(from_attributes=True)


class LLMModelSelectionRead(BaseModel):
    model_identifier: str

    model_config = ConfigDict(from_attributes=True)


class LLMCapabilityRequirementsRead(BaseModel):
    required_capabilities: list[LLMCapability]

    model_config = ConfigDict(from_attributes=True)


class LLMRequestMetadataRead(BaseModel):
    """
    Operational metadata only - never a secret. No API key, credential,
    or environment value ever appears on this or any other response
    schema in this module (Milestone 16's own security requirement).
    """

    project_id: int
    context_assembly_version: str | None
    prompt_builder_version: str
    composition_policy_version: str
    prompt_package_version: str
    provider_abstraction_version: str
    request_preparation_policy_version: str
    provider_id: str
    model_identifier: str
    request_correlation_id: str
    excluded_section_types: list[str]
    prepared_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMRequestVersionRead(BaseModel):
    provider_abstraction_version: str
    request_preparation_policy_version: str

    model_config = ConfigDict(from_attributes=True)


class LLMRequestRead(BaseModel):
    project_id: int
    provider_selection: LLMProviderSelectionRead
    model_selection: LLMModelSelectionRead
    messages: list[LLMMessageRead]
    references: list[PromptEvidenceReferenceRead]
    generation_parameters: LLMGenerationParametersRead
    capability_requirements: LLMCapabilityRequirementsRead
    metadata: LLMRequestMetadataRead
    version: LLMRequestVersionRead

    model_config = ConfigDict(from_attributes=True)


class LLMProviderCapabilitiesRead(BaseModel):
    provider_id: str
    supported: list[LLMCapability]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(
        cls, capabilities: LLMProviderCapabilities
    ) -> "LLMProviderCapabilitiesRead":
        return cls(
            provider_id=capabilities.provider_id,
            supported=sorted(
                (capability for capability in capabilities.supported),
                key=lambda capability: capability.value,
            ),
        )


class LLMCapabilityValidationResultRead(BaseModel):
    valid: bool
    missing_required_capabilities: list[LLMCapability]
    unsupported_requested_capabilities: list[LLMCapability]

    model_config = ConfigDict(from_attributes=True)


class AnthropicContentBlockRead(BaseModel):
    type: str
    text: str

    model_config = ConfigDict(from_attributes=True)


class AnthropicMessageRead(BaseModel):
    role: str
    content: list[AnthropicContentBlockRead]

    model_config = ConfigDict(from_attributes=True)


class AnthropicPreparedRequestRead(BaseModel):
    """
    Shaped for the currently configured provider adapter (Anthropic,
    this milestone's only production-registered adapter). A future
    provider added to the real router's registry will need its own
    prepared-request response shape - documented as a known extension
    point, not solved speculatively here (see
    ``docs/architecture/llm_provider_abstraction.md``).
    """

    provider_id: str
    model: str
    system: str
    messages: list[AnthropicMessageRead]
    max_tokens: int
    temperature: float | None
    stop_sequences: list[str]

    model_config = ConfigDict(from_attributes=True)


class LLMRequestPreparationResultRead(BaseModel):
    request: LLMRequestRead
    provider_capabilities: LLMProviderCapabilitiesRead
    capability_validation: LLMCapabilityValidationResultRead
    prepared_request: AnthropicPreparedRequestRead
    warnings: list[str]

    model_config = ConfigDict(from_attributes=True)


# --- Invocation (Milestone 17) -------------------------------------------


class LLMInvokeRequestBody(BaseModel):
    """
    A real invocation request. ``project_id`` is deliberately absent -
    the path's own ``{project_id}`` is authoritative.
    ``provider_id``/``model_identifier`` are optional overrides; when
    omitted, the application's own runtime configuration
    (``LLM_PROVIDER``/``LLM_MODEL``) supplies them. **Never accepts an
    API key or any other credential** - credentials are runtime
    configuration only, never a request body field (Milestone 17's own
    "never accept an API key from the request body" requirement).
    """

    prompt_package: PromptPackageRead
    provider_id: str | None = None
    model_identifier: str | None = None
    generation_parameters: LLMGenerationParametersInput | None = None
    request_correlation_id: str | None = None


class LLMProviderErrorDetailsRead(BaseModel):
    http_status: int | None
    provider_error_type: str | None
    provider_request_id: str | None
    retry_after_seconds: float | None
    timeout_phase: LLMTimeoutPhase | None

    model_config = ConfigDict(from_attributes=True)


class LLMProviderErrorRead(BaseModel):
    category: LLMProviderErrorCategory
    message: str
    details: LLMProviderErrorDetailsRead

    model_config = ConfigDict(from_attributes=True)


class LLMInvocationAttemptRead(BaseModel):
    attempt_number: int
    status: LLMInvocationAttemptStatus
    started_at: datetime
    completed_at: datetime
    latency_seconds: float
    error: LLMProviderErrorRead | None

    model_config = ConfigDict(from_attributes=True)


class LLMResponseContentRead(BaseModel):
    sequence_index: int
    content_type: LLMResponseContentType
    text: str
    provider_block_type: str | None
    annotations: list[str]

    model_config = ConfigDict(from_attributes=True)


class LLMUsageRead(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    cache_creation_tokens: int | None

    model_config = ConfigDict(from_attributes=True)


class LLMResponseMetadataRead(BaseModel):
    runtime_version: str
    adapter_version: str
    request_preparation_policy_version: str
    prompt_package_version: str | None
    context_assembly_version: str | None
    prompt_builder_version: str | None

    model_config = ConfigDict(from_attributes=True)


class LLMResponseEnvelopeRead(BaseModel):
    """
    Deliberately exposes only normalized, provider-neutral fields - no
    Anthropic SDK response object, no API key, no authorization
    header, and no raw exception traceback anywhere on this schema
    (Milestone 17's own "must not contain" list).
    """

    provider_id: str
    configured_model_identifier: str
    returned_model_identifier: str | None
    content: list[LLMResponseContentRead]
    finish_reason: LLMFinishReason
    usage: LLMUsageRead
    status: LLMInvocationStatus
    request_correlation_id: str
    provider_request_id: str | None
    started_at: datetime
    completed_at: datetime
    latency_seconds: float
    attempt_count: int
    attempts: list[LLMInvocationAttemptRead]
    warnings: list[str]
    metadata: LLMResponseMetadataRead

    model_config = ConfigDict(from_attributes=True)


class LLMResponseValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


def llm_response_envelope_from_schema(
    model: LLMResponseEnvelopeRead,
) -> LLMResponseEnvelope:
    """
    Reconstructs a domain-owned ``LLMResponseEnvelope`` from its own API
    response shape - the same "reuse the upstream response shape as the
    next stage's request shape" pattern
    ``prompt_package_from_schema``/``context_package_from_schema``
    already established. Used by Engineering Response
    (``app/routers/engineering_response.py``), the first Milestone 18
    capability to consume a previously-returned ``LLMResponseEnvelope``
    as its own input.
    """

    return LLMResponseEnvelope(
        provider_id=model.provider_id,
        configured_model_identifier=model.configured_model_identifier,
        returned_model_identifier=model.returned_model_identifier,
        content=tuple(
            LLMResponseContent(
                sequence_index=c.sequence_index,
                content_type=c.content_type,
                text=c.text,
                provider_block_type=c.provider_block_type,
                annotations=tuple(c.annotations),
            )
            for c in model.content
        ),
        finish_reason=model.finish_reason,
        usage=LLMUsage(
            input_tokens=model.usage.input_tokens,
            output_tokens=model.usage.output_tokens,
            total_tokens=model.usage.total_tokens,
            cached_input_tokens=model.usage.cached_input_tokens,
            cache_creation_tokens=model.usage.cache_creation_tokens,
        ),
        status=model.status,
        request_correlation_id=model.request_correlation_id,
        provider_request_id=model.provider_request_id,
        started_at=model.started_at,
        completed_at=model.completed_at,
        latency_seconds=model.latency_seconds,
        attempt_count=model.attempt_count,
        attempts=tuple(
            LLMInvocationAttempt(
                attempt_number=a.attempt_number,
                status=a.status,
                started_at=a.started_at,
                completed_at=a.completed_at,
                latency_seconds=a.latency_seconds,
                error=(
                    LLMProviderError(
                        category=a.error.category,
                        message=a.error.message,
                        details=LLMProviderErrorDetails(
                            http_status=a.error.details.http_status,
                            provider_error_type=a.error.details.provider_error_type,
                            provider_request_id=a.error.details.provider_request_id,
                            retry_after_seconds=a.error.details.retry_after_seconds,
                            timeout_phase=a.error.details.timeout_phase,
                        ),
                    )
                    if a.error is not None
                    else None
                ),
            )
            for a in model.attempts
        ),
        warnings=tuple(model.warnings),
        metadata=LLMResponseMetadata(
            runtime_version=model.metadata.runtime_version,
            adapter_version=model.metadata.adapter_version,
            request_preparation_policy_version=(
                model.metadata.request_preparation_policy_version
            ),
            prompt_package_version=model.metadata.prompt_package_version,
            context_assembly_version=model.metadata.context_assembly_version,
            prompt_builder_version=model.metadata.prompt_builder_version,
        ),
    )


class LLMInvocationResultRead(BaseModel):
    """
    Either ``envelope`` is populated (``status="succeeded"``,
    ``terminal_error`` is ``None``) or ``terminal_error`` is populated
    (``status`` is ``"failed"``/``"cancelled"``, ``envelope`` is
    ``None``) - never both, never neither (Milestone 17's own
    "success and failure contract").
    """

    status: LLMInvocationStatus
    envelope: LLMResponseEnvelopeRead | None
    terminal_error: LLMProviderErrorRead | None
    attempts: list[LLMInvocationAttemptRead]
    request_correlation_id: str
    validation: LLMResponseValidationResultRead | None

    model_config = ConfigDict(from_attributes=True)
