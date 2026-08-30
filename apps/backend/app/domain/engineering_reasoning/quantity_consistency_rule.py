"""
The first engineering reasoning rule: quantity consistency.

**Pure.** A `ContextPackage` in, a `ReasoningResult` out. No repository,
no session, no clock read, no provider, no randomness. Given the same
context and the same query it returns the same conclusion, the same
contributor order and the same identity.

---

## The question it answers

> Do the governed values for one quantity of one asset agree?

`TR1` has a rated power of 630 kVA in one drawing and 800 kVA in
another: two engineers approved two statements that cannot both describe
the same transformer. Nothing in this platform noticed that before -
retrieval returned both, context carried both, and a reader had to spot
it. This rule says it.

## Why *this* question first, and not nominal current

Because it is the only one governed semantics can express.
`GraphEdgeKind` has one member, `HAS_RATED_POWER`, produced by one
semantic rule. A `nominal_current` consistency rule would need a
statement type no pipeline produces, an entity type no rule assigns and
a quantity kind no ontology declares - so it would be a rule that can
never fire, over knowledge that can never exist.

The rule is written against `GraphEdgeKind` rather than against
`HAS_RATED_POWER` specifically, so the day a second quantity kind is
governed, this rule covers it with no change here.

## Required inputs, stated rather than assumed

| Outcome | Requires |
|---|---|
| `CONSISTENT` / `INCONSISTENT` | exactly one governed subject **and** at least one comparable governed value of the required kind |
| `AMBIGUOUS` | more than one governed subject |
| `INSUFFICIENT_KNOWLEDGE` | no subject, or no value of the required kind, or no value that can be compared |

**Absence is never consistency.** "No contradiction was found" and
"there was nothing to contradict" are different answers, and only the
first is `CONSISTENT`.

## What counts as a conflict

Two governed values conflict when they carry the **same unit** and
different numeric values. Nothing else. In particular:

- **Different units are not compared.** Governed knowledge carries the
  declared value and the declared unit and no base conversion - the
  exact-conversion fields the evidence layer computes
  (``base_value``/``base_unit``) are not projected into the graph. A rule
  that converted kVA to VA here would be a units engine built on data it
  does not have, so it reports `UNSUPPORTED_COMPARISON` instead and
  concludes `INSUFFICIENT_KNOWLEDGE`. That is a smaller answer than
  guessing, and it is the true one.
- **No tolerance.** Governed quantity semantics declare none, so this
  rule invents none. `630` and `630.0` are equal because `Decimal`
  compares them equal; `630` and `631` are not.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.domain.context_builder.context_builder_models import (
    ContextItem,
    ContextPackage,
)
from app.domain.engineering_reasoning.reasoning_identity import (
    reasoning_result_id,
)
from app.domain.engineering_reasoning.reasoning_models import (
    QuantityConsistencyQuery,
    ReasoningContributor,
    ReasoningDiagnostics,
    ReasoningResult,
    ReasoningRuleIdentity,
)
from app.domain.engineering_reasoning.reasoning_policy import (
    REASONING_POLICY_VERSION,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
    ReasoningRuleFamily,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedQueryType,
    GovernedResultKind,
)

#: This rule's identity. **Bump the version whenever what it concludes
#: could change** - a new comparison, a tolerance, a different treatment
#: of a single value. Two results carrying the same identity and the same
#: governed inputs are required to agree.
QUANTITY_CONSISTENCY_RULE = ReasoningRuleIdentity(
    rule_id="governed_quantity_consistency",
    rule_version="1.0",
    family=ReasoningRuleFamily.QUANTITY_CONSISTENCY,
)

#: How many comparable governed values the rule needs before it will say
#: `CONSISTENT` or `INCONSISTENT`.
#:
#: **One is enough to say `CONSISTENT`**, and that is a decision rather
#: than an oversight: the question is whether the governed knowledge
#: *disagrees with itself*, and one approved value does not. It is
#: recorded in the diagnostics as `SINGLE_VALUE` so a reader can tell
#: "one value, no disagreement" from "several values that agree" - which
#: are different engineering situations even though the outcome is the
#: same.
MINIMUM_COMPARABLE_VALUES = 1


def _parse(value: str) -> Decimal | None:
    """
    A governed normalized value, as an exact number.

    ``Decimal``, never ``float``: 0.1 is not representable in binary
    floating point, and a rated power reading back as 630.0000000000001
    would be a defect an engineer could not explain. The evidence layer
    made the same choice for the same reason.
    """

    try:
        return Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _quantity_items(
    package: ContextPackage, query: QuantityConsistencyQuery
) -> tuple[ContextItem, ...]:
    """
    The governed quantities asserted about the subject by the required
    relationship kind.

    Selected from the context the caller was given - never fetched. If
    the required knowledge is not in the context, the answer is
    `INSUFFICIENT_KNOWLEDGE`, not a second query (AF-CTX-002).
    """

    return tuple(
        item
        for item in package.selected_items
        if item.kind is GovernedResultKind.QUANTITY
        and item.result.relationship is not None
        and item.result.relationship.kind is query.quantity_kind
    )


def _subject_outcome(
    package: ContextPackage,
) -> tuple[GovernedMatchOutcome | None, int]:
    """
    How many governed subjects the question resolved to.

    Read from the **retrieval outcome the context carries**, not
    recounted from the items: retrieval decided what matched, and
    recounting here would be a second definition of ambiguity that could
    disagree with the first.
    """

    designation_queries = [
        query
        for query in package.retrieval_summary.queries
        if query.query_type is GovernedQueryType.ASSET_BY_DESIGNATION
    ]

    if not designation_queries:
        return (None, 0)

    if any(
        query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
        for query in designation_queries
    ):
        return (
            GovernedMatchOutcome.MULTIPLE_MATCHES,
            max(query.matched_before_limit for query in designation_queries),
        )

    if all(
        query.outcome is GovernedMatchOutcome.NO_MATCH
        for query in designation_queries
    ):
        return (GovernedMatchOutcome.NO_MATCH, 0)

    return (GovernedMatchOutcome.UNIQUE_MATCH, 1)


def _result(
    *,
    query: QuantityConsistencyQuery,
    outcome: ReasoningOutcome,
    contributors: tuple[ReasoningContributor, ...],
    diagnostics: ReasoningDiagnostics,
    package: ContextPackage,
    evaluated_at: datetime,
) -> ReasoningResult:
    return ReasoningResult(
        result_id=reasoning_result_id(
            rule_id=QUANTITY_CONSISTENCY_RULE.rule_id,
            rule_version=QUANTITY_CONSISTENCY_RULE.rule_version,
            question=query.question,
            project_id=query.project_id,
            contributing_identities=tuple(
                contributor.item_id for contributor in contributors
            ),
        ),
        query=query,
        rule=QUANTITY_CONSISTENCY_RULE,
        outcome=outcome,
        contributors=contributors,
        diagnostics=diagnostics,
        reasoning_policy_version=REASONING_POLICY_VERSION,
        context_assembly_version=package.metadata.context_assembly_version,
        evaluated_at=evaluated_at,
    )


def evaluate(
    package: ContextPackage,
    query: QuantityConsistencyQuery,
    *,
    evaluated_at: datetime,
) -> ReasoningResult:
    """
    Evaluates the rule over one governed context.

    ``evaluated_at`` is supplied by the caller rather than read from the
    clock, so this function performs no I/O and no non-deterministic
    side effect - and nothing in the result's *identity* derives from it.
    """

    subject_outcome, candidate_count = _subject_outcome(package)

    def diagnostics(
        code: ReasoningDiagnosticCode,
        *,
        available: int,
        contributing: int,
        distinct_values: int,
        distinct_units: int,
    ) -> ReasoningDiagnostics:
        return ReasoningDiagnostics(
            code=code,
            required_input_count=MINIMUM_COMPARABLE_VALUES,
            available_input_count=available,
            contributing_input_count=contributing,
            candidate_subject_count=candidate_count,
            distinct_value_count=distinct_values,
            distinct_unit_count=distinct_units,
            subject_retrieval_outcome=subject_outcome,
        )

    # --- Ambiguity first, and it is never resolved here ------------------
    #
    # A question that named two governed assets was never one question.
    # Reasoning over both and reporting a conflict would manufacture a
    # disagreement between two different transformers; picking one would
    # be silent cross-document entity resolution. Both are refused.
    if subject_outcome is GovernedMatchOutcome.MULTIPLE_MATCHES:
        return _result(
            query=query,
            outcome=ReasoningOutcome.AMBIGUOUS,
            contributors=(),
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.AMBIGUOUS_SUBJECT,
                available=0,
                contributing=0,
                distinct_values=0,
                distinct_units=0,
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    if subject_outcome is GovernedMatchOutcome.NO_MATCH:
        return _result(
            query=query,
            outcome=ReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
            contributors=(),
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.NO_SUBJECT,
                available=0,
                contributing=0,
                distinct_values=0,
                distinct_units=0,
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    items = _quantity_items(package, query)

    if not items:
        return _result(
            query=query,
            outcome=ReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
            contributors=(),
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.NO_REQUIRED_QUANTITY,
                available=0,
                contributing=0,
                distinct_values=0,
                distinct_units=0,
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    # --- Contributors, in the governed total order -----------------------
    #
    # Every governed value is a contributor, including ones that cannot
    # be compared: a conclusion of INSUFFICIENT_KNOWLEDGE still has to
    # say which governed knowledge it looked at.
    contributors = tuple(
        sorted(
            (
                ReasoningContributor.of(
                    item,
                    None
                    if item.result.node is None
                    else _parse(item.result.node.normalized_value),
                )
                for item in items
            ),
            key=lambda contributor: (
                contributor.order_key,
                contributor.item_id,
            ),
        )
    )

    comparable = tuple(
        contributor
        for contributor in contributors
        if contributor.value is not None and contributor.unit is not None
    )
    units = {contributor.unit for contributor in comparable}
    values = {contributor.value for contributor in comparable}

    if len(comparable) < MINIMUM_COMPARABLE_VALUES:
        return _result(
            query=query,
            outcome=ReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
            contributors=contributors,
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.UNPARSABLE_VALUE,
                available=len(items),
                contributing=len(contributors),
                distinct_values=len(values),
                distinct_units=len(units),
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    # --- Different units are reported, never converted -------------------
    if len(units) > 1:
        return _result(
            query=query,
            outcome=ReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
            contributors=contributors,
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.UNSUPPORTED_COMPARISON,
                available=len(items),
                contributing=len(contributors),
                distinct_values=len(values),
                distinct_units=len(units),
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    if len(values) > 1:
        return _result(
            query=query,
            outcome=ReasoningOutcome.INCONSISTENT,
            contributors=contributors,
            diagnostics=diagnostics(
                ReasoningDiagnosticCode.VALUES_CONFLICT,
                available=len(items),
                contributing=len(contributors),
                distinct_values=len(values),
                distinct_units=len(units),
            ),
            package=package,
            evaluated_at=evaluated_at,
        )

    return _result(
        query=query,
        outcome=ReasoningOutcome.CONSISTENT,
        contributors=contributors,
        diagnostics=diagnostics(
            ReasoningDiagnosticCode.SINGLE_VALUE
            if len(comparable) == 1
            else ReasoningDiagnosticCode.VALUES_EQUAL,
            available=len(items),
            contributing=len(contributors),
            distinct_values=len(values),
            distinct_units=len(units),
        ),
        package=package,
        evaluated_at=evaluated_at,
    )
