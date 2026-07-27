"""
Orchestrates the full Context Builder pipeline (Milestone 14):

    KnowledgeCandidateCollection
            |
       Selection            (candidate_selection.py)
            |
       Aggregation          (context_aggregation.py)
            |
       Coverage Analysis    (coverage_analysis.py)
            |
       Budget Enforcement   (budget_enforcement.py, context_metadata.py,
            |                context_warnings.py)
       ContextPackage

Pure and deterministic: given the same ``ContextBuildRequest`` and the
same ``now``, always produces the same ``ContextPackage``, including
every warning and every budget figure. ``now`` is accepted as an
explicit parameter rather than read from the wall clock, so this
function itself performs no I/O and no non-deterministic side effect
(CLAUDE.md SS15, "Pure domain").

Overall complexity is O(n log n) in the number of candidates in the
incoming collection - dominated entirely by Selection's ranking sort;
every later stage (Aggregation, Coverage Analysis, metadata/warning
truncation, Statistics) is a single O(n) or O(1) pass over
already-materialized results, never a second scan of the raw candidate
collection.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.budget_enforcement import build_budget
from app.domain.context_builder.candidate_selection import select_candidates
from app.domain.context_builder.context_aggregation import aggregate
from app.domain.context_builder.context_builder_models import (
    ContextBuildRequest,
    ContextPackage,
    RetrievalSummary,
)
from app.domain.context_builder.context_metadata import build_metadata
from app.domain.context_builder.context_statistics import build_statistics
from app.domain.context_builder.context_warnings import generate_warnings
from app.domain.context_builder.coverage_analysis import analyze
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
    KnowledgeCandidateKind,
)


def _summarize_retrieval(
    collection: KnowledgeCandidateCollection,
) -> RetrievalSummary:
    return RetrievalSummary(
        retrieved_candidate_count=len(collection.candidates),
        total_before_limit=collection.total_before_limit,
        applied_limit=collection.applied_limit,
        retrieved_entity_count=sum(
            1
            for candidate in collection.candidates
            if candidate.candidate_kind is KnowledgeCandidateKind.ENTITY
        ),
        retrieved_relationship_count=sum(
            1
            for candidate in collection.candidates
            if candidate.candidate_kind
            is KnowledgeCandidateKind.RELATIONSHIP
        ),
        retrieved_attribute_count=sum(
            1
            for candidate in collection.candidates
            if candidate.candidate_kind is KnowledgeCandidateKind.ATTRIBUTE
        ),
    )


def assemble_context_package(
    request: ContextBuildRequest, *, now: datetime
) -> ContextPackage:
    summary = _summarize_retrieval(request.candidates)

    selection = select_candidates(
        request.candidates.candidates,
        request.configuration.budget_policy,
    )
    assembly = aggregate(selection.selected)
    coverage = analyze(summary, assembly)

    metadata, metadata_consumption = build_metadata(
        configuration=request.configuration,
        retrieval_policy_version=request.retrieval_policy_version,
        metadata_entries=request.metadata_entries,
        now=now,
    )

    warnings, warnings_consumption = generate_warnings(
        selection=selection,
        assembly=assembly,
        coverage=coverage,
        summary=summary,
        consumption_so_far=selection.consumption,
        max_warnings=request.configuration.budget_policy.max_warnings,
    )

    budget = build_budget(
        request.configuration.budget_policy,
        selection.consumption + (metadata_consumption, warnings_consumption),
    )

    statistics = build_statistics(
        assembly=assembly,
        selection=selection,
        coverage=coverage,
        budget=budget,
    )

    return ContextPackage(
        project_id=request.project_id,
        retrieval_summary=summary,
        selected_entities=assembly.selected_entities,
        selected_relationships=assembly.selected_relationships,
        selected_attributes=assembly.selected_attributes,
        selected_candidates=assembly.selected_candidates,
        coverage=coverage,
        statistics=statistics,
        warnings=warnings,
        budget=budget,
        metadata=metadata,
    )
