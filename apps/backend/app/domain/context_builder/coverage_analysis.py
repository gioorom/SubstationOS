"""
Coverage Analysis (Milestone 14's pipeline stage of the same name).
Explains how much of the retrieved knowledge entered the package -
selection completeness, never engineering confidence or certainty about
the underlying facts (Milestone 14's explicit "do not invent confidence
percentages" rule). Every ratio is ``selected_count / available_count``,
or ``1.0`` when nothing was available to begin with (vacuously
complete - there is nothing missing). A single O(1) pass over the four
already-computed counts; no I/O.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    ContextAssemblyResult,
    CoverageCategory,
    CoverageMetric,
    CoverageReport,
    RetrievalSummary,
)


def _ratio(selected_count: int, available_count: int) -> float:
    return 1.0 if available_count == 0 else selected_count / available_count


def _metric(
    category: CoverageCategory, selected_count: int, available_count: int
) -> CoverageMetric:
    return CoverageMetric(
        category=category,
        selected_count=selected_count,
        available_count=available_count,
        ratio=_ratio(selected_count, available_count),
    )


def analyze(
    summary: RetrievalSummary, assembly: ContextAssemblyResult
) -> CoverageReport:
    entity_metric = _metric(
        CoverageCategory.ENTITY_COVERAGE,
        len(assembly.selected_entities),
        summary.retrieved_entity_count,
    )
    relationship_metric = _metric(
        CoverageCategory.RELATIONSHIP_COVERAGE,
        len(assembly.selected_relationships),
        summary.retrieved_relationship_count,
    )
    attribute_metric = _metric(
        CoverageCategory.ATTRIBUTE_COVERAGE,
        len(assembly.selected_attributes),
        summary.retrieved_attribute_count,
    )
    utilization_metric = _metric(
        CoverageCategory.CANDIDATE_UTILIZATION,
        len(assembly.selected_candidates),
        summary.retrieved_candidate_count,
    )

    base_metrics = (
        entity_metric,
        relationship_metric,
        attribute_metric,
        utilization_metric,
    )
    overall_completeness = sum(metric.ratio for metric in base_metrics) / len(
        base_metrics
    )

    completeness_metric = CoverageMetric(
        category=CoverageCategory.CONTEXT_COMPLETENESS,
        selected_count=len(assembly.selected_candidates),
        available_count=summary.retrieved_candidate_count,
        ratio=overall_completeness,
    )

    return CoverageReport(
        metrics=base_metrics + (completeness_metric,),
        overall_completeness=overall_completeness,
    )
