"""
Shared builders for governed retrieval results and governed contexts.

Introduced by EPIC 31.3, when Context Assembly stopped speaking the
legacy ``KnowledgeCandidate`` vocabulary. Every test that needs "a
context with some governed knowledge in it" builds one here, so the
shape lives in one place and a change to the governed model breaks one
file rather than thirty.

**Everything here is a real domain object.** These helpers construct
genuine ``GovernedRetrievalItem``/``GovernedRetrievalResult`` values and
run the real assembler; nothing is a stub, and no test can accidentally
assert against a shape the production path could not produce. In
particular the provenance is complete, because a governed item cannot be
constructed without it - which is the invariant most of these tests
exist to protect.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_match_policy import (
    precedence_of,
)
from app.domain.governed_retrieval.governed_normalization import (
    normalize_designation,
)
from app.domain.governed_retrieval.governed_result_identity import (
    node_result_id,
    relationship_result_id,
    traversed_node_result_id,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    AssetDesignationQuery,
    AssetQuantityQuery,
    GovernedGraphVersion,
    GovernedMatchExplanation,
    GovernedNodeReference,
    GovernedProvenanceView,
    GovernedRelationshipReference,
    GovernedRetrievalDiagnostics,
    GovernedRetrievalItem,
    GovernedRetrievalResult,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedResultKind,
    RetrievalScope,
)
from app.services import context_builder_service

REVIEWED_AT = datetime(2026, 3, 4, 10, 30, 0)
RETRIEVED_AT = datetime(2026, 3, 5, 9, 0, 0)


def provenance(
    *,
    statement_key: str = "statement-1",
    document_id: int = 11,
    review_id: int = 21,
    project_id: int | None = 1,
) -> GovernedProvenanceView:
    """Complete governed provenance. Every field is populated because
    every field is mandatory."""

    return GovernedProvenanceView(
        statement_key=statement_key,
        document_id=document_id,
        content_checksum="checksum-abc",
        review_id=review_id,
        reviewer_user_id=7,
        reviewer_display_name="Test Engineer",
        reviewed_at=REVIEWED_AT,
        semantic_rule_id="rated_power_from_associated_quantity",
        semantic_rule_version="1.0",
        semantic_contract_version="1.0",
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint="fingerprint-abc",
        project_id=project_id,
    )


def node(
    node_id: str,
    label: str,
    *,
    kind: GraphNodeKind = GraphNodeKind.ENGINEERING_ASSET,
    unit: str | None = None,
) -> GovernedNodeReference:
    return GovernedNodeReference(
        node_id=node_id,
        kind=kind,
        label=label,
        normalized_value=normalize_designation(label),
        unit=unit,
    )


def asset_item(
    node_id: str,
    label: str,
    *,
    strategy: GovernedMatchStrategy = (
        GovernedMatchStrategy.EXACT_DESIGNATION
    ),
    state: GraphObjectState = GraphObjectState.ACTIVE,
    statement_key: str = "statement-1",
    document_id: int = 11,
    review_id: int = 21,
    project_id: int | None = 1,
) -> GovernedRetrievalItem:
    reference = node(node_id, label)

    return GovernedRetrievalItem(
        result_id=node_result_id(GovernedResultKind.ASSET, node_id),
        kind=GovernedResultKind.ASSET,
        node=reference,
        relationship=None,
        state=state,
        retirement_reason=None,
        match=GovernedMatchExplanation(
            strategy=strategy,
            matched_field="label",
            matched_value=label,
            normalized_query=normalize_designation(label),
        ),
        provenance=provenance(
            statement_key=statement_key,
            document_id=document_id,
            review_id=review_id,
            project_id=project_id,
        ),
        sort_key=(
            precedence_of(strategy),
            normalize_designation(label),
            "",
            node_id,
        ),
    )


def quantity_item(
    *,
    subject_node_id: str,
    subject_label: str,
    quantity_node_id: str,
    quantity_label: str,
    unit: str = "kVA",
    normalized_value: str | None = None,
    edge_id: str = "edge-1",
    statement_key: str = "statement-1",
    document_id: int = 11,
    review_id: int = 21,
    project_id: int | None = 1,
) -> GovernedRetrievalItem:
    """
    A governed quantity reached by traversing one governed relationship -
    the shape ``has_rated_power`` produces.

    ``normalized_value`` defaults to the **bare decimal** parsed out of
    the label, which is what promotion actually writes
    (``str(entity.quantity.value)`` in ``_node_for``) - the unit lives in
    its own column. It is not the designation fold ``node()`` applies:
    that fold is right for an asset label and wrong for a quantity, and
    a fixture that used it would let a test pass against a shape the
    pipeline never produces.
    """

    subject = node(subject_node_id, subject_label)
    quantity = GovernedNodeReference(
        node_id=quantity_node_id,
        kind=GraphNodeKind.ENGINEERING_QUANTITY,
        label=quantity_label,
        normalized_value=(
            quantity_label.split()[0]
            if normalized_value is None
            else normalized_value
        ),
        unit=unit,
    )
    strategy = GovernedMatchStrategy.RELATIONSHIP_TRAVERSAL

    return GovernedRetrievalItem(
        result_id=traversed_node_result_id(
            GovernedResultKind.QUANTITY, edge_id, quantity_node_id
        ),
        kind=GovernedResultKind.QUANTITY,
        node=quantity,
        relationship=GovernedRelationshipReference(
            edge_id=edge_id,
            kind=GraphEdgeKind.HAS_RATED_POWER,
            subject=subject,
            object=quantity,
        ),
        state=GraphObjectState.ACTIVE,
        retirement_reason=None,
        match=GovernedMatchExplanation(
            strategy=strategy,
            matched_field=f"edge.{GraphEdgeKind.HAS_RATED_POWER.value}",
            matched_value=edge_id,
        ),
        provenance=provenance(
            statement_key=statement_key,
            document_id=document_id,
            review_id=review_id,
            project_id=project_id,
        ),
        sort_key=(
            precedence_of(strategy),
            normalize_designation(subject_label),
            normalize_designation(quantity_label),
            edge_id,
        ),
    )


def relationship_item(
    *,
    subject_node_id: str,
    subject_label: str,
    object_node_id: str,
    object_label: str,
    edge_id: str = "edge-1",
    statement_key: str = "statement-1",
    document_id: int = 11,
    review_id: int = 21,
    project_id: int | None = 1,
) -> GovernedRetrievalItem:
    subject = node(subject_node_id, subject_label)
    object_node = node(
        object_node_id,
        object_label,
        kind=GraphNodeKind.ENGINEERING_QUANTITY,
        unit="kVA",
    )
    strategy = GovernedMatchStrategy.EDGE_KIND

    return GovernedRetrievalItem(
        result_id=relationship_result_id(edge_id),
        kind=GovernedResultKind.RELATIONSHIP,
        node=None,
        relationship=GovernedRelationshipReference(
            edge_id=edge_id,
            kind=GraphEdgeKind.HAS_RATED_POWER,
            subject=subject,
            object=object_node,
        ),
        state=GraphObjectState.ACTIVE,
        retirement_reason=None,
        match=GovernedMatchExplanation(
            strategy=strategy,
            matched_field="kind",
            matched_value=GraphEdgeKind.HAS_RATED_POWER.value,
        ),
        provenance=provenance(
            statement_key=statement_key,
            document_id=document_id,
            review_id=review_id,
            project_id=project_id,
        ),
        sort_key=(
            precedence_of(strategy),
            normalize_designation(subject_label),
            normalize_designation(object_label),
            edge_id,
        ),
    )


def designation_result(
    designation: str,
    items: tuple[GovernedRetrievalItem, ...],
    *,
    project_id: int = 1,
    limit: int = 20,
    total_before_limit: int | None = None,
    scope: RetrievalScope = RetrievalScope.CURRENT_ONLY,
) -> GovernedRetrievalResult:
    """
    One governed designation lookup.

    ``total_before_limit`` defaults to the item count, so the outcome is
    consistent with what the result carries; pass a larger number to
    build a **truncated** result whose outcome is still honest about how
    many governed objects matched.
    """

    total = len(items) if total_before_limit is None else total_before_limit

    return _result(
        query=AssetDesignationQuery(
            designation=designation,
            scope=scope,
            limit=limit,
            project_id=project_id,
        ),
        items=items,
        total_before_limit=total,
        limit=limit,
        normalized_query=normalize_designation(designation),
    )


def quantity_result(
    designation: str,
    items: tuple[GovernedRetrievalItem, ...],
    *,
    project_id: int = 1,
    limit: int = 20,
    total_before_limit: int | None = None,
) -> GovernedRetrievalResult:
    total = len(items) if total_before_limit is None else total_before_limit

    return _result(
        query=AssetQuantityQuery(
            scope=RetrievalScope.CURRENT_ONLY,
            limit=limit,
            designation=designation,
            project_id=project_id,
        ),
        items=items,
        total_before_limit=total,
        limit=limit,
        normalized_query=normalize_designation(designation),
    )


def _result(
    *,
    query,
    items: tuple[GovernedRetrievalItem, ...],
    total_before_limit: int,
    limit: int,
    normalized_query: str | None,
) -> GovernedRetrievalResult:
    if total_before_limit == 0:
        outcome = GovernedMatchOutcome.NO_MATCH
    elif total_before_limit == 1:
        outcome = GovernedMatchOutcome.UNIQUE_MATCH
    else:
        outcome = GovernedMatchOutcome.MULTIPLE_MATCHES

    return GovernedRetrievalResult(
        query=query,
        outcome=outcome,
        items=items,
        total_before_limit=total_before_limit,
        applied_limit=limit,
        diagnostics=GovernedRetrievalDiagnostics(
            query_type=query.query_type,
            scope=query.scope,
            normalized_query=normalized_query,
            strategies_attempted=(
                GovernedMatchStrategy.EXACT_DESIGNATION,
            ),
            candidates_examined=max(total_before_limit, len(items)),
            matched_count=total_before_limit,
            returned_count=len(items),
            ambiguous=outcome is GovernedMatchOutcome.MULTIPLE_MATCHES,
            no_match=outcome is GovernedMatchOutcome.NO_MATCH,
            normalization_version="1.0",
            matching_policy_version="1.0",
            graph_version=GovernedGraphVersion(
                generation_number=3,
                generation_created_at=REVIEWED_AT,
                promotion_contract_version="1.0",
            ),
            duration_seconds=0.001,
        ),
        retrieved_at=RETRIEVED_AT,
    )


def one_asset_results(
    *, project_id: int = 1
) -> tuple[GovernedRetrievalResult, ...]:
    """The commonest fixture: one unambiguous asset and its rated
    power."""

    return (
        designation_result(
            "TR1",
            (
                asset_item(
                    "node-tr1", "TR1", project_id=project_id
                ),
            ),
            project_id=project_id,
        ),
        quantity_result(
            "TR1",
            (
                quantity_item(
                    subject_node_id="node-tr1",
                    subject_label="TR1",
                    quantity_node_id="node-630kva",
                    quantity_label="630 kVA",
                    project_id=project_id,
                ),
            ),
            project_id=project_id,
        ),
    )


def context_package(
    *,
    project_id: int = 1,
    results: tuple[GovernedRetrievalResult, ...] | None = None,
    now: datetime = RETRIEVED_AT,
    **limits,
):
    """
    A real ``ContextPackage``, assembled by the real service.

    Tests that need "a context" get one that the production path could
    have produced, rather than a hand-built value object that might drift
    from what assembly actually emits.
    """

    return context_builder_service.build_context_package(
        project_id=project_id,
        results=one_asset_results(project_id=project_id)
        if results is None
        else results,
        now=now,
        **limits,
    ).package


def empty_context_package(*, project_id: int = 1, now: datetime = RETRIEVED_AT):
    """A context assembled from a governed query that matched nothing -
    an honest engineering answer, never an error."""

    return context_builder_service.build_context_package(
        project_id=project_id,
        results=(designation_result("TR1", (), project_id=project_id),),
        now=now,
    ).package

def results_for(
    items: tuple[GovernedRetrievalItem, ...], *, project_id: int = 1
) -> tuple[GovernedRetrievalResult, ...]:
    """
    One governed query per item, each an unambiguous match.

    The honest default for a test that just needs "a context holding
    these things": several distinct governed objects are normally the
    answers to several queries, not several answers to one. Bundling
    them into a single result would make every such fixture report
    ``MULTIPLE_MATCHES`` and raise an ambiguity warning that describes
    nothing real.
    """

    results = []

    for item in items:
        label = (
            item.node.label
            if item.node is not None
            else item.relationship.subject.label
        )
        results.append(
            designation_result(label, (item,), project_id=project_id)
        )

    return tuple(results)

