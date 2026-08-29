"""
Statistics: one summary of what assembly decided.

Summarizes the already-computed assembly, selection, coverage and budget
results into one ``ContextStatistics`` value object - never persistence
statistics, and never a recomputation of anything an earlier stage
already decided. O(1) given the already-materialized inputs.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    ContextAssemblyResult,
    ContextBudget,
    ContextStatistics,
    CoverageReport,
    SelectionOutcome,
)


def build_statistics(
    *,
    assembly: ContextAssemblyResult,
    selection: SelectionOutcome,
    coverage: CoverageReport,
    budget: ContextBudget,
) -> ContextStatistics:
    return ContextStatistics(
        selected_item_count=len(assembly.selected_items),
        discarded_item_count=len(selection.discarded),
        asset_count=len(assembly.selected_assets),
        quantity_count=len(assembly.selected_quantities),
        relationship_count=len(assembly.selected_relationships),
        coverage_summary=coverage,
        budget_summary=budget,
    )
