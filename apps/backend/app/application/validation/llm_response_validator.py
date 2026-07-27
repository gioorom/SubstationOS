"""
Validation (EPIC 4, Milestone 17). Proves, after normalization, that
an ``LLMResponseEnvelope`` satisfies every structural invariant this
milestone requires - never a gate a caller must pass, and never a use
of the model itself to validate its own response (Milestone 17's own
"do not use the model to validate its own response" rule). O(n) in the
number of content blocks and attempts (both small, bounded
collections).
"""

from __future__ import annotations

from app.application.models.llm_invocation import (
    LLMInvocationStatus,
    LLMResponseEnvelope,
    LLMResponseValidationResult,
)

_SECRET_LIKE_SUBSTRINGS = ("api_key", "apikey", "authorization", "bearer ", "sk-")


def _contains_secret_like_text(value: str) -> bool:
    lowered = value.lower()
    return any(substring in lowered for substring in _SECRET_LIKE_SUBSTRINGS)


def validate_envelope(
    envelope: LLMResponseEnvelope, *, configured_model_identifier: str
) -> LLMResponseValidationResult:
    errors: list[str] = []

    if (
        envelope.status is LLMInvocationStatus.SUCCEEDED
        and not envelope.content
    ):
        errors.append(
            "A successful envelope has no response content blocks."
        )

    if envelope.configured_model_identifier != configured_model_identifier:
        errors.append(
            "Envelope's configured_model_identifier does not match the "
            "model identifier that was actually requested."
        )

    for field_name, value in (
        ("input_tokens", envelope.usage.input_tokens),
        ("output_tokens", envelope.usage.output_tokens),
        ("total_tokens", envelope.usage.total_tokens),
        ("cached_input_tokens", envelope.usage.cached_input_tokens),
        ("cache_creation_tokens", envelope.usage.cache_creation_tokens),
    ):
        if value is not None and value < 0:
            errors.append(f"Usage field '{field_name}' is negative.")

    if envelope.attempt_count != len(envelope.attempts):
        errors.append(
            "attempt_count is inconsistent with the recorded attempts."
        )

    if envelope.completed_at < envelope.started_at:
        errors.append("completed_at precedes started_at.")

    if envelope.latency_seconds < 0:
        errors.append("latency_seconds is negative.")

    if not envelope.request_correlation_id or not envelope.request_correlation_id.strip():
        errors.append("request_correlation_id is missing.")

    if _contains_secret_like_text(envelope.request_correlation_id):
        errors.append("request_correlation_id looks like it may contain a secret.")

    for warning in envelope.warnings:
        if _contains_secret_like_text(warning):
            errors.append("A warning message looks like it may contain a secret.")

    return LLMResponseValidationResult(valid=not errors, errors=tuple(errors))
