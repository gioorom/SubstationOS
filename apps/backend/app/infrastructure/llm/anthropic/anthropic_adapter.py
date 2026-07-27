"""
The first provider adapter, targeting Anthropic-compatible Claude
models (EPIC 4, Milestones 16-17) - the intended first production
deployment choice, not the platform's architectural identity
(ADR-0013, ADR-0014).

Milestone 16 established request preparation with **zero** external
provider dependency. Milestone 17 adds real invocation, and with it
the **one** place in this codebase allowed to import the ``anthropic``
SDK for the new, governed path - confined to this package
(``app/infrastructure/llm/anthropic/**``) by dedicated architecture
tests. The adapter never constructs its own client: an
``AsyncAnthropic`` instance (or ``None``, when only preparation is
needed - e.g. Milestone 16's own preparation-only endpoint) is injected
at construction time by the composition root
(``app/routers/llm_provider.py``), never built lazily inside
``invoke()`` itself - tests never need a real client to exercise
preparation, and ``invoke()`` fails loudly and immediately if invoked
without one.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMProviderCapabilities,
)
from app.application.models.llm_invocation import (
    LLMInvocationContext,
    LLMResponseEnvelope,
)
from app.application.models.llm_request import LLMRequest
from app.application.ports.llm_provider_port import LLMProviderPort
from app.infrastructure.llm.anthropic.anthropic_invoker import invoke_anthropic
from app.infrastructure.llm.anthropic.anthropic_mapper import (
    map_llm_request_to_anthropic_prepared_request,
)
from app.infrastructure.llm.anthropic.anthropic_models import (
    AnthropicPreparedRequest,
)

ANTHROPIC_PROVIDER_ID = "anthropic"
ANTHROPIC_ADAPTER_VERSION = "1.0"

# Only capabilities this adapter's own prepare_request()/invoke()
# implementation genuinely honors - streaming, tool use, structured
# output, and multimodal input are all real Anthropic API features,
# but none of them are implemented by this adapter's mapping logic, so
# none are declared (Milestone 16's "only mark capabilities supported
# when the adapter implementation actually supports their request
# preparation" rule, unchanged by Milestone 17).
_SUPPORTED_CAPABILITIES: frozenset[LLMCapability] = frozenset(
    {
        LLMCapability.TEXT_INPUT,
        LLMCapability.STRUCTURED_TEXT_INPUT,
        LLMCapability.CONFIGURABLE_MAX_OUTPUT,
        LLMCapability.TEMPERATURE,
        LLMCapability.STOP_SEQUENCES,
    }
)


class AnthropicAdapter(LLMProviderPort):
    """
    Configured with an opaque, runtime-supplied model identifier - no
    Claude Opus/Sonnet version is assumed to exist, and none is ever
    hardcoded here. Holds no API key itself: the injected ``client``
    (when supplied) already carries its own credential, set up once by
    the composition root, never read or logged by this adapter.
    """

    def __init__(
        self,
        *,
        model_identifier: str,
        default_max_output_tokens: int,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._model_identifier = model_identifier
        self._default_max_output_tokens = default_max_output_tokens
        self._client = client

    def provider_id(self) -> str:
        return ANTHROPIC_PROVIDER_ID

    def provider_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            provider_id=ANTHROPIC_PROVIDER_ID, supported=_SUPPORTED_CAPABILITIES
        )

    def validate_configuration(self) -> tuple[str, ...]:
        problems: list[str] = []

        if not self._model_identifier or not self._model_identifier.strip():
            problems.append(
                "Anthropic adapter has no configured model identifier "
                "(set LLM_MODEL)."
            )

        if self._default_max_output_tokens <= 0:
            problems.append(
                "Anthropic adapter's default max output tokens must be "
                "positive."
            )

        return tuple(problems)

    def prepare_request(self, request: LLMRequest) -> AnthropicPreparedRequest:
        return map_llm_request_to_anthropic_prepared_request(
            request, default_max_output_tokens=self._default_max_output_tokens
        )

    async def invoke(
        self,
        request: LLMRequest,
        prepared_request: AnthropicPreparedRequest,
        invocation_context: LLMInvocationContext,
    ) -> LLMResponseEnvelope:
        if self._client is None:
            raise RuntimeError(
                "AnthropicAdapter.invoke() was called without an injected "
                "AsyncAnthropic client - this is a composition-root wiring "
                "error, never a caller-facing condition."
            )

        return await invoke_anthropic(
            client=self._client,
            prepared_request=prepared_request,
            request=request,
            invocation_context=invocation_context,
            adapter_version=ANTHROPIC_ADAPTER_VERSION,
        )
