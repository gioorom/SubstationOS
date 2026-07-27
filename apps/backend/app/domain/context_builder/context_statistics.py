"""
Statistics (Milestone 14's pipeline stage of the same name). Summarizes
the already-computed assembly, selection, coverage, and budget results
into one ``ContextStatistics`` value object - never persistence
statistics, never a recomputation of anything an earlier stage already
decided. O(1) given the already-materialized inputs.
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
        selected_candidate_count=len(assembly.selected_candidates),
        discarded_candidate_count=len(selection.discarded),
        entity_count=len(assembly.selected_entities),
        relationship_count=len(assembly.selected_relationships),
        attribute_count=len(assembly.selected_attributes),
        coverage_summary=coverage,
        budget_summary=budget,
    )
