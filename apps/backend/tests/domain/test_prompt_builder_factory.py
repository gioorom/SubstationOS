from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.prompt_builder.prompt_builder_exceptions import (
    InvalidProjectIdError,
    ProjectIdMismatchError,
)
from app.domain.prompt_builder.prompt_builder_factory import (
    PromptBuildRequestFactory,
)
from app.services import context_builder_service
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)

NOW = datetime(2026, 1, 1, 10, 0, 0)


def _context_package(project_id: int = 1):
    collection = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    result = context_builder_service.build_context_package(
        project_id=project_id, candidates=collection, now=NOW
    )
    return result.package


def test_project_id_must_be_positive():
    with pytest.raises(InvalidProjectIdError):
        PromptBuildRequestFactory.create(
            project_id=0, context_package=_context_package(project_id=1)
        )


def test_project_id_must_match_the_context_package_project_id():
    with pytest.raises(ProjectIdMismatchError):
        PromptBuildRequestFactory.create(
            project_id=2, context_package=_context_package(project_id=1)
        )


def test_matching_project_id_is_accepted():
    request = PromptBuildRequestFactory.create(
        project_id=1, context_package=_context_package(project_id=1)
    )
    assert request.project_id == 1


def test_configuration_carries_versioned_policy():
    request = PromptBuildRequestFactory.create(
        project_id=1, context_package=_context_package(project_id=1)
    )
    assert request.configuration.prompt_builder_version == "1.0"
    assert request.configuration.composition_policy.version == "1.0"
