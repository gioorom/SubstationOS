"""
The provider-neutral invocation contract (EPIC 4, Milestone 17). Every
type here represents SubstationOS's own view of "what happened when we
called a provider" - never a copy of one provider's response schema.
An ``LLMRequest``/``PreparedProviderRequest`` pair (Milestone 16) is
executed through ``LLMProviderPort.invoke`` and normalized into an
``LLMResponseEnvelope`` here; only a provider-specific infrastructure
adapter (``app.infrastructure.llm.anthropic``) ever sees a provider
SDK's own response or exception type. No type in this module imports a
provider SDK, performs I/O, or reads the wall clock - every timestamp
is supplied by the caller (the runtime), keeping normalization itself
pure and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
    PreparedProviderRequest,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


class LLMInvocationStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LLMInvocationAttemptStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LLMProviderErrorCategory(str, Enum):
    """A closed, exhaustive set of normalized error categories - never
    a provider-native error type or string. See
    ``app.application.policies.llm_retry_policy`` for the fixed,
    documented retryable/non-retryable classification of each value."""

    CONNECTION_FAILURE = "connection_failure"
    CONNECTION_TIMEOUT = "connection_timeout"
    READ_TIMEOUT = "read_timeout"
    TOTAL_DEADLINE_EXCEEDED = "total_deadline_exceeded"
    RATE_LIMITED = "rate_limited"
    PROVIDER_OVERLOADED = "provider_overloaded"
    TRANSIENT_PROVIDER_FAILURE = "transient_provider_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_REQUEST = "unsupported_request"
    MODEL_NOT_FOUND = "model_not_found"
    REQUEST_TOO_LARGE = "request_too_large"
    INVALID_CONFIGURATION = "invalid_configuration"
    RUNTIME_DISABLED = "runtime_disabled"
    CANCELLED = "cancelled"
    CONTENT_POLICY_REJECTION = "content_policy_rejection"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class LLMTimeoutPhase(str, Enum):
    CONNECTION = "connection"
    READ = "read"
    TOTAL_DEADLINE = "total_deadline"
    UNKNOWN = "unknown"


class LLMResponseContentType(str, Enum):
    """Only ``TEXT`` is produced by a genuinely supported provider
    content block this milestone; ``UNSUPPORTED`` represents any
    provider block type SubstationOS does not interpret (tool use,
    thinking, or any future block type) - preserved as a safe type
    identifier plus a structured warning, never silently reinterpreted
    as engineering text."""

    TEXT = "text"
    UNSUPPORTED = "unsupported"


class LLMFinishReason(str, Enum):
    COMPLETED = "completed"
    MAXIMUM_OUTPUT_REACHED = "maximum_output_reached"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_REQUEST = "tool_request"
    REFUSAL = "refusal"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LLMTimeoutPolicy:
    connect_timeout_seconds: float
    read_timeout_seconds: float
    total_deadline_seconds: float


@dataclass(frozen=True, slots=True)
class LLMRetryPolicy:
    version: str
    max_attempts: int
    base_delay_seconds: float
    max_delay_seconds: float
    jitter_enabled: bool


@dataclass(frozen=True, slots=True)
class LLMInvocationPolicy:
    retry_policy: LLMRetryPolicy
    timeout_policy: LLMTimeoutPolicy
    runtime_version: str


@dataclass(frozen=True, slots=True)
class LLMInvocationContext:
    """Everything one provider call needs to know about its own
    attempt and the invocation it belongs to - never a place to smuggle
    engineering content or credentials. ``deadline_at`` is the absolute
    wall-clock deadline for the *entire* invocation (every attempt and
    every retry delay), computed once by the runtime, never recomputed
    per attempt."""

    request_correlation_id: str
    attempt_number: int
    deadline_at: datetime
    policy: LLMInvocationPolicy


@dataclass(frozen=True, slots=True)
class LLMInvocationRequest:
    """The top-level, caller-supplied intent: invoke a provider with
    this ``PromptPackage``, this provider/model selection, these
    portable generation parameters. Mirrors ``PromptBuildRequest``'s
    own shape one layer downstream."""

    project_id: int
    prompt_package: PromptPackage
    provider_selection: LLMProviderSelection
    model_selection: LLMModelSelection
    generation_parameters: LLMGenerationParameters
    capability_requirements: LLMCapabilityRequirements
    request_correlation_id: str


@dataclass(frozen=True, slots=True)
class LLMProviderErrorDetails:
    """Safe, filtered operational details extracted from a provider
    failure - never a raw SDK exception, never a full response body,
    never a header carrying a credential."""

    http_status: int | None
    provider_error_type: str | None
    provider_request_id: str | None
    retry_after_seconds: float | None
    timeout_phase: LLMTimeoutPhase | None


@dataclass(frozen=True, slots=True)
class LLMProviderError:
    category: LLMProviderErrorCategory
    message: str
    details: LLMProviderErrorDetails


@dataclass(frozen=True, slots=True)
class LLMRetryDecision:
    should_retry: bool
    delay_seconds: float
    reason: str


@dataclass(frozen=True, slots=True)
class LLMInvocationAttempt:
    attempt_number: int
    status: LLMInvocationAttemptStatus
    started_at: datetime
    completed_at: datetime
    latency_seconds: float
    error: LLMProviderError | None


@dataclass(frozen=True, slots=True)
class LLMResponseContent:
    sequence_index: int
    content_type: LLMResponseContentType
    text: str
    provider_block_type: str | None
    annotations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Operational telemetry, never billing truth (Milestone 17's own
    "do not calculate costs" rule). Every populated value is
    non-negative; an unavailable value is represented as ``None``,
    never estimated or defaulted to zero."""

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    cache_creation_tokens: int | None


@dataclass(frozen=True, slots=True)
class LLMResponseMetadata:
    runtime_version: str
    adapter_version: str
    request_preparation_policy_version: str
    prompt_package_version: str | None
    context_builder_version: str | None
    prompt_builder_version: str | None


@dataclass(frozen=True, slots=True)
class LLMResponseEnvelope:
    """
    The normalized artifact one successful invocation produces - never
    a provider SDK response object, never a raw exception, never a
    credential. ``attempts``/``attempt_count`` and the top-level
    ``started_at``/``completed_at``/``latency_seconds`` describe the
    *entire* invocation (every attempt and retry delay), overwritten by
    the runtime once the full attempt loop concludes - an individual
    adapter call only ever sees its own single attempt.
    """

    provider_id: str
    configured_model_identifier: str
    returned_model_identifier: str | None
    content: tuple[LLMResponseContent, ...]
    finish_reason: LLMFinishReason
    usage: LLMUsage
    status: LLMInvocationStatus
    request_correlation_id: str
    provider_request_id: str | None
    started_at: datetime
    completed_at: datetime
    latency_seconds: float
    attempt_count: int
    attempts: tuple[LLMInvocationAttempt, ...]
    warnings: tuple[str, ...]
    metadata: LLMResponseMetadata


@dataclass(frozen=True, slots=True)
class LLMResponseValidationResult:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LLMInvocationResult:
    """
    The full, inspectable outcome of one invocation - either a
    successful ``envelope`` (``terminal_error`` is ``None``) or a
    ``terminal_error`` (``envelope`` is ``None``); never both, never
    neither. An apparently successful envelope with empty content after
    a provider failure never occurs - a provider failure always
    produces ``status=FAILED``/``terminal_error``, never a
    ``SUCCEEDED`` envelope with nothing in it.
    """

    status: LLMInvocationStatus
    envelope: LLMResponseEnvelope | None
    terminal_error: LLMProviderError | None
    attempts: tuple[LLMInvocationAttempt, ...]
    request_correlation_id: str
    validation: LLMResponseValidationResult | None


@dataclass(frozen=True, slots=True)
class LLMRuntimeVersion:
    runtime_version: str
    retry_policy_version: str
    request_preparation_policy_version: str


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfiguration:
    """
    Runtime enablement and policy configuration - **never carries a
    credential**. The API key is read separately, only at the
    infrastructure composition root
    (``app/routers/llm_provider.py``/``anthropic_client.py``), and never
    stored on this or any other provider-neutral dataclass, so it can
    never be accidentally logged, serialized, or returned through an
    API response.
    """

    enabled: bool
    provider_id: str
    model_identifier: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    total_deadline_seconds: float
    max_attempts: int
    retry_base_delay_seconds: float
    retry_max_delay_seconds: float
    retry_jitter_enabled: bool
    default_max_output_tokens: int
    default_temperature: float | None


__all__ = [
    "LLMInvocationStatus",
    "LLMInvocationAttemptStatus",
    "LLMProviderErrorCategory",
    "LLMTimeoutPhase",
    "LLMResponseContentType",
    "LLMFinishReason",
    "LLMTimeoutPolicy",
    "LLMRetryPolicy",
    "LLMInvocationPolicy",
    "LLMInvocationContext",
    "LLMInvocationRequest",
    "LLMProviderErrorDetails",
    "LLMProviderError",
    "LLMRetryDecision",
    "LLMInvocationAttempt",
    "LLMResponseContent",
    "LLMUsage",
    "LLMResponseMetadata",
    "LLMResponseEnvelope",
    "LLMResponseValidationResult",
    "LLMInvocationResult",
    "LLMRuntimeVersion",
    "LLMRuntimeConfiguration",
    "LLMRequest",
    "PreparedProviderRequest",
]
