"""
The application-owned port every language-model provider adapter must
implement (EPIC 4, Milestones 16-17). Expresses exactly what
SubstationOS's application layer needs from a provider - never a
provider SDK type, never a provider-native role or payload shape.

Milestone 17 evolves this port minimally: one new async method,
``invoke``, added alongside the three Milestone 16 methods
(preparation and invocation remain two separate operations - an
adapter's ``prepare_request`` still performs no I/O). No
chat/agent/tool/embedding/image method is added - the smallest useful
interface remains the goal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.models.llm_capabilities import LLMProviderCapabilities
from app.application.models.llm_invocation import (
    LLMInvocationContext,
    LLMResponseEnvelope,
)
from app.application.models.llm_request import LLMRequest, PreparedProviderRequest


class LLMProviderPort(ABC):
    """
    One configured adapter for one language-model provider. An
    implementation must perform no network I/O, no client
    construction, and no response parsing this milestone - only
    structural configuration validation and deterministic request
    translation.
    """

    @abstractmethod
    def provider_id(self) -> str:
        """This adapter's own provider identifier - must match the
        identifier under which the adapter was registered in an
        ``LLMProviderRegistry`` (checked defensively by
        ``LLMRequestPreparationService``, never assumed)."""

        raise NotImplementedError

    @abstractmethod
    def provider_capabilities(self) -> LLMProviderCapabilities:
        """Which capabilities this adapter's own ``prepare_request``
        implementation genuinely supports - never a capability the
        adapter cannot actually honor."""

        raise NotImplementedError

    @abstractmethod
    def validate_configuration(self) -> tuple[str, ...]:
        """
        Structural configuration problems only (e.g. a blank model
        identifier) - an empty tuple means the adapter's own
        configuration is structurally sound. Never checks an API key's
        presence or validity: this milestone performs no network call,
        so there is nothing to authenticate against yet.
        """

        raise NotImplementedError

    @abstractmethod
    def prepare_request(self, request: LLMRequest) -> PreparedProviderRequest:
        """
        Translates a provider-neutral ``LLMRequest`` into this
        provider's own local, immutable prepared-request
        representation. Performs no I/O, no serialization, and no HTTP
        transmission - the result is never sent anywhere this
        milestone.
        """

        raise NotImplementedError

    @abstractmethod
    async def invoke(
        self,
        request: LLMRequest,
        prepared_request: PreparedProviderRequest,
        invocation_context: LLMInvocationContext,
    ) -> LLMResponseEnvelope:
        """
        Performs exactly **one** provider call for **one** runtime
        attempt (``invocation_context.attempt_number``) and returns a
        normalized ``LLMResponseEnvelope`` on success. On failure, an
        implementation raises
        ``app.application.models.llm_exceptions.ProviderInvocationFailedError``
        carrying an already-normalized ``LLMProviderError`` - never a
        raw provider SDK exception, and never a partially-populated
        "successful" envelope. An implementation must never retry
        internally (retry decisions belong exclusively to
        ``app.application.services.llm_runtime`` - see
        ``invocation_context.policy.retry_policy``), never persist the
        request or response, and never expose a provider SDK object or
        a credential anywhere in its return value or in any exception
        it raises.
        """

        raise NotImplementedError
