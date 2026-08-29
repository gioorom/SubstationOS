"""
Coverage Analysis: how much of the retrieved governed knowledge entered
the package.

Selection completeness, **never engineering confidence** and never
certainty about the underlying knowledge. Every ratio is
``selected_count / available_count``, or ``1.0`` when nothing was
available to begin with (vacuously complete - there is nothing missing).
A single O(1) pass over already-computed counts; no I/O.

A high ratio means "little was dropped on the way into this context". It
says nothing about whether the governed knowledge answers the engineer's
question, and a reader that treated it as a quality signal would be
reading a budget report as an engineering judgement.
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
    asset_metric = _metric(
        CoverageCategory.ASSET_COVERAGE,
        len(assembly.selected_assets),
        summary.retrieved_asset_count,
    )
    quantity_metric = _metric(
        CoverageCategory.QUANTITY_COVERAGE,
        len(assembly.selected_quantities),
        summary.retrieved_quantity_count,
    )
    relationship_metric = _metric(
        CoverageCategory.RELATIONSHIP_COVERAGE,
        len(assembly.selected_relationships),
        summary.retrieved_relationship_count,
    )
    utilization_metric = _metric(
        CoverageCategory.ITEM_UTILIZATION,
        len(assembly.selected_items),
        summary.retrieved_item_count,
    )

    base_metrics = (
        asset_metric,
        quantity_metric,
        relationship_metric,
        utilization_metric,
    )
    overall_completeness = sum(metric.ratio for metric in base_metrics) / len(
        base_metrics
    )

    completeness_metric = CoverageMetric(
        category=CoverageCategory.CONTEXT_COMPLETENESS,
        selected_count=len(assembly.selected_items),
        available_count=summary.retrieved_item_count,
        ratio=overall_completeness,
    )

    return CoverageReport(
        metrics=base_metrics + (completeness_metric,),
        overall_completeness=overall_completeness,
    )
