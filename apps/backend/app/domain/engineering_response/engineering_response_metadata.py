"""
Builds ``EngineeringResponseMetadata`` and ``EngineeringResponseVersion``.
``now`` is always supplied by the caller (the service layer) rather
than read from the wall clock here, keeping building deterministic and
reproducible (CLAUDE.md SS16) given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseBuildRequest,
    EngineeringResponseMetadata,
    EngineeringResponseVersion,
)
from app.domain.engineering_response.engineering_response_policy import (
    RESPONSE_PACKAGE_VERSION,
)


def build_metadata(
    request: EngineeringResponseBuildRequest, *, now: datetime
) -> EngineeringResponseMetadata:
    source = request.source
    prompt_package = request.prompt_package

    return EngineeringResponseMetadata(
        engineering_response_version=(
            request.configuration.engineering_response_version
        ),
        response_policy_version=request.configuration.response_policy.version,
        assembled_at=now,
        project_id=request.project_id,
        provider_id=source.provider_id,
        configured_model_identifier=source.configured_model_identifier,
        returned_model_identifier=source.returned_model_identifier,
        request_correlation_id=source.request_correlation_id,
        prompt_package_version=prompt_package.version.package_version,
        context_builder_version=prompt_package.metadata.context_builder_version,
        prompt_builder_version=prompt_package.version.prompt_builder_version,
        package_version=RESPONSE_PACKAGE_VERSION,
    )


def build_version(
    request: EngineeringResponseBuildRequest,
) -> EngineeringResponseVersion:
    source = request.source
    prompt_package = request.prompt_package

    return EngineeringResponseVersion(
        engineering_response_version=(
            request.configuration.engineering_response_version
        ),
        response_policy_version=request.configuration.response_policy.version,
        prompt_builder_version=prompt_package.version.prompt_builder_version,
        context_builder_version=prompt_package.metadata.context_builder_version,
        request_preparation_policy_version=(
            source.request_preparation_policy_version
        ),
        runtime_version=source.runtime_version,
        package_version=RESPONSE_PACKAGE_VERSION,
    )
