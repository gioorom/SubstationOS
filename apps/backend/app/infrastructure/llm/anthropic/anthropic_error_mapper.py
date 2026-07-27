"""
Normalizes every Anthropic SDK exception into a provider-neutral
``LLMProviderError`` (EPIC 4, Milestone 17). No raw SDK exception, HTTP
response object, request payload, or credential ever crosses out of
this module - only safe, already-extracted operational fields
(status code, provider error type, provider request id, a
``Retry-After`` hint, a filtered message summary).

Mapping table (``anthropic`` 0.117.x error hierarchy ->
``LLMProviderErrorCategory``):

| Anthropic exception       | HTTP | Category                      |
|----------------------------|-----:|--------------------------------|
| ``AuthenticationError``    |  401 | ``AUTHENTICATION_FAILURE``     |
| ``PermissionDeniedError``  |  403 | ``AUTHORIZATION_FAILURE``      |
| ``NotFoundError``          |  404 | ``MODEL_NOT_FOUND``            |
| ``BadRequestError``        |  400 | ``INVALID_REQUEST``            |
| ``UnprocessableEntityError``| 422 | ``UNSUPPORTED_REQUEST``        |
| ``ConflictError``          |  409 | ``INVALID_REQUEST``            |
| ``RequestTooLargeError``   |  413 | ``REQUEST_TOO_LARGE``          |
| ``RateLimitError``         |  429 | ``RATE_LIMITED``               |
| ``OverloadedError``        |  529 | ``PROVIDER_OVERLOADED``        |
| ``InternalServerError``    |  500 | ``TRANSIENT_PROVIDER_FAILURE`` |
| ``APITimeoutError`` (connect)|  - | ``CONNECTION_TIMEOUT``         |
| ``APITimeoutError`` (read/unknown)| - | ``READ_TIMEOUT``          |
| ``APIConnectionError``     |    - | ``CONNECTION_FAILURE``         |
| any other ``APIStatusError``| any | ``UNKNOWN_PROVIDER_ERROR``     |
| anything else              |    - | ``UNKNOWN_PROVIDER_ERROR``     |

``APITimeoutError`` is a *subclass* of ``APIConnectionError`` in the
installed SDK version, so it is checked first. Only ``RATE_LIMITED``,
``PROVIDER_OVERLOADED``, ``TRANSIENT_PROVIDER_FAILURE``,
``CONNECTION_FAILURE``, ``CONNECTION_TIMEOUT``, and ``READ_TIMEOUT``
are retryable (see ``app.application.policies.llm_retry_policy`` for
the authoritative classification) - every other category, including
``UNKNOWN_PROVIDER_ERROR``, is treated conservatively as non-retryable.
"""

from __future__ import annotations

import anthropic
import httpx

from app.application.models.llm_invocation import (
    LLMProviderErrorCategory,
    LLMProviderErrorDetails,
    LLMTimeoutPhase,
)

_STATUS_CATEGORY_BY_EXCEPTION_TYPE: dict[type[Exception], LLMProviderErrorCategory] = {
    anthropic.AuthenticationError: LLMProviderErrorCategory.AUTHENTICATION_FAILURE,
    anthropic.PermissionDeniedError: LLMProviderErrorCategory.AUTHORIZATION_FAILURE,
    anthropic.NotFoundError: LLMProviderErrorCategory.MODEL_NOT_FOUND,
    anthropic.BadRequestError: LLMProviderErrorCategory.INVALID_REQUEST,
    anthropic.UnprocessableEntityError: LLMProviderErrorCategory.UNSUPPORTED_REQUEST,
    anthropic.ConflictError: LLMProviderErrorCategory.INVALID_REQUEST,
    anthropic.RequestTooLargeError: LLMProviderErrorCategory.REQUEST_TOO_LARGE,
    anthropic.RateLimitError: LLMProviderErrorCategory.RATE_LIMITED,
    anthropic.OverloadedError: LLMProviderErrorCategory.PROVIDER_OVERLOADED,
    anthropic.InternalServerError: LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
}


def _safe_message(exc: Exception) -> str:
    """A short, filtered summary - never the raw exception repr (which
    could embed request/response detail), never a stack trace."""

    return f"{type(exc).__name__}: {str(exc)[:300]}"


def _retry_after_seconds(exc: anthropic.APIStatusError) -> float | None:
    header_value = exc.response.headers.get("retry-after")
    if not header_value:
        return None

    try:
        return float(header_value)
    except ValueError:
        return None


def _timeout_phase(exc: anthropic.APITimeoutError) -> LLMTimeoutPhase:
    cause = exc.__cause__
    if isinstance(cause, httpx.ConnectTimeout):
        return LLMTimeoutPhase.CONNECTION
    if isinstance(cause, httpx.ReadTimeout):
        return LLMTimeoutPhase.READ

    return LLMTimeoutPhase.UNKNOWN


def map_anthropic_exception_to_provider_error(
    exc: Exception,
) -> tuple[LLMProviderErrorCategory, str, LLMProviderErrorDetails]:
    """Returns ``(category, message, details)`` - assembled by the
    caller into an ``LLMProviderError``. Kept as a plain tuple return
    rather than constructing the dataclass here, so callers that only
    need the category (e.g. a future health check) are not forced to
    build the full details object."""

    if isinstance(exc, anthropic.APITimeoutError):
        phase = _timeout_phase(exc)
        category = (
            LLMProviderErrorCategory.CONNECTION_TIMEOUT
            if phase is LLMTimeoutPhase.CONNECTION
            else LLMProviderErrorCategory.READ_TIMEOUT
        )
        return (
            category,
            _safe_message(exc),
            LLMProviderErrorDetails(
                http_status=None,
                provider_error_type="timeout",
                provider_request_id=None,
                retry_after_seconds=None,
                timeout_phase=phase,
            ),
        )

    if isinstance(exc, anthropic.APIConnectionError):
        return (
            LLMProviderErrorCategory.CONNECTION_FAILURE,
            _safe_message(exc),
            LLMProviderErrorDetails(
                http_status=None,
                provider_error_type="connection_error",
                provider_request_id=None,
                retry_after_seconds=None,
                timeout_phase=None,
            ),
        )

    if isinstance(exc, anthropic.APIStatusError):
        category = _STATUS_CATEGORY_BY_EXCEPTION_TYPE.get(
            type(exc), LLMProviderErrorCategory.UNKNOWN_PROVIDER_ERROR
        )
        return (
            category,
            _safe_message(exc),
            LLMProviderErrorDetails(
                http_status=exc.status_code,
                provider_error_type=exc.type,
                provider_request_id=exc.request_id,
                retry_after_seconds=_retry_after_seconds(exc),
                timeout_phase=None,
            ),
        )

    return (
        LLMProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
        _safe_message(exc),
        LLMProviderErrorDetails(
            http_status=None,
            provider_error_type=type(exc).__name__,
            provider_request_id=None,
            retry_after_seconds=None,
            timeout_phase=None,
        ),
    )
