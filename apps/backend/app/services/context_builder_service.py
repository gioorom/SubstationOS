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
from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
    ComparisonContextStatistics,
    ComparisonOperandContext,
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


def build_comparison_context_package(
    *,
    project_id: int,
    left_designation: str,
    left_candidates: KnowledgeCandidateCollection,
    right_designation: str,
    right_candidates: KnowledgeCandidateCollection,
    left_retrieval_policy_version: str | None = None,
    right_retrieval_policy_version: str | None = None,
    now: datetime,
) -> ComparisonContextPackage:
    """
    Assembles the two-sided context a comparison needs, by calling the
    **existing** builder once per side.

    No new assembly logic exists here: each side is an ordinary
    ``ContextPackage``, built by the same code, under the same budget
    policy, with its own coverage and warnings. The only thing this
    function adds is the labelled pairing - and it never merges, unions
    or diffs the two sides, because computing a difference is the
    comparison's answer rather than its input.
    """

    left = build_context_package(
        project_id=project_id,
        candidates=left_candidates,
        retrieval_policy_version=left_retrieval_policy_version,
        now=now,
    ).package
    right = build_context_package(
        project_id=project_id,
        candidates=right_candidates,
        retrieval_policy_version=right_retrieval_policy_version,
        now=now,
    ).package

    left_operand = ComparisonOperandContext(
        designation=left_designation, package=left
    )
    right_operand = ComparisonOperandContext(
        designation=right_designation, package=right
    )

    return ComparisonContextPackage(
        project_id=project_id,
        left=left_operand,
        right=right_operand,
        statistics=ComparisonContextStatistics(
            left_evidence_count=left_operand.evidence_count,
            right_evidence_count=right_operand.evidence_count,
            both_sides_have_evidence=(
                left_operand.has_evidence and right_operand.has_evidence
            ),
        ),
        assembled_at=now,
    )
