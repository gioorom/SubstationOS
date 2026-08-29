from __future__ import annotations

from datetime import datetime

import pytest

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationStatus,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMUsage,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    ProjectIdMismatchError,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseStatus,
    EngineeringSourceFinishReason,
)
from app.services import (
    context_builder_service,
    engineering_response_service,
    prompt_builder_service,
)

from tests._governed_context import designation_result
from app.services.engineering_response_service import (
    _source_envelope_from_llm_envelope,
)

PROJECT_ID = 31
NOW = datetime(2026, 1, 1, 13, 0, 0)


def _packages(project_id: int = PROJECT_ID):
    context_result = context_builder_service.build_context_package(
        project_id=project_id,
        results=(designation_result("TR1", ()),),
        now=NOW,
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    return context_result.package, prompt_result.package


def _envelope(prompt_package, **overrides) -> LLMResponseEnvelope:
    defaults = dict(
        provider_id="anthropic",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="The direct answer.",
                provider_block_type=None,
                annotations=(),
            ),
        ),
        finish_reason=LLMFinishReason.COMPLETED,
        usage=LLMUsage(
            input_tokens=42,
            output_tokens=7,
            total_tokens=49,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        ),
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id="corr-service-1",
        provider_request_id="prov-req-1",
        started_at=NOW,
        completed_at=NOW,
        latency_seconds=0.25,
        attempt_count=1,
        attempts=(),
        warnings=(),
        metadata=LLMResponseMetadata(
            runtime_version="1.0",
            adapter_version="1.0",
            request_preparation_policy_version="1.0",
            prompt_package_version=prompt_package.version.package_version,
            context_assembly_version=prompt_package.metadata.context_assembly_version,
            prompt_builder_version=prompt_package.version.prompt_builder_version,
        ),
    )
    defaults.update(overrides)
    return LLMResponseEnvelope(**defaults)


def test_build_engineering_response_translates_a_real_llm_response_envelope() -> (
    None
):
    context_package, prompt_package = _packages()
    envelope = _envelope(prompt_package)

    result = engineering_response_service.build_engineering_response(
        project_id=PROJECT_ID,
        context_package=context_package,
        prompt_package=prompt_package,
        llm_response_envelope=envelope,
        now=NOW,
    )

    assert result.project_id == PROJECT_ID
    assert result.response.direct_answer.body == ("The direct answer.",)
    assert result.response.metadata.provider_id == "anthropic"
    assert result.response.metadata.request_correlation_id == "corr-service-1"
    assert result.validation.valid is True


def test_project_id_mismatch_against_the_context_package_is_rejected() -> None:
    context_package, prompt_package = _packages(project_id=PROJECT_ID)
    envelope = _envelope(prompt_package)

    with pytest.raises(ProjectIdMismatchError):
        engineering_response_service.build_engineering_response(
            project_id=PROJECT_ID + 1,
            context_package=context_package,
            prompt_package=prompt_package,
            llm_response_envelope=envelope,
            now=NOW,
        )


def test_source_translation_preserves_content_finish_reason_and_usage() -> None:
    _, prompt_package = _packages()
    envelope = _envelope(
        prompt_package,
        finish_reason=LLMFinishReason.MAXIMUM_OUTPUT_REACHED,
        warnings=("a runtime-level warning",),
    )

    source = _source_envelope_from_llm_envelope(envelope)

    assert source.finish_reason is EngineeringSourceFinishReason.MAXIMUM_OUTPUT_REACHED
    assert source.warnings == ("a runtime-level warning",)
    assert source.input_tokens == 42
    assert source.output_tokens == 7
    assert len(source.content) == 1
    assert source.content[0].is_supported_text is True
    assert source.content[0].text == "The direct answer."


def test_source_translation_restates_unsupported_content_type_correctly() -> None:
    _, prompt_package = _packages()
    envelope = _envelope(
        prompt_package,
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.UNSUPPORTED,
                text="",
                provider_block_type="thinking",
                annotations=(),
            ),
        ),
    )

    source = _source_envelope_from_llm_envelope(envelope)

    assert source.content[0].is_supported_text is False
    assert source.content[0].provider_block_type == "thinking"


def test_the_service_never_exposes_engineering_response_status_as_a_provider_status() -> (
    None
):
    """A quick, explicit reminder-level check that this service produces
    an engineering-native status, not a copy of the provider's own
    invocation status."""

    context_package, prompt_package = _packages()
    envelope = _envelope(prompt_package)

    result = engineering_response_service.build_engineering_response(
        project_id=PROJECT_ID,
        context_package=context_package,
        prompt_package=prompt_package,
        llm_response_envelope=envelope,
        now=NOW,
    )

    assert isinstance(result.response.status, EngineeringResponseStatus)
