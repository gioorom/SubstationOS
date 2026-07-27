"""
Warnings (Milestone 14's pipeline stage of the same name). Generates
every structured, machine-readable ``ContextWarning`` in a fixed,
documented priority order - budget exceeded, missing provenance,
missing attributes, missing relationships, partial coverage, candidate
discarded - then truncates the result to the configured ``max_warnings``
budget, reporting that truncation as its own ``BudgetConsumption``.
Never invents a warning about data Context Builder cannot observe; each
warning is derived strictly from the ``SelectionOutcome``/
``ContextAssemblyResult``/``CoverageReport`` already computed earlier in
the pipeline. O(n) in the number of selected/discarded candidates.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    ContextAssemblyResult,
    ContextWarning,
    ContextWarningCategory,
    CoverageCategory,
    CoverageReport,
    RetrievalSummary,
    SelectionOutcome,
)


def _budget_exceeded_warnings(
    consumption: tuple[BudgetConsumption, ...],
) -> list[ContextWarning]:
    return [
        ContextWarning(
            category=ContextWarningCategory.BUDGET_EXCEEDED,
            message=(
                f"Budget exceeded for '{entry.category.value}': "
                f"{entry.discarded} of {entry.requested} discarded "
                f"(limit {entry.limit})."
            ),
        )
        for entry in consumption
        if entry.discarded > 0
    ]


def _missing_provenance_warnings(
    assembly: ContextAssemblyResult,
) -> list[ContextWarning]:
    # A missing GraphExecution id is a real, honestly-observable gap
    # (structured_retrieval.md's Provenance section: this field is
    # "sometimes absent"), unlike source_fact_ids, which is always
    # empty this milestone (a known, tracked technical debt item) and
    # so would fire for every candidate, never a useful signal.
    return [
        ContextWarning(
            category=ContextWarningCategory.MISSING_PROVENANCE,
            message=(
                f"Candidate '{candidate.candidate_id}' carries no graph "
                "execution provenance."
            ),
            candidate_id=candidate.candidate_id,
        )
        for candidate in assembly.selected_candidates
        if not candidate.graph_execution_ids
    ]


def _missing_attributes_and_relationships_warnings(
    assembly: ContextAssemblyResult, summary: RetrievalSummary
) -> list[ContextWarning]:
    """
    Fires only when knowledge of that kind actually existed in the
    retrieved collection but none survived selection - never for a
    kind that was never offered to Context Builder in the first place
    (an empty or narrowly-scoped ``KnowledgeCandidateCollection`` is not
    a "gap," it is simply what was asked for).
    """

    warnings: list[ContextWarning] = []

    if not assembly.selected_attributes and summary.retrieved_attribute_count:
        warnings.append(
            ContextWarning(
                category=ContextWarningCategory.MISSING_ATTRIBUTES,
                message=(
                    f"{summary.retrieved_attribute_count} attribute "
                    "candidate(s) were retrieved, but none were selected "
                    "into this context package."
                ),
            )
        )

    if (
        not assembly.selected_relationships
        and summary.retrieved_relationship_count
    ):
        warnings.append(
            ContextWarning(
                category=ContextWarningCategory.MISSING_RELATIONSHIPS,
                message=(
                    f"{summary.retrieved_relationship_count} relationship "
                    "candidate(s) were retrieved, but none were selected "
                    "into this context package."
                ),
            )
        )

    return warnings


def _partial_coverage_warnings(
    coverage: CoverageReport,
) -> list[ContextWarning]:
    incomplete = [
        metric.category.value
        for metric in coverage.metrics
        if metric.category is not CoverageCategory.CONTEXT_COMPLETENESS
        and metric.ratio < 1.0
    ]

    if not incomplete:
        return []

    return [
        ContextWarning(
            category=ContextWarningCategory.PARTIAL_COVERAGE,
            message=f"Partial coverage in: {', '.join(incomplete)}.",
        )
    ]


def _candidate_discarded_warnings(
    selection: SelectionOutcome,
) -> list[ContextWarning]:
    return [
        ContextWarning(
            category=ContextWarningCategory.CANDIDATE_DISCARDED,
            message=(
                f"Candidate '{discarded.candidate.candidate_id}' was "
                f"discarded ({discarded.reason.value} budget)."
            ),
            candidate_id=discarded.candidate.candidate_id,
        )
        for discarded in selection.discarded
    ]


def generate_warnings(
    *,
    selection: SelectionOutcome,
    assembly: ContextAssemblyResult,
    coverage: CoverageReport,
    summary: RetrievalSummary,
    consumption_so_far: tuple[BudgetConsumption, ...],
    max_warnings: int,
) -> tuple[tuple[ContextWarning, ...], BudgetConsumption]:
    warnings: list[ContextWarning] = []
    warnings.extend(_budget_exceeded_warnings(consumption_so_far))
    warnings.extend(_missing_provenance_warnings(assembly))
    warnings.extend(
        _missing_attributes_and_relationships_warnings(assembly, summary)
    )
    warnings.extend(_partial_coverage_warnings(coverage))
    warnings.extend(_candidate_discarded_warnings(selection))

    accepted = tuple(warnings[:max_warnings])
    consumption = BudgetConsumption(
        category=BudgetCategory.WARNINGS,
        requested=len(warnings),
        accepted=len(accepted),
        discarded=len(warnings) - len(accepted),
        limit=max_warnings,
        utilization=(
            0.0 if max_warnings == 0 else len(accepted) / max_warnings
        ),
    )

    return accepted, consumption
