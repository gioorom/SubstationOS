"""
Orchestrates the full Governed Context Assembly pipeline (EPIC 31.3):

    tuple[GovernedRetrievalResult, ...]
            |
       Ingestion            (this module - results become ContextItems)
            |
       Selection            (item_selection.py)
            |
       Aggregation          (context_aggregation.py)
            |
       Coverage Analysis    (coverage_analysis.py)
            |
       Budget Enforcement   (budget_enforcement.py, context_metadata.py,
            |                context_warnings.py)
       ContextPackage

Pure and deterministic: given the same governed results and the same
``now``, always produces the same ``ContextPackage`` - the same items,
in the same order, with the same warnings and the same budget figures.
``now`` is an explicit parameter rather than a wall-clock read, so this
function performs no I/O and no non-deterministic side effect
(CLAUDE.md SS15, "Pure domain"), and nothing in the package's *content*
derives from it.

Overall complexity is O(n log n) in the number of governed items -
dominated entirely by Selection's ranking sort; every later stage is a
single O(n) or O(1) pass over already-materialized results.

---

## Ingestion: what turns a governed result into a context item

Each ``GovernedRetrievalItem`` is wrapped, untouched, in a
``ContextItem`` alongside a ``ContextItemOrigin`` recording the query
that produced it. Nothing is copied out of the governed item and nothing
is computed from it:

- **provenance** travels inside the governed item, where it is
  structurally mandatory;
- **ambiguity** travels in the origin, per query, so a truncated page
  can never read as one certain answer;
- **order** is the governed sort key, so this stage introduces no
  ranking of its own.

Items are deduplicated by governed identity across queries, because two
governed queries may legitimately answer with the same governed object.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.budget_enforcement import build_budget
from app.domain.context_builder.context_aggregation import aggregate
from app.domain.context_builder.context_builder_models import (
    ContextBuildRequest,
    ContextItem,
    ContextItemOrigin,
    ContextPackage,
    GovernedQuerySummary,
    RetrievalSummary,
)
from app.domain.context_builder.context_metadata import build_metadata
from app.domain.context_builder.context_statistics import build_statistics
from app.domain.context_builder.context_warnings import generate_warnings
from app.domain.context_builder.coverage_analysis import analyze
from app.domain.context_builder.item_selection import (
    deduplicate_items,
    select_items,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalResult,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedResultKind,
)


def _origin_of(result: GovernedRetrievalResult) -> ContextItemOrigin:
    return ContextItemOrigin(
        query_type=result.query.query_type,
        outcome=result.outcome,
        scope=result.query.scope,
        normalized_query=result.diagnostics.normalized_query,
        matched_before_limit=result.total_before_limit,
    )


def ingest(
    results: tuple[GovernedRetrievalResult, ...],
) -> tuple[ContextItem, ...]:
    """Every governed item, wrapped with the query that produced it, in
    the order retrieval returned them and deduplicated by governed
    identity."""

    items: list[ContextItem] = []

    for result in results:
        origin = _origin_of(result)
        items.extend(
            ContextItem(result=item, origin=origin) for item in result.items
        )

    return deduplicate_items(tuple(items))


def summarize_retrieval(
    results: tuple[GovernedRetrievalResult, ...],
    items: tuple[ContextItem, ...],
) -> RetrievalSummary:
    """
    An echo, never a recomputation.

    ``total_before_limit`` is the sum over the governed queries: how many
    governed objects retrieval saw before its own limit, which is the
    number a reader needs to tell a complete answer from a truncated one.
    """

    return RetrievalSummary(
        retrieved_item_count=len(items),
        total_before_limit=sum(
            result.total_before_limit for result in results
        ),
        retrieved_asset_count=sum(
            1 for item in items if item.kind is GovernedResultKind.ASSET
        ),
        retrieved_quantity_count=sum(
            1 for item in items if item.kind is GovernedResultKind.QUANTITY
        ),
        retrieved_relationship_count=sum(
            1
            for item in items
            if item.kind is GovernedResultKind.RELATIONSHIP
        ),
        queries=tuple(
            GovernedQuerySummary(
                query_type=result.query.query_type,
                outcome=result.outcome,
                scope=result.query.scope,
                normalized_query=result.diagnostics.normalized_query,
                matched_before_limit=result.total_before_limit,
                returned_count=len(result.items),
            )
            for result in results
        ),
    )


def assemble_context_package(
    request: ContextBuildRequest, *, now: datetime
) -> ContextPackage:
    items = ingest(request.results)
    summary = summarize_retrieval(request.results, items)

    selection = select_items(items, request.configuration.budget_policy)
    assembly = aggregate(selection.selected)
    coverage = analyze(summary, assembly)

    metadata, metadata_consumption = build_metadata(
        configuration=request.configuration,
        results=request.results,
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
        selected_assets=assembly.selected_assets,
        selected_quantities=assembly.selected_quantities,
        selected_relationships=assembly.selected_relationships,
        selected_items=assembly.selected_items,
        coverage=coverage,
        statistics=statistics,
        warnings=warnings,
        budget=budget,
        metadata=metadata,
    )
