"""
Application service for Context Builder (EPIC 4, Milestone 14).
Validates a package request through ``ContextBuildRequestFactory``,
delegates assembly to the pure domain pipeline
(``context_package_assembler.assemble_context_package``), and returns a
``ContextBuilderResult``. Performs no persistence and no I/O of any
kind - Context Builder's entire input is the ``KnowledgeCandidateCollection``
the caller supplies; it never calls Graph Query, Structured Retrieval,
or an AI provider itself.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.budget_policy import (
    DEFAULT_MAX_ATTRIBUTES,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_ENTITIES,
    DEFAULT_MAX_METADATA_ENTRIES,
    DEFAULT_MAX_RELATIONSHIPS,
    DEFAULT_MAX_WARNINGS,
)
from app.domain.context_builder.context_builder_factory import (
    ContextBuildRequestFactory,
)
from app.domain.context_builder.context_builder_models import (
    ContextBuilderResult,
)
from app.domain.context_builder.context_package_assembler import (
    assemble_context_package,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)


def build_context_package(
    *,
    project_id: int,
    candidates: KnowledgeCandidateCollection,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    max_entities: int = DEFAULT_MAX_ENTITIES,
    max_relationships: int = DEFAULT_MAX_RELATIONSHIPS,
    max_attributes: int = DEFAULT_MAX_ATTRIBUTES,
    max_metadata_entries: int = DEFAULT_MAX_METADATA_ENTRIES,
    max_warnings: int = DEFAULT_MAX_WARNINGS,
    metadata_entries: tuple[tuple[str, str], ...] = (),
    retrieval_policy_version: str | None = None,
    now: datetime,
) -> ContextBuilderResult:
    request = ContextBuildRequestFactory.create(
        project_id=project_id,
        candidates=candidates,
        max_candidates=max_candidates,
        max_entities=max_entities,
        max_relationships=max_relationships,
        max_attributes=max_attributes,
        max_metadata_entries=max_metadata_entries,
        max_warnings=max_warnings,
        metadata_entries=metadata_entries,
        retrieval_policy_version=retrieval_policy_version,
    )

    package = assemble_context_package(request, now=now)

    return ContextBuilderResult(
        project_id=project_id,
        configuration=request.configuration,
        package=package,
    )
