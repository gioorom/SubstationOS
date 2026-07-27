"""
Budget Enforcement (Milestone 14's pipeline stage of the same name).
Combines every ``BudgetConsumption`` record gathered across the
pipeline - the candidate/entity/relationship/attribute admission
decisions Selection already made, plus the metadata-entry and warning
truncation decisions made later in assembly - into the final,
reportable ``ContextBudget``. Performs no admission decisions of its
own; it is the single place that reports what every earlier stage's
budget bookkeeping decided. O(1) in the (fixed, small) number of budget
categories.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import (
    BudgetConsumption,
    BudgetPolicy,
    ContextBudget,
)


def build_budget(
    policy: BudgetPolicy, consumption: tuple[BudgetConsumption, ...]
) -> ContextBudget:
    exceeded = any(entry.discarded > 0 for entry in consumption)

    return ContextBudget(
        policy=policy, consumption=consumption, exceeded=exceeded
    )
