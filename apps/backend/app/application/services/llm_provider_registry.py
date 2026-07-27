"""
A small, explicit adapter registry (EPIC 4, Milestone 16). Maps a
provider identifier to one configured ``LLMProviderPort`` adapter -
nothing more. Deliberately holds no business logic: it never selects a
provider based on prompt content, never performs automatic cost
routing, and never silently falls back to a different provider than
the one requested. Registration is the composition root's
responsibility (``app/routers/llm_provider.py`` constructs and
registers concrete adapters); this module itself never imports a
concrete adapter, so the provider-neutral application layer stays
genuinely unaware of which providers exist.
"""

from __future__ import annotations

from app.application.models.llm_exceptions import (
    DuplicateProviderRegistrationError,
    UnknownProviderError,
)
from app.application.ports.llm_provider_port import LLMProviderPort


class LLMProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, LLMProviderPort] = {}

    def register(self, provider_id: str, adapter: LLMProviderPort) -> None:
        if provider_id in self._adapters:
            raise DuplicateProviderRegistrationError(provider_id)

        self._adapters[provider_id] = adapter

    def resolve(self, provider_id: str) -> LLMProviderPort:
        try:
            return self._adapters[provider_id]
        except KeyError:
            raise UnknownProviderError(provider_id) from None

    def registered_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
