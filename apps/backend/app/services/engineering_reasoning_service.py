"""
Application service for deterministic engineering reasoning (EPIC 32.1).

**Performs no I/O**, and that is a security property rather than a
layering preference. Its entire input is the `ContextPackage` it is
handed: it opens no session, holds no repository, reads no graph and
reads no review. Governed Structured Retrieval applied the project
scope, the document scope and the caller's authorization; a reasoning
service that could read for itself would be able to widen any of them
with nothing downstream noticing.

If the knowledge a rule needs is not in the context, the answer is
`INSUFFICIENT_KNOWLEDGE` - never a second query.

---

## What this service is, and is not

It is a thin, deterministic dispatcher: it picks the rule for a query
and times the evaluation. It contains **no reasoning logic** - that
lives in the rule, which owns an identity and a version, so a change to
what the platform concludes is always a version change somebody can
point at.

It does not write the governed graph, create a review, or modify any
pipeline artefact. It cannot: it has nothing to write with.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_reasoning import quantity_consistency_rule
from app.domain.engineering_reasoning.reasoning_models import (
    QuantityConsistencyQuery,
    ReasoningResult,
)


def evaluate_quantity_consistency(
    package: ContextPackage,
    query: QuantityConsistencyQuery,
    *,
    now: datetime,
) -> ReasoningResult:
    """
    Runs the quantity-consistency rule over one governed context.

    ``now`` is supplied by the caller rather than read from the clock,
    so the engineering content of the result is a pure function of the
    context and the query. The one thing measured here -
    ``duration_seconds`` - is operational, varies run to run, and is
    excluded from the result's identity for exactly that reason.
    """

    started = time.perf_counter()

    result = quantity_consistency_rule.evaluate(
        package, query, evaluated_at=now
    )

    return replace(
        result,
        diagnostics=replace(
            result.diagnostics,
            duration_seconds=time.perf_counter() - started,
        ),
    )
