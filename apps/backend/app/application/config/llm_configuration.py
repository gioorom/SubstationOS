"""
Runtime configuration for the LLM Provider Abstraction Layer (EPIC 4,
Milestones 16-17). Follows this repository's existing configuration
convention exactly (``app/services/ai/claude_provider.py``: plain
``os.getenv``, no settings framework). ``LLMRuntimeConfiguration``
(Milestone 17) never carries a credential - ``read_provider_credential``
reads one directly from the environment, only ever called at the
infrastructure composition root
(``app/routers/llm_provider.py``/``anthropic_client.py``), never stored
on a dataclass that could be logged, serialized, or returned through an
API response.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.application.models.llm_invocation import LLMRuntimeConfiguration

REQUEST_PREPARATION_POLICY_VERSION = "1.0"
PROVIDER_ABSTRACTION_VERSION = "1.0"
RUNTIME_VERSION = "1.0"

LLM_PROVIDER_ENV_VAR = "LLM_PROVIDER"
LLM_MODEL_ENV_VAR = "LLM_MODEL"
LLM_DEFAULT_MAX_OUTPUT_TOKENS_ENV_VAR = "LLM_DEFAULT_MAX_OUTPUT_TOKENS"
LLM_TEMPERATURE_ENV_VAR = "LLM_TEMPERATURE"

# Anthropic is the first intended production deployment target (per
# this milestone's own instructions), not a privileged architectural
# concept - this default only picks which adapter a fresh environment
# exercises out of the box; nothing prevents another registered
# provider identifier from being configured instead.
DEFAULT_PROVIDER_ID = "anthropic"
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# --- Milestone 17: runtime invocation ---------------------------------

LLM_RUNTIME_ENABLED_ENV_VAR = "LLM_RUNTIME_ENABLED"
LLM_CONNECT_TIMEOUT_SECONDS_ENV_VAR = "LLM_CONNECT_TIMEOUT_SECONDS"
LLM_READ_TIMEOUT_SECONDS_ENV_VAR = "LLM_READ_TIMEOUT_SECONDS"
LLM_TOTAL_TIMEOUT_SECONDS_ENV_VAR = "LLM_TOTAL_TIMEOUT_SECONDS"
LLM_MAX_ATTEMPTS_ENV_VAR = "LLM_MAX_ATTEMPTS"
LLM_RETRY_BASE_DELAY_SECONDS_ENV_VAR = "LLM_RETRY_BASE_DELAY_SECONDS"
LLM_RETRY_MAX_DELAY_SECONDS_ENV_VAR = "LLM_RETRY_MAX_DELAY_SECONDS"
LLM_RETRY_JITTER_ENABLED_ENV_VAR = "LLM_RETRY_JITTER_ENABLED"

# Real invocation is disabled unless explicitly turned on - a fresh
# deployment never silently transmits project data to an external
# provider (see ADR-0014's External Data Boundary section).
DEFAULT_RUNTIME_ENABLED = False
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 60.0
DEFAULT_TOTAL_TIMEOUT_SECONDS = 90.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_RETRY_MAX_DELAY_SECONDS = 20.0
DEFAULT_RETRY_JITTER_ENABLED = True

# Which environment variable holds each registered provider's own
# credential - deliberately provider-specific (never a single generic
# "LLM_API_KEY"), since different providers use different secret
# shapes/auth schemes. Reuses the exact variable name the legacy
# ClaudeProvider already reads (the same real Anthropic account's key),
# so an operator configures one secret, not two, for the same provider.
PROVIDER_CREDENTIAL_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
}


@dataclass(frozen=True, slots=True)
class LLMConfiguration:
    provider_id: str
    model_identifier: str
    default_max_output_tokens: int
    default_temperature: float | None
    request_preparation_policy_version: str


def load_llm_configuration_from_env() -> LLMConfiguration:
    """
    Reads ``LLM_PROVIDER``/``LLM_MODEL``/``LLM_DEFAULT_MAX_OUTPUT_TOKENS``/
    ``LLM_TEMPERATURE`` from the environment. ``model_identifier`` has
    no hardcoded fallback of any kind (never a Claude Opus/Sonnet
    version, never a dated model string) - an unset ``LLM_MODEL``
    simply yields an empty string, which
    ``llm_request_validator.py`` rejects as a structurally invalid
    model selection, the same "fail loudly, not silently" posture
    ``ClaudeProvider`` already established for its own required
    configuration.
    """

    max_output_tokens_raw = os.getenv(LLM_DEFAULT_MAX_OUTPUT_TOKENS_ENV_VAR)
    temperature_raw = os.getenv(LLM_TEMPERATURE_ENV_VAR)

    return LLMConfiguration(
        provider_id=os.getenv(LLM_PROVIDER_ENV_VAR, DEFAULT_PROVIDER_ID),
        model_identifier=os.getenv(LLM_MODEL_ENV_VAR, ""),
        default_max_output_tokens=(
            int(max_output_tokens_raw)
            if max_output_tokens_raw
            else DEFAULT_MAX_OUTPUT_TOKENS
        ),
        default_temperature=(
            float(temperature_raw) if temperature_raw else None
        ),
        request_preparation_policy_version=REQUEST_PREPARATION_POLICY_VERSION,
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_llm_runtime_configuration_from_env() -> LLMRuntimeConfiguration:
    """
    Reads every Milestone 17 runtime/timeout/retry environment
    variable. Deliberately never reads a credential - see
    ``read_provider_credential`` for that, called only at the
    composition root.
    """

    base = load_llm_configuration_from_env()

    def _float(name: str, default: float) -> float:
        raw = os.getenv(name)
        return float(raw) if raw else default

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        return int(raw) if raw else default

    return LLMRuntimeConfiguration(
        enabled=_env_bool(LLM_RUNTIME_ENABLED_ENV_VAR, DEFAULT_RUNTIME_ENABLED),
        provider_id=base.provider_id,
        model_identifier=base.model_identifier,
        connect_timeout_seconds=_float(
            LLM_CONNECT_TIMEOUT_SECONDS_ENV_VAR, DEFAULT_CONNECT_TIMEOUT_SECONDS
        ),
        read_timeout_seconds=_float(
            LLM_READ_TIMEOUT_SECONDS_ENV_VAR, DEFAULT_READ_TIMEOUT_SECONDS
        ),
        total_deadline_seconds=_float(
            LLM_TOTAL_TIMEOUT_SECONDS_ENV_VAR, DEFAULT_TOTAL_TIMEOUT_SECONDS
        ),
        max_attempts=_int(LLM_MAX_ATTEMPTS_ENV_VAR, DEFAULT_MAX_ATTEMPTS),
        retry_base_delay_seconds=_float(
            LLM_RETRY_BASE_DELAY_SECONDS_ENV_VAR, DEFAULT_RETRY_BASE_DELAY_SECONDS
        ),
        retry_max_delay_seconds=_float(
            LLM_RETRY_MAX_DELAY_SECONDS_ENV_VAR, DEFAULT_RETRY_MAX_DELAY_SECONDS
        ),
        retry_jitter_enabled=_env_bool(
            LLM_RETRY_JITTER_ENABLED_ENV_VAR, DEFAULT_RETRY_JITTER_ENABLED
        ),
        default_max_output_tokens=base.default_max_output_tokens,
        default_temperature=base.default_temperature,
    )


def read_provider_credential(provider_id: str) -> str | None:
    """
    Reads one provider's credential directly from the environment -
    never stored on ``LLMRuntimeConfiguration`` or any other
    provider-neutral dataclass. Returns ``None`` (never an empty
    string) when unset or blank, so callers can use a simple truthiness
    check. Only ever called at the infrastructure composition root.
    """

    env_var_name = PROVIDER_CREDENTIAL_ENV_VARS.get(provider_id)
    if env_var_name is None:
        return None

    value = os.getenv(env_var_name)
    return value if value else None
