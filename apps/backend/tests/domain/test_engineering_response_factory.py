from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_response.engineering_response_exceptions import (
    InvalidProjectIdError,
    ProjectIdMismatchError,
)
from app.domain.engineering_response.engineering_response_factory import (
    EngineeringResponseBuildRequestFactory,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseSourceEnvelope,
    EngineeringSourceFinishReason,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.services import context_builder_service, prompt_builder_service

PROJECT_ID = 11
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _empty_collection() -> KnowledgeCandidateCollection:
    return KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )


def _packages(project_id: int = PROJECT_ID):
    context_result = context_builder_service.build_context_package(
        project_id=project_id, candidates=_empty_collection(), now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    return context_result.package, prompt_result.package


def _source() -> EngineeringResponseSourceEnvelope:
    return EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(),
        finish_reason=EngineeringSourceFinishReason.COMPLETED,
        request_correlation_id="corr-1",
        attempt_count=1,
        warnings=(),
        input_tokens=None,
        output_tokens=None,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )


def test_a_well_formed_request_builds_successfully() -> None:
    context_package, prompt_package = _packages()

    request = EngineeringResponseBuildRequestFactory.create(
        project_id=PROJECT_ID,
        context_package=context_package,
        prompt_package=prompt_package,
        source=_source(),
    )

    assert request.project_id == PROJECT_ID
    assert request.context_package is context_package
    assert request.prompt_package is prompt_package
    assert request.configuration.engineering_response_version == "1.0"
    assert request.configuration.response_policy.version == "1.0"


def test_a_non_positive_project_id_is_rejected() -> None:
    context_package, prompt_package = _packages()

    with pytest.raises(InvalidProjectIdError):
        EngineeringResponseBuildRequestFactory.create(
            project_id=0,
            context_package=context_package,
            prompt_package=prompt_package,
            source=_source(),
        )


def test_a_project_id_disagreeing_with_the_context_package_is_rejected() -> None:
    context_package, prompt_package = _packages(project_id=PROJECT_ID)

    with pytest.raises(ProjectIdMismatchError):
        EngineeringResponseBuildRequestFactory.create(
            project_id=PROJECT_ID + 1,
            context_package=context_package,
            prompt_package=prompt_package,
            source=_source(),
        )


def test_a_project_id_disagreeing_with_the_prompt_package_is_rejected() -> None:
    context_package, _ = _packages(project_id=PROJECT_ID)
    _, other_prompt_package = _packages(project_id=PROJECT_ID + 1)

    with pytest.raises(ProjectIdMismatchError):
        EngineeringResponseBuildRequestFactory.create(
            project_id=PROJECT_ID,
            context_package=context_package,
            prompt_package=other_prompt_package,
            source=_source(),
        )
