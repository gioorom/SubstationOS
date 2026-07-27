from __future__ import annotations

import httpx
import anthropic
import pytest

from app.application.models.llm_invocation import (
    LLMProviderErrorCategory,
    LLMTimeoutPhase,
)
from app.infrastructure.llm.anthropic.anthropic_error_mapper import (
    map_anthropic_exception_to_provider_error,
)
from tests.infrastructure._anthropic_test_support import make_httpx_response


def _status_error(cls, status_code: int, *, headers=None, error_type="test_error"):
    response = make_httpx_response(status_code, headers=headers)
    return cls(
        "synthetic error",
        response=response,
        body={"error": {"type": error_type, "message": "synthetic"}},
    )


@pytest.mark.parametrize(
    "exception_factory,expected_category,expected_status",
    [
        (
            lambda: _status_error(anthropic.AuthenticationError, 401),
            LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
            401,
        ),
        (
            lambda: _status_error(anthropic.PermissionDeniedError, 403),
            LLMProviderErrorCategory.AUTHORIZATION_FAILURE,
            403,
        ),
        (
            lambda: _status_error(anthropic.NotFoundError, 404),
            LLMProviderErrorCategory.MODEL_NOT_FOUND,
            404,
        ),
        (
            lambda: _status_error(anthropic.BadRequestError, 400),
            LLMProviderErrorCategory.INVALID_REQUEST,
            400,
        ),
        (
            lambda: _status_error(anthropic.UnprocessableEntityError, 422),
            LLMProviderErrorCategory.UNSUPPORTED_REQUEST,
            422,
        ),
        (
            lambda: _status_error(anthropic.ConflictError, 409),
            LLMProviderErrorCategory.INVALID_REQUEST,
            409,
        ),
        (
            lambda: _status_error(anthropic.RequestTooLargeError, 413),
            LLMProviderErrorCategory.REQUEST_TOO_LARGE,
            413,
        ),
        (
            lambda: _status_error(anthropic.RateLimitError, 429),
            LLMProviderErrorCategory.RATE_LIMITED,
            429,
        ),
        (
            lambda: _status_error(anthropic.OverloadedError, 529),
            LLMProviderErrorCategory.PROVIDER_OVERLOADED,
            529,
        ),
        (
            lambda: _status_error(anthropic.InternalServerError, 500),
            LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            500,
        ),
    ],
)
def test_every_supported_status_error_is_normalized(
    exception_factory, expected_category, expected_status
):
    exc = exception_factory()
    category, message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is expected_category
    assert details.http_status == expected_status
    assert details.provider_error_type == "test_error"
    assert message


def test_rate_limit_error_preserves_retry_after_and_request_id():
    response = make_httpx_response(
        429, headers={"retry-after": "3.5", "request-id": "req_abc123"}
    )
    exc = anthropic.RateLimitError(
        "rate limited",
        response=response,
        body={"error": {"type": "rate_limit_error", "message": "slow down"}},
    )

    category, _message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.RATE_LIMITED
    assert details.retry_after_seconds == 3.5
    assert details.provider_request_id == "req_abc123"


def test_connection_error_maps_to_connection_failure():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.APIConnectionError(request=request)

    category, _message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.CONNECTION_FAILURE
    assert details.http_status is None
    assert details.timeout_phase is None


def test_connect_timeout_maps_to_connection_timeout_with_phase():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    cause = httpx.ConnectTimeout("connect timed out")
    exc = anthropic.APITimeoutError(request=request)
    exc.__cause__ = cause

    category, _message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.CONNECTION_TIMEOUT
    assert details.timeout_phase is LLMTimeoutPhase.CONNECTION


def test_read_timeout_maps_to_read_timeout_with_phase():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    cause = httpx.ReadTimeout("read timed out")
    exc = anthropic.APITimeoutError(request=request)
    exc.__cause__ = cause

    category, _message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.READ_TIMEOUT
    assert details.timeout_phase is LLMTimeoutPhase.READ


def test_timeout_with_unknown_cause_defaults_to_read_timeout_unknown_phase():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.APITimeoutError(request=request)

    category, _message, details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.READ_TIMEOUT
    assert details.timeout_phase is LLMTimeoutPhase.UNKNOWN


def test_unmatched_status_error_maps_to_unknown_provider_error():
    response = make_httpx_response(451)
    exc = anthropic.APIStatusError(
        "unavailable for legal reasons", response=response, body=None
    )

    category, _message, _details = map_anthropic_exception_to_provider_error(exc)

    assert category is LLMProviderErrorCategory.UNKNOWN_PROVIDER_ERROR


def test_arbitrary_non_anthropic_exception_maps_to_unknown_provider_error():
    category, message, details = map_anthropic_exception_to_provider_error(
        ValueError("something unexpected")
    )

    assert category is LLMProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
    assert details.provider_error_type == "ValueError"
    assert "something unexpected" in message


def test_mapped_message_never_contains_the_raw_response_object_repr():
    response = make_httpx_response(500)
    exc = anthropic.InternalServerError(
        "server error", response=response, body={"error": {"type": "api_error"}}
    )

    _category, message, _details = map_anthropic_exception_to_provider_error(exc)

    assert "httpx.Response" not in message
