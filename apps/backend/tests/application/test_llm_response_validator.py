from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationStatus,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMUsage,
)
from app.application.validation.llm_response_validator import validate_envelope

NOW = datetime(2026, 1, 1, 3, 0, 0)


def _envelope(**overrides) -> LLMResponseEnvelope:
    defaults = dict(
        provider_id="fake",
        configured_model_identifier="fake-model",
        returned_model_identifier="fake-model",
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="hello",
                provider_block_type=None,
                annotations=(),
            ),
        ),
        finish_reason=LLMFinishReason.COMPLETED,
        usage=LLMUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        ),
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id="corr-1",
        provider_request_id="req-1",
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        latency_seconds=1.0,
        attempt_count=0,
        attempts=(),
        warnings=(),
        metadata=LLMResponseMetadata(
            runtime_version="1.0",
            adapter_version="1.0",
            request_preparation_policy_version="1.0",
            prompt_package_version="1.0",
            context_builder_version="1.0",
            prompt_builder_version="1.0",
        ),
    )
    defaults.update(overrides)
    return LLMResponseEnvelope(**defaults)


def test_a_well_formed_envelope_is_valid():
    result = validate_envelope(_envelope(), configured_model_identifier="fake-model")
    assert result.valid is True
    assert result.errors == ()


def test_successful_envelope_with_no_content_is_invalid():
    envelope = _envelope(content=())
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False
    assert any("content" in error for error in result.errors)


def test_model_identifier_mismatch_is_invalid():
    envelope = _envelope(configured_model_identifier="fake-model")
    result = validate_envelope(envelope, configured_model_identifier="different-model")
    assert result.valid is False


def test_negative_usage_is_invalid():
    envelope = _envelope(
        usage=LLMUsage(
            input_tokens=-1,
            output_tokens=5,
            total_tokens=4,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        )
    )
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False


def test_attempt_count_inconsistency_is_invalid():
    envelope = _envelope(attempt_count=3, attempts=())
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False


def test_completed_before_started_is_invalid():
    envelope = _envelope(started_at=NOW, completed_at=NOW - timedelta(seconds=1))
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False


def test_negative_latency_is_invalid():
    envelope = _envelope(latency_seconds=-0.5)
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False


def test_missing_correlation_id_is_invalid():
    envelope = _envelope(request_correlation_id="")
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is False


def test_none_usage_values_are_accepted_as_honestly_unavailable():
    envelope = _envelope(
        usage=LLMUsage(
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        )
    )
    result = validate_envelope(envelope, configured_model_identifier="fake-model")
    assert result.valid is True
