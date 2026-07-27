from __future__ import annotations

import pytest

from app.application.models.llm_exceptions import (
    DuplicateProviderRegistrationError,
    UnknownProviderError,
)
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeLLMProviderAdapter,
)


def test_resolve_returns_the_registered_adapter():
    registry = LLMProviderRegistry()
    adapter = FakeLLMProviderAdapter(provider_id="fake")
    registry.register("fake", adapter)

    assert registry.resolve("fake") is adapter


def test_resolve_rejects_an_unknown_provider():
    registry = LLMProviderRegistry()
    with pytest.raises(UnknownProviderError):
        registry.resolve("does-not-exist")


def test_register_rejects_a_duplicate_provider_id():
    registry = LLMProviderRegistry()
    registry.register("fake", FakeLLMProviderAdapter(provider_id="fake"))

    with pytest.raises(DuplicateProviderRegistrationError):
        registry.register("fake", FakeLLMProviderAdapter(provider_id="fake"))


def test_registered_provider_ids_lists_every_registration():
    registry = LLMProviderRegistry()
    registry.register("fake", FakeLLMProviderAdapter(provider_id="fake"))
    registry.register("anthropic", FakeLLMProviderAdapter(provider_id="anthropic"))

    assert registry.registered_provider_ids() == ("anthropic", "fake")
