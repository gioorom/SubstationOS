"""
Application service for Governed Context Assembly (EPIC 31.3).

Validates a request through ``ContextBuildRequestFactory``, delegates
assembly to the pure domain pipeline
(``context_package_assembler.assemble_context_package``), and returns a
``ContextBuilderResult``.

**Performs no persistence and no I/O of any kind.** Context Assembly's
entire input is the governed retrieval results the caller supplies: it
never reads the governed graph, never issues a query of its own, and
never calls an AI provider. That is not only a layering preference - it
is what makes the security boundary hold. Governed Structured Retrieval
applied the project and document scope and the caller's authorization;
a Context Assembly that could read for itself would be able to widen
either, and nothing downstream would notice.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.budget_policy import (
    DEFAULT_MAX_ASSETS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_METADATA_ENTRIES,
    DEFAULT_MAX_QUANTITIES,
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
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalResult,
)


def build_context_package(
    *,
    project_id: int,
    results: tuple[GovernedRetrievalResult, ...],
    max_items: int = DEFAULT_MAX_ITEMS,
    max_assets: int = DEFAULT_MAX_ASSETS,
    max_quantities: int = DEFAULT_MAX_QUANTITIES,
    max_relationships: int = DEFAULT_MAX_RELATIONSHIPS,
    max_metadata_entries: int = DEFAULT_MAX_METADATA_ENTRIES,
    max_warnings: int = DEFAULT_MAX_WARNINGS,
    metadata_entries: tuple[tuple[str, str], ...] = (),
    now: datetime,
) -> ContextBuilderResult:
    request = ContextBuildRequestFactory.create(
        project_id=project_id,
        results=results,
        max_items=max_items,
        max_assets=max_assets,
        max_quantities=max_quantities,
        max_relationships=max_relationships,
        max_metadata_entries=max_metadata_entries,
        max_warnings=max_warnings,
        metadata_entries=metadata_entries,
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
    left_results: tuple[GovernedRetrievalResult, ...],
    right_designation: str,
    right_results: tuple[GovernedRetrievalResult, ...],
    now: datetime,
) -> ComparisonContextPackage:
    """
    Assembles the two-sided context a comparison needs, by calling the
    **same** governed assembly once per side.

    No new assembly logic exists here: each side is an ordinary
    ``ContextPackage``, built by the same code, under the same budget
    policy, with its own coverage, its own ambiguity and its own
    warnings. The only thing this function adds is the labelled pairing -
    and it never merges, unions or diffs the two sides, because
    computing a difference is the comparison's answer rather than its
    input.

    Each side keeps its **own** governed results, so an ambiguous left
    subject cannot make the right one look ambiguous, and neither side's
    provenance can be attributed to the other.
    """

    left = build_context_package(
        project_id=project_id, results=left_results, now=now
    ).package
    right = build_context_package(
        project_id=project_id, results=right_results, now=now
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
