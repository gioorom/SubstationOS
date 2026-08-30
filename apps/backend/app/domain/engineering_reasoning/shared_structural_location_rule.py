"""
The second engineering reasoning rule: shared structural location.

**Pure.** A `ContextPackage` in, a `ReasoningResult` out. No repository,
no session, no clock read, no provider, no randomness, no traversal.
Given the same context and the same query it returns the same
conclusion, the same contributor order and the same identity.

---

## The question it answers

> Does governed knowledge establish that these two assets stand in the
> same governed structural location?

EPIC 32.P1 gave the governed graph its first relationship between two
structural objects. Two approved statements can now say
``+E01-QA1 IS_LOCATED_IN +E01`` and ``+E01-QB1 IS_LOCATED_IN +E01``.
Nothing in either document says the two devices are in one place
together - that is a conclusion, and this rule is the first thing in the
platform allowed to draw it.

## Why the shape is not the reason

The governed graph contains, after 32.P1, a path:

```
A --IS_LOCATED_IN--> X <--IS_LOCATED_IN-- B
```

**That path is not why the inference is valid.** A graph path is a fact
about a data structure. The inference is authorised by this rule, which
states in engineering terms what that particular shape means for this
particular question, and carries a version so the statement can be
argued with and changed.

The distinction is not academic. The identical shape over a different
edge kind would license nothing: two assets that both have a rated power
of 630 kVA form the same topological shape through the quantity node and
share no engineering property whatever. This rule reads
``IS_LOCATED_IN`` and nothing else, by name, because the meaning lives in
the edge kind rather than in the geometry.

## What it concludes, and the far longer list of what it does not

It concludes exactly one thing: the two assets share a governed
structural-location context.

It does **not** conclude that they are connected, that current can flow
between them, that one feeds, supplies, protects or controls the other,
that they are adjacent, that they are on one busbar or in one circuit,
that either is energised or in service, or what kind of place the shared
location is. A substation location routinely holds equipment from
several unrelated circuits; a bay, a room and a cubicle are all just
``+`` aspects to this platform.

## Required inputs, stated rather than assumed

| Outcome | Requires |
|---|---|
| `ESTABLISHED` | one applicable governed location per side, and the **same** governed location identity |
| `AMBIGUOUS` | a designation that resolved to several governed assets, or a side with several applicable governed locations |
| `INSUFFICIENT_KNOWLEDGE` | a missing location on either side, **or** two governed locations whose identities differ |

## Why differing locations are insufficient rather than negative

``A -> X``, ``B -> Y``, ``X != Y`` does **not** establish that the two
assets are in different places, and the rule never says so. Two
independent reasons, either sufficient on its own:

1. **Location identity is document-scoped** (EPIC 32.P1, ADR-0030). The
   same ``+E01`` written in two documents is two governed identities. So
   ``X != Y`` is entirely compatible with one physical place.
2. **The graph is partial.** A location relationship exists only where a
   document wrote a compound designation and a reviewer approved reading
   it. An asset may stand somewhere nobody has recorded.

A `NOT_SHARED` outcome would assert something no governed input
supports, and it would be believed. `INSUFFICIENT_KNOWLEDGE` with the
`DISTINCT_LOCATION_IDENTITIES` diagnostic reports precisely what was
found: two locations, not the same identity, no conclusion.

## What it reads

The selected governed items, filtered to those carrying an
`IS_LOCATED_IN` relationship. Nothing is fetched. If the required knowledge is not in the
context the answer is `INSUFFICIENT_KNOWLEDGE`, never a second query
(AF-CTX-002).

There is **no traversal**: the rule reads a flat collection of governed
relationships and matches on subject identity. There is no depth
parameter because there is no depth, no visited set because nothing is
walked, and no cycle handling because a cycle in unrelated context is
simply data this rule does not select.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import (
    ContextItem,
    ContextPackage,
)
from app.domain.engineering_reasoning.reasoning_identity import (
    reasoning_result_id,
)
from app.domain.engineering_reasoning.reasoning_models import (
    ReasoningContributor,
    ReasoningResult,
    ReasoningRuleIdentity,
    SharedLocationInferencePath,
    SharedStructuralLocationAssessment,
    SharedStructuralLocationQuery,
    StructuralReasoningDiagnostics,
)
from app.domain.engineering_reasoning.reasoning_policy import (
    REASONING_POLICY_VERSION,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    DerivedRelationshipKind,
    ReasoningRuleFamily,
    StructuralReasoningDiagnosticCode,
    StructuralReasoningOutcome,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedQueryType,
)

#: This rule's identity. **Bump the version whenever what it concludes
#: could change** - a different treatment of multiple locations, a
#: negative outcome, a second supported edge kind. Two results carrying
#: the same identity and the same governed inputs are required to agree.
SHARED_STRUCTURAL_LOCATION_RULE = ReasoningRuleIdentity(
    rule_id="shared_structural_location",
    rule_version="1.0",
    family=ReasoningRuleFamily.STRUCTURAL_RELATIONSHIP,
)

#: The one governed relationship kind this rule reads.
#:
#: Named explicitly rather than derived, because the whole validity of
#: the inference rests on *which* relationship it is. The same graph
#: shape over `HAS_RATED_POWER` would mean two assets happen to have
#: equal ratings, which licenses nothing. A future structural rule reads
#: its own edge kind, stated on its own line, under its own version.
LOCATION_RELATIONSHIP_KIND = GraphEdgeKind.IS_LOCATED_IN

#: How many applicable governed locations a side may have for the rule to
#: reach a conclusion about it. More than one and the question of *which*
#: location is being asked about is not decidable from governed inputs.
MAXIMUM_APPLICABLE_LOCATIONS_PER_SIDE = 1


def _location_items(package: ContextPackage) -> tuple[ContextItem, ...]:
    """
    The governed location relationships the context carries.

    Selected from the context the caller was given - never fetched.

    Filtered on **the relationship's kind**, across every selected item,
    rather than on the item's result kind. Governed retrieval reports the
    same relationship under different result kinds depending on how it
    was reached: a relationship query returns it as a ``RELATIONSHIP``,
    while traversing outward from an asset returns the node arrived at,
    carrying the relationship that led there. Both are the same governed
    edge, and a rule that read only one shape would answer differently
    depending on which query the engine happened to run.
    """

    return tuple(
        item
        for item in package.selected_items
        if item.result.relationship is not None
        and item.result.relationship.kind is LOCATION_RELATIONSHIP_KIND
    )


def _for_asset(
    items: tuple[ContextItem, ...], asset_node_id: str
) -> tuple[ContextItem, ...]:
    """
    The governed location relationships whose **subject** is this asset.

    Matched on governed node identity, never on label. Two documents may
    each designate a ``TR1``; matching on the designation would answer
    about whichever of them retrieval happened to return first.
    """

    return tuple(
        item
        for item in items
        if item.result.relationship is not None
        and item.result.relationship.subject.node_id == asset_node_id
    )


def _distinct_locations(items: tuple[ContextItem, ...]) -> tuple[str, ...]:
    """
    The distinct governed location identities these relationships point
    at, in canonical (sorted) order.

    **Identity, not label.** ``+E01`` from one document and ``+E01`` from
    another are two governed locations, and collapsing them here would be
    the cross-document entity resolution this platform does not perform
    (ADR-0030).
    """

    return tuple(
        sorted(
            {
                item.result.relationship.object.node_id
                for item in items
                if item.result.relationship is not None
            }
        )
    )


def _contributors(
    *items: ContextItem,
) -> tuple[ReasoningContributor, ...]:
    """
    The governed relationships a conclusion rests on, in canonical order.

    Ordered by the governed retrieval sort key and then by the governed
    result id - never by the order the context happened to list them, and
    never by which side of the question they came from. Asking about
    (A, B) and about (B, A) therefore yields the same contributors in the
    same order, which is what lets the two be recognised as one
    conclusion.
    """

    contributors = [
        ReasoningContributor.of_relationship(item) for item in items
    ]

    return tuple(
        sorted(contributors, key=lambda c: (c.order_key, c.item_id))
    )


def _asset_outcome(
    package: ContextPackage,
) -> GovernedMatchOutcome | None:
    """
    Whether the designations in the question resolved to one governed
    asset each.

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
        return None

    if any(
        query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
        for query in designation_queries
    ):
        return GovernedMatchOutcome.MULTIPLE_MATCHES

    return None


def _result(
    *,
    query: SharedStructuralLocationQuery,
    assessment: SharedStructuralLocationAssessment,
    contributors: tuple[ReasoningContributor, ...],
    package: ContextPackage,
    evaluated_at: datetime,
) -> ReasoningResult:
    """
    Wraps one assessment in the common reasoning envelope.

    The identity is composed from the **canonical** question - the two
    governed asset identities, sorted - so a symmetric question has a
    symmetric identity. The displayed question keeps the order asked.
    """

    return ReasoningResult(
        result_id=reasoning_result_id(
            rule_id=SHARED_STRUCTURAL_LOCATION_RULE.rule_id,
            rule_version=SHARED_STRUCTURAL_LOCATION_RULE.rule_version,
            question=query.identity_question,
            project_id=query.project_id,
            contributing_identities=tuple(
                contributor.item_id for contributor in contributors
            ),
        ),
        query=query,
        rule=SHARED_STRUCTURAL_LOCATION_RULE,
        outcome=assessment.outcome,
        contributors=contributors,
        diagnostics=assessment.diagnostics,
        reasoning_policy_version=REASONING_POLICY_VERSION,
        context_assembly_version=package.metadata.context_assembly_version,
        evaluated_at=evaluated_at,
        structural=assessment,
    )


def evaluate(
    package: ContextPackage,
    query: SharedStructuralLocationQuery,
    *,
    evaluated_at: datetime,
) -> ReasoningResult:
    """
    Evaluates the rule over one governed context.

    ``evaluated_at`` is supplied by the caller rather than read from the
    clock, so this function performs no I/O and no non-deterministic side
    effect - and nothing in the result's *identity* derives from it.
    """

    asset_outcome = _asset_outcome(package)

    def assess(
        code: StructuralReasoningDiagnosticCode,
        outcome: StructuralReasoningOutcome,
        *,
        left_count: int,
        right_count: int,
        contributing: int,
        derived: DerivedRelationshipKind | None = None,
        location_node_id: str | None = None,
        location_label: str | None = None,
        path: SharedLocationInferencePath | None = None,
    ) -> SharedStructuralLocationAssessment:
        return SharedStructuralLocationAssessment(
            outcome=outcome,
            diagnostics=StructuralReasoningDiagnostics(
                code=code,
                left_location_count=left_count,
                right_location_count=right_count,
                contributing_input_count=contributing,
                subject_retrieval_outcome=asset_outcome,
            ),
            derived_relationship=derived,
            shared_location_node_id=location_node_id,
            shared_location_label=location_label,
            inference_path=path,
        )

    # --- Ambiguity first, and it is never resolved here ------------------
    #
    # A question whose designation named two governed assets was never
    # one question. Choosing between them would be silent cross-document
    # entity resolution; reasoning over both would answer about equipment
    # nobody asked about.
    if asset_outcome is GovernedMatchOutcome.MULTIPLE_MATCHES:
        return _result(
            query=query,
            assessment=assess(
                StructuralReasoningDiagnosticCode.ASSET_IDENTITY_AMBIGUOUS,
                StructuralReasoningOutcome.AMBIGUOUS,
                left_count=0,
                right_count=0,
                contributing=0,
            ),
            contributors=(),
            package=package,
            evaluated_at=evaluated_at,
        )

    governed = _location_items(package)
    left_items = _for_asset(governed, query.left_asset_node_id)
    right_items = _for_asset(governed, query.right_asset_node_id)
    left_locations = _distinct_locations(left_items)
    right_locations = _distinct_locations(right_items)

    # --- Missing knowledge is missing knowledge, not a negative ---------
    if not left_locations or not right_locations:
        if not left_locations and not right_locations:
            code = StructuralReasoningDiagnosticCode.BOTH_LOCATIONS_MISSING
        elif not left_locations:
            code = StructuralReasoningDiagnosticCode.LEFT_LOCATION_MISSING
        else:
            code = StructuralReasoningDiagnosticCode.RIGHT_LOCATION_MISSING

        contributors = _contributors(*left_items, *right_items)

        return _result(
            query=query,
            assessment=assess(
                code,
                StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
                left_count=len(left_locations),
                right_count=len(right_locations),
                contributing=len(contributors),
            ),
            contributors=contributors,
            package=package,
            evaluated_at=evaluated_at,
        )

    # --- Several governed locations on one side is a real ambiguity -----
    #
    # Which location the question is about cannot be decided from the
    # governed inputs, and picking the one that happens to match the
    # other side would be answering a question the engineer did not ask.
    if (
        len(left_locations) > MAXIMUM_APPLICABLE_LOCATIONS_PER_SIDE
        or len(right_locations) > MAXIMUM_APPLICABLE_LOCATIONS_PER_SIDE
    ):
        contributors = _contributors(*left_items, *right_items)

        return _result(
            query=query,
            assessment=assess(
                (
                    StructuralReasoningDiagnosticCode
                    .MULTIPLE_APPLICABLE_LOCATIONS
                ),
                StructuralReasoningOutcome.AMBIGUOUS,
                left_count=len(left_locations),
                right_count=len(right_locations),
                contributing=len(contributors),
            ),
            contributors=contributors,
            package=package,
            evaluated_at=evaluated_at,
        )

    left_location = left_locations[0]
    right_location = right_locations[0]

    # --- Different governed identities establish nothing either way -----
    if left_location != right_location:
        contributors = _contributors(*left_items, *right_items)

        return _result(
            query=query,
            assessment=assess(
                (
                    StructuralReasoningDiagnosticCode
                    .DISTINCT_LOCATION_IDENTITIES
                ),
                StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE,
                left_count=1,
                right_count=1,
                contributing=len(contributors),
            ),
            contributors=contributors,
            package=package,
            evaluated_at=evaluated_at,
        )

    # --- Established ----------------------------------------------------
    left_item = left_items[0]
    right_item = right_items[0]
    contributors = _contributors(left_item, right_item)

    # Canonical path orientation, so the same conclusion has the same
    # path whichever way round it was asked.
    first, second = sorted(
        (left_item, right_item),
        key=lambda item: item.result.relationship.subject.node_id,
    )

    return _result(
        query=query,
        assessment=assess(
            (
                StructuralReasoningDiagnosticCode
                .SHARED_STRUCTURAL_LOCATION_ESTABLISHED
            ),
            StructuralReasoningOutcome.ESTABLISHED,
            left_count=1,
            right_count=1,
            contributing=len(contributors),
            derived=DerivedRelationshipKind.SHARES_STRUCTURAL_LOCATION_WITH,
            location_node_id=left_location,
            location_label=left_item.result.relationship.object.label,
            path=SharedLocationInferencePath(
                left_asset_node_id=(
                    first.result.relationship.subject.node_id
                ),
                left_edge_id=first.result.relationship.edge_id,
                location_node_id=left_location,
                right_edge_id=second.result.relationship.edge_id,
                right_asset_node_id=(
                    second.result.relationship.subject.node_id
                ),
            ),
        ),
        contributors=contributors,
        package=package,
        evaluated_at=evaluated_at,
    )
