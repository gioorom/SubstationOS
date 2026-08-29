"""
A deterministic, in-memory provider adapter used only by tests (EPIC 4,
Milestones 16-17) - implements ``LLMProviderPort`` (preparation *and*
invocation) with no external dependency and no real network I/O of any
kind, proving both the application layer and the LLM Invocation
Runtime are genuinely provider-neutral rather than secretly coupled to
Anthropic. Never registered by the real application router.

``invoke`` consumes a caller-scripted sequence of
``FakeInvocationOutcome``s, one per attempt (1-indexed; the last
outcome repeats if more attempts occur than outcomes were scripted) -
successful responses, normalized failures (any
``LLMProviderErrorCategory``), and delayed responses (a genuine,
cancellable ``await`` point, so a test can prove real cancellation
propagation) are all expressible without any timing dependency beyond
an injected sleeper.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMProviderCapabilities,
)
from app.application.models.llm_exceptions import ProviderInvocationFailedError
from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationContext,
    LLMInvocationStatus,
    LLMProviderError,
    LLMProviderErrorCategory,
    LLMProviderErrorDetails,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMUsage,
)
from app.application.models.llm_request import LLMMessageRole, LLMRequest
from app.application.ports.llm_provider_port import LLMProviderPort

DEFAULT_FAKE_PROVIDER_ID = "fake"
FAKE_ADAPTER_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class FakePreparedRequest:
    """A local, immutable prepared-request stand-in - deliberately
    unrelated in shape to ``AnthropicPreparedRequest``, so a test
    asserting against this type alone cannot accidentally depend on
    Anthropic-specific structure."""

    model: str
    instruction_text: str
    conversational_text: str
    max_tokens: int
    temperature: float | None
    stop_sequences: tuple[str, ...]
    provider_id: str = DEFAULT_FAKE_PROVIDER_ID


async def _default_sleeper(seconds: float) -> None:
    await asyncio.sleep(seconds)


@dataclass(frozen=True, slots=True)
class FakeInvocationOutcome:
    """One scripted outcome for one invocation attempt. ``delay_seconds``
    (if non-zero) is awaited *before* the outcome resolves - a genuine,
    cancellable suspension point, not a synchronous no-op - so a test
    can cancel the enclosing task mid-invocation and observe real
    cancellation propagation."""

    succeeds: bool = True
    error_category: LLMProviderErrorCategory = (
        LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE
    )
    retry_after_seconds: float | None = None
    delay_seconds: float = 0.0
    text: str = "This is a deterministic fake response."
    content_type: LLMResponseContentType = LLMResponseContentType.TEXT
    provider_block_type: str | None = None
    finish_reason: LLMFinishReason = LLMFinishReason.COMPLETED
    input_tokens: int | None = 10
    output_tokens: int | None = 5
    provider_request_id: str | None = "fake-request-id"


def _default_outcomes() -> tuple[FakeInvocationOutcome, ...]:
    return (FakeInvocationOutcome(),)


class FakeLLMProviderAdapter(LLMProviderPort):
    def __init__(
        self,
        *,
        provider_id: str = DEFAULT_FAKE_PROVIDER_ID,
        supported_capabilities: frozenset[LLMCapability] | None = None,
        default_max_output_tokens: int = 1024,
        configuration_problems: tuple[str, ...] = (),
        outcomes: tuple[FakeInvocationOutcome, ...] = (),
        sleeper: Callable[[float], Awaitable[None]] = _default_sleeper,
    ) -> None:
        self._provider_id = provider_id
        self._supported = (
            supported_capabilities
            if supported_capabilities is not None
            else frozenset({LLMCapability.TEXT_INPUT})
        )
        self._default_max_output_tokens = default_max_output_tokens
        self._configuration_problems = configuration_problems
        self._outcomes = outcomes or _default_outcomes()
        self._sleeper = sleeper
        self.call_count = 0

    def provider_id(self) -> str:
        return self._provider_id

    def provider_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            provider_id=self._provider_id, supported=self._supported
        )

    def validate_configuration(self) -> tuple[str, ...]:
        return self._configuration_problems

    def prepare_request(self, request: LLMRequest) -> FakePreparedRequest:
        instruction_lines = [
            block.text
            for message in request.messages
            if message.role is LLMMessageRole.INSTRUCTION
            for block in message.content_blocks
        ]
        conversational_lines = [
            block.text
            for message in request.messages
            if message.role is not LLMMessageRole.INSTRUCTION
            for block in message.content_blocks
        ]

        return FakePreparedRequest(
            model=request.model_selection.model_identifier,
            instruction_text="\n".join(instruction_lines),
            conversational_text="\n".join(conversational_lines),
            max_tokens=(
                request.generation_parameters.max_output_tokens
                or self._default_max_output_tokens
            ),
            temperature=request.generation_parameters.temperature,
            stop_sequences=request.generation_parameters.stop_sequences,
            provider_id=self._provider_id,
        )

    def _outcome_for_attempt(self, attempt_number: int) -> FakeInvocationOutcome:
        index = min(attempt_number - 1, len(self._outcomes) - 1)
        return self._outcomes[index]

    async def invoke(
        self,
        request: LLMRequest,
        prepared_request: FakePreparedRequest,
        invocation_context: LLMInvocationContext,
    ) -> LLMResponseEnvelope:
        self.call_count += 1
        outcome = self._outcome_for_attempt(invocation_context.attempt_number)

        if outcome.delay_seconds:
            await self._sleeper(outcome.delay_seconds)

        if not outcome.succeeds:
            raise ProviderInvocationFailedError(
                LLMProviderError(
                    category=outcome.error_category,
                    message=f"Fake provider failure: {outcome.error_category.value}",
                    details=LLMProviderErrorDetails(
                        http_status=None,
                        provider_error_type="fake_error",
                        provider_request_id=outcome.provider_request_id,
                        retry_after_seconds=outcome.retry_after_seconds,
                        timeout_phase=None,
                    ),
                )
            )

        is_supported = outcome.content_type is LLMResponseContentType.TEXT
        content = (
            LLMResponseContent(
                sequence_index=0,
                content_type=outcome.content_type,
                text=outcome.text if is_supported else "",
                provider_block_type=outcome.provider_block_type,
                annotations=(),
            ),
        )
        warnings: tuple[str, ...] = (
            ()
            if is_supported
            else (
                "Unsupported provider content block type: "
                f"'{outcome.provider_block_type}'.",
            )
        )

        total_tokens = (
            outcome.input_tokens + outcome.output_tokens
            if outcome.input_tokens is not None and outcome.output_tokens is not None
            else None
        )

        return LLMResponseEnvelope(
            provider_id=self._provider_id,
            configured_model_identifier=request.model_selection.model_identifier,
            returned_model_identifier=request.model_selection.model_identifier,
            content=content,
            finish_reason=outcome.finish_reason,
            usage=LLMUsage(
                input_tokens=outcome.input_tokens,
                output_tokens=outcome.output_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=None,
                cache_creation_tokens=None,
            ),
            status=LLMInvocationStatus.SUCCEEDED,
            request_correlation_id=invocation_context.request_correlation_id,
            provider_request_id=outcome.provider_request_id,
            started_at=invocation_context.deadline_at,
            completed_at=invocation_context.deadline_at,
            latency_seconds=0.0,
            attempt_count=1,
            attempts=(),
            warnings=warnings,
            metadata=LLMResponseMetadata(
                runtime_version=invocation_context.policy.runtime_version,
                adapter_version=FAKE_ADAPTER_VERSION,
                request_preparation_policy_version=(
                    request.version.request_preparation_policy_version
                ),
                prompt_package_version=request.metadata.prompt_package_version,
                context_assembly_version=request.metadata.context_assembly_version,
                prompt_builder_version=request.metadata.prompt_builder_version,
            ),
        )
