"""
Warnings: what a governed context must say about itself.

Generates every structured, machine-readable ``ContextWarning`` in a
fixed, documented priority order - budget exceeded, ambiguous retrieval,
missing quantities, missing relationships, partial coverage, item
discarded - then truncates to the configured ``max_warnings`` budget,
reporting that truncation as its own ``BudgetConsumption``.

Never invents a warning about data Context Assembly cannot observe: each
one is derived strictly from the ``SelectionOutcome``,
``ContextAssemblyResult``, ``CoverageReport`` and ``RetrievalSummary``
already computed. O(n) in the number of selected and discarded items.

---

## What EPIC 31.3 removed, and why

``MISSING_PROVENANCE`` is **gone**. It fired when a legacy candidate
carried no ``GraphExecution`` id - the strongest origin a Canonical
Facts candidate had. A governed item cannot exist without provenance
(``GovernedRetrievalItem.provenance`` has no default and no ``| None``,
and the governed tables enforce it with ``nullable=False``), so the
warning described a state the platform can no longer produce. A warning
that can never fire is worse than no warning: its silence reads as
reassurance.

## What EPIC 31.3 added

``AMBIGUOUS_RETRIEVAL``, and it is the important one. When a governed
query matched more than one object - two documents each designating a
``TR1`` - the context says so, per query, naming the term and the count.
Downstream must never be able to read an ordered list as one certain
answer, and this is where that becomes visible rather than merely true.
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
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
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


def _ambiguous_retrieval_warnings(
    summary: RetrievalSummary,
) -> list[ContextWarning]:
    """
    One warning per ambiguous governed query, naming the term and the
    number of governed objects that matched.

    Per query rather than per package: a context assembled from a unique
    match and an ambiguous one is not "somewhat ambiguous", and averaging
    the two would be exactly the false certainty this warning exists to
    prevent.
    """

    return [
        ContextWarning(
            category=ContextWarningCategory.AMBIGUOUS_RETRIEVAL,
            message=(
                f"Governed retrieval for '{query.normalized_query}' matched "
                f"{query.matched_before_limit} distinct governed objects. "
                "They are different governed identities and were not "
                "merged; this context contains more than one answer."
                if query.normalized_query
                else (
                    f"A governed {query.query_type.value} query matched "
                    f"{query.matched_before_limit} distinct governed "
                    "objects, which were not merged."
                )
            ),
        )
        for query in summary.queries
        if query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
    ]


def _missing_kind_warnings(
    assembly: ContextAssemblyResult, summary: RetrievalSummary
) -> list[ContextWarning]:
    """
    Fires only when knowledge of that kind was actually retrieved but
    none survived selection - never for a kind that was never offered
    (an empty or narrowly-scoped retrieval is not a "gap", it is what
    was asked for).
    """

    warnings: list[ContextWarning] = []

    if not assembly.selected_quantities and summary.retrieved_quantity_count:
        warnings.append(
            ContextWarning(
                category=ContextWarningCategory.MISSING_QUANTITIES,
                message=(
                    f"{summary.retrieved_quantity_count} governed "
                    "quantity result(s) were retrieved, but none were "
                    "selected into this context package."
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
                    f"{summary.retrieved_relationship_count} governed "
                    "relationship result(s) were retrieved, but none were "
                    "selected into this context package."
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


def _item_discarded_warnings(
    selection: SelectionOutcome,
) -> list[ContextWarning]:
    return [
        ContextWarning(
            category=ContextWarningCategory.ITEM_DISCARDED,
            message=(
                f"Governed result '{discarded.item.item_id}' was discarded "
                f"({discarded.reason.value} budget)."
            ),
            item_id=discarded.item.item_id,
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
    warnings.extend(_ambiguous_retrieval_warnings(summary))
    warnings.extend(_missing_kind_warnings(assembly, summary))
    warnings.extend(_partial_coverage_warnings(coverage))
    warnings.extend(_item_discarded_warnings(selection))

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
