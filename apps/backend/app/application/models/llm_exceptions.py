"""
Typed exceptions for the LLM Provider Abstraction Layer (EPIC 4,
Milestones 16-17). Every exception here represents either invalid
caller input or a genuinely impossible/programmer-error state
(CLAUDE.md SS15, "use exceptions only for programmer errors or
impossible states") - a merely *optional* capability or generation
parameter the resolved provider does not support is reported as a
warning instead (see ``llm_capabilities.LLMCapabilityValidationResult``),
and an *expected* provider failure during invocation (rate limiting, a
transient server error, ...) is reported as an inspectable
``LLMProviderError`` value on ``LLMInvocationResult``, never raised as
an exception (Milestone 17's own "expected provider failures should be
inspectable operational outcomes" rule). No provider SDK exception
ever crosses out of ``app/infrastructure/llm/anthropic/**`` - every one
is normalized into an ``LLMProviderError`` value before it reaches this
layer.
"""

from __future__ import annotations

import asyncio

from app.application.models.llm_capabilities import LLMCapability
from app.application.models.llm_invocation import (
    LLMInvocationAttempt,
    LLMProviderError,
)


class LLMProviderAbstractionError(Exception):
    """Base class for every exception raised by the LLM Provider
    Abstraction Layer."""


class InvalidProjectIdError(LLMProviderAbstractionError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class ProjectIdMismatchError(LLMProviderAbstractionError):
    def __init__(self, path_project_id: int, prompt_package_project_id: int) -> None:
        self.path_project_id = path_project_id
        self.prompt_package_project_id = prompt_package_project_id

        super().__init__(
            f"Project id mismatch: path project id {path_project_id} "
            "does not match the supplied PromptPackage's project id "
            f"{prompt_package_project_id}."
        )


class InvalidPromptPackageError(LLMProviderAbstractionError):
    def __init__(self, reason: str) -> None:
        self.reason = reason

        super().__init__(f"Invalid PromptPackage: {reason}")


class MissingProviderSelectionError(LLMProviderAbstractionError):
    def __init__(self) -> None:
        super().__init__("A provider selection is required.")


class MissingModelSelectionError(LLMProviderAbstractionError):
    def __init__(self) -> None:
        super().__init__("A model selection is required.")


class InvalidModelIdentifierError(LLMProviderAbstractionError):
    def __init__(self, model_identifier: str, maximum_length: int) -> None:
        self.model_identifier = model_identifier

        super().__init__(
            f"Invalid model identifier: '{model_identifier}' (must be "
            f"non-blank and at most {maximum_length} characters). Model "
            "identifiers are opaque, runtime-configured strings - never "
            "validated against a static list of known model names."
        )


class InvalidGenerationParametersError(LLMProviderAbstractionError):
    def __init__(self, reason: str) -> None:
        self.reason = reason

        super().__init__(f"Invalid generation parameters: {reason}")


class UnknownProviderError(LLMProviderAbstractionError):
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

        super().__init__(f"Unknown LLM provider: '{provider_id}'.")


class DuplicateProviderRegistrationError(LLMProviderAbstractionError):
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

        super().__init__(
            f"An adapter is already registered for provider '{provider_id}'."
        )


class ProviderMismatchError(LLMProviderAbstractionError):
    """The registry resolved an adapter whose own declared
    ``provider_id`` disagrees with the requested provider id - an
    impossible state under correct registry configuration, guarded
    defensively rather than assumed."""

    def __init__(self, requested_provider_id: str, adapter_provider_id: str) -> None:
        self.requested_provider_id = requested_provider_id
        self.adapter_provider_id = adapter_provider_id

        super().__init__(
            f"Provider mismatch: requested '{requested_provider_id}' but "
            f"the resolved adapter declares '{adapter_provider_id}'."
        )


class UnsupportedCapabilityError(LLMProviderAbstractionError):
    def __init__(
        self, provider_id: str, missing_capabilities: tuple[LLMCapability, ...]
    ) -> None:
        self.provider_id = provider_id
        self.missing_capabilities = missing_capabilities

        joined = ", ".join(capability.value for capability in missing_capabilities)
        super().__init__(
            f"Provider '{provider_id}' does not support required "
            f"capabilities: {joined}."
        )


class ProviderRequestMappingError(LLMProviderAbstractionError):
    def __init__(self, provider_id: str, reason: str) -> None:
        self.provider_id = provider_id
        self.reason = reason

        super().__init__(
            f"Failed to map the neutral request into a '{provider_id}' "
            f"request representation: {reason}"
        )


# --- Invocation (Milestone 17) -------------------------------------------


class LLMRuntimeDisabledError(LLMProviderAbstractionError):
    """Invocation was requested while the runtime is disabled (the
    default posture - see ``LLM_RUNTIME_ENABLED`` in
    ``llm_configuration.py``). The preparation-only endpoint
    (Milestone 16) remains available regardless of this flag; only
    real invocation is gated by it."""

    def __init__(self) -> None:
        super().__init__(
            "LLM invocation is disabled. Set LLM_RUNTIME_ENABLED=true to "
            "enable real provider invocation."
        )


class MissingCredentialError(LLMProviderAbstractionError):
    """A provider adapter's required credential is not configured -
    raised before any network access is attempted, the same "fail
    loudly, not silently" discipline ``ClaudeProvider`` (the legacy
    adapter) already established for its own required configuration.
    Never carries the credential's own value, even in the exception
    message."""

    def __init__(self, provider_id: str, environment_variable_name: str) -> None:
        self.provider_id = provider_id
        self.environment_variable_name = environment_variable_name

        super().__init__(
            f"No credential is configured for provider '{provider_id}' "
            f"(expected environment variable '{environment_variable_name}')."
        )


class InvalidInvocationConfigurationError(LLMProviderAbstractionError):
    def __init__(self, reason: str) -> None:
        self.reason = reason

        super().__init__(f"Invalid invocation configuration: {reason}")


class LLMInvocationCancelledError(asyncio.CancelledError):
    """
    Raised when caller cancellation propagates during invocation -
    deliberately a subclass of ``asyncio.CancelledError``, not of
    ``LLMProviderAbstractionError``: cancellation must keep behaving
    like real ``asyncio`` cancellation (it is not caught by an
    ``except Exception`` or ``except LLMProviderAbstractionError``
    clause, including the router's own error-translation logic), while
    still being a distinct, inspectable type carrying the attempt
    history recorded before cancellation - never converted into a
    retryable provider error, never used to start a new attempt.
    """

    def __init__(self, attempts: tuple[LLMInvocationAttempt, ...]) -> None:
        self.attempts = attempts

        super().__init__("LLM invocation was cancelled.")


class ProviderInvocationFailedError(LLMProviderAbstractionError):
    """
    Raised by a provider adapter's own ``invoke()`` when one provider
    call fails - always carrying an already-normalized
    ``LLMProviderError``, never a raw SDK exception. Caught by
    ``llm_runtime.py`` to record the failed attempt and consult the
    retry policy; never allowed to propagate past the runtime itself.
    """

    def __init__(self, provider_error: LLMProviderError) -> None:
        self.provider_error = provider_error

        super().__init__(provider_error.message)
