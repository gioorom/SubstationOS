"""
Reading configuration from the environment (EPIC 33.R2).

``apps/backend/.env.example`` ships every variable **present and blank**,
and tells the reader they may copy it and leave every line alone. That
promise is the contract these tests pin.

It was not being kept. ``os.getenv(name, default)`` returns its default
only when the name is *absent*, so a blank line in a real ``.env`` set the
provider id to the empty string instead of leaving it defaulted - and a
credential lookup for a provider called ``""`` then failed 17 API tests.

The defect was invisible from two directions at once: the developer's tree
has no ``.env``, and CI never creates one, so the only person who could
meet it was a reviewer following the setup instructions literally. Hence
these tests, which construct the condition explicitly rather than relying
on anyone's filesystem.
"""

from __future__ import annotations

import pytest

from app.application.config.llm_configuration import (
    DEFAULT_PROVIDER_ID,
    DEFAULT_RUNTIME_ENABLED,
    LLM_PROVIDER_ENV_VAR,
    LLM_RUNTIME_ENABLED_ENV_VAR,
    load_llm_configuration_from_env,
)


def test_a_blank_provider_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact shape a copied `.env.example` produces."""

    monkeypatch.setenv(LLM_PROVIDER_ENV_VAR, "")

    assert load_llm_configuration_from_env().provider_id == (
        DEFAULT_PROVIDER_ID
    )


def test_whitespace_is_not_a_provider_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LLM_PROVIDER_ENV_VAR, "   ")

    assert load_llm_configuration_from_env().provider_id == (
        DEFAULT_PROVIDER_ID
    )


def test_an_absent_provider_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LLM_PROVIDER_ENV_VAR, raising=False)

    assert load_llm_configuration_from_env().provider_id == (
        DEFAULT_PROVIDER_ID
    )


def test_a_real_provider_is_read_and_trimmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank means unset; a value still means what it says."""

    monkeypatch.setenv(LLM_PROVIDER_ENV_VAR, "  anthropic  ")

    assert load_llm_configuration_from_env().provider_id == "anthropic"


def test_a_blank_runtime_flag_keeps_invocation_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The same rule on the flag that decides whether project content may
    leave the process. It already behaved correctly - pinned because a
    blank line in a `.env` must never be the thing that enables it.
    """

    from app.application.config.llm_configuration import (
        load_llm_runtime_configuration_from_env,
    )

    monkeypatch.setenv(LLM_RUNTIME_ENABLED_ENV_VAR, "")

    assert load_llm_runtime_configuration_from_env().enabled is (
        DEFAULT_RUNTIME_ENABLED
    )
    assert DEFAULT_RUNTIME_ENABLED is False
