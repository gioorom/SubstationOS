"""
Result assembly: turning matched governed objects into an ordered,
classified, bounded answer.

Pure. Everything here is a function of already-fetched governed objects
and the match explanations ``governed_matching`` produced - no
repository, no clock, no configuration.

Three responsibilities, in this order:

1. **Build** an item from a governed node or edge, copying the labels
   that make an answer readable and referencing everything else by
   identity.
2. **Order** items by the documented sort key
   (``governed_match_policy``), which is total and never depends on
   insertion order.
3. **Classify and bound** - the outcome is computed from the count
   *before* the limit, so truncating a page can never turn several
   governed answers into one apparently certain one.
"""

from __future__ import annotations

from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
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
    GovernedMatchExplanation,
    GovernedNodeReference,
    GovernedProvenanceView,
    GovernedRelationshipReference,
    GovernedRetrievalItem,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedResultKind,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphNodeKind,
)

#: Which result kind a governed node produces. Total over
#: ``GraphNodeKind`` - a node kind missing here would be governed
#: knowledge retrieval could not report, so a test asserts completeness.
RESULT_KIND_FOR_NODE_KIND: dict[GraphNodeKind, GovernedResultKind] = {
    GraphNodeKind.ENGINEERING_ASSET: GovernedResultKind.ASSET,
    GraphNodeKind.ENGINEERING_QUANTITY: GovernedResultKind.QUANTITY,
    GraphNodeKind.STRUCTURAL_LOCATION: (
        GovernedResultKind.STRUCTURAL_LOCATION
    ),
}


def provenance_view(node_or_edge) -> GovernedProvenanceView:
    """Copies the governed provenance verbatim. Derives nothing."""

    provenance = node_or_edge.provenance

    return GovernedProvenanceView(
        statement_key=provenance.statement_key,
        document_id=provenance.document_id,
        content_checksum=provenance.content_checksum,
        review_id=provenance.review_id,
        reviewer_user_id=provenance.reviewer_user_id,
        reviewer_display_name=provenance.reviewer_display_name,
        reviewed_at=provenance.reviewed_at,
        semantic_rule_id=provenance.semantic_rule_id,
        semantic_rule_version=provenance.semantic_rule_version,
        semantic_contract_version=provenance.semantic_contract_version,
        resolution_policy_version=provenance.resolution_policy_version,
        fact_policy_version=provenance.fact_policy_version,
        semantic_policy_version=provenance.semantic_policy_version,
        support_fingerprint=provenance.support_fingerprint,
        project_id=provenance.project_id,
    )


def node_reference(node: GraphNode) -> GovernedNodeReference:
    return GovernedNodeReference(
        node_id=node.node_id.value,
        kind=node.kind,
        label=node.label,
        normalized_value=node.normalized_value,
        unit=node.unit,
    )


def node_item(
    node: GraphNode, match: GovernedMatchExplanation
) -> GovernedRetrievalItem:
    """One governed node, returned in its own right."""

    kind = RESULT_KIND_FOR_NODE_KIND[node.kind]
    reference = node_reference(node)

    return GovernedRetrievalItem(
        result_id=node_result_id(kind, reference.node_id),
        kind=kind,
        node=reference,
        relationship=None,
        state=node.state,
        retirement_reason=(
            None if node.retirement is None else node.retirement.reason
        ),
        match=match,
        provenance=provenance_view(node),
        sort_key=(
            precedence_of(match.strategy),
            normalize_designation(reference.label),
            "",
            reference.node_id,
        ),
    )


def traversed_node_item(
    node: GraphNode,
    edge: GraphEdge,
    subject: GraphNode,
    match: GovernedMatchExplanation,
) -> GovernedRetrievalItem:
    """
    One governed node reached by following a relationship from an asset.

    The relationship travels with it: "630 kVA" on its own is not an
    engineering answer, and a caller must never have to re-derive which
    asset it was asserted about.
    """

    kind = RESULT_KIND_FOR_NODE_KIND[node.kind]
    reference = node_reference(node)

    return GovernedRetrievalItem(
        result_id=traversed_node_result_id(
            kind, edge.edge_id.value, reference.node_id
        ),
        kind=kind,
        node=reference,
        relationship=GovernedRelationshipReference(
            edge_id=edge.edge_id.value,
            kind=edge.kind,
            subject=node_reference(subject),
            object=reference,
        ),
        state=edge.state,
        retirement_reason=(
            None if edge.retirement is None else edge.retirement.reason
        ),
        match=match,
        provenance=provenance_view(edge),
        sort_key=(
            precedence_of(match.strategy),
            normalize_designation(subject.label),
            normalize_designation(reference.label),
            edge.edge_id.value,
        ),
    )


def relationship_item(
    edge: GraphEdge,
    subject: GraphNode,
    object_node: GraphNode,
    match: GovernedMatchExplanation,
) -> GovernedRetrievalItem:
    """One governed relationship, with both endpoints resolved."""

    return GovernedRetrievalItem(
        result_id=relationship_result_id(edge.edge_id.value),
        kind=GovernedResultKind.RELATIONSHIP,
        node=None,
        relationship=GovernedRelationshipReference(
            edge_id=edge.edge_id.value,
            kind=edge.kind,
            subject=node_reference(subject),
            object=node_reference(object_node),
        ),
        state=edge.state,
        retirement_reason=(
            None if edge.retirement is None else edge.retirement.reason
        ),
        match=match,
        provenance=provenance_view(edge),
        sort_key=(
            precedence_of(match.strategy),
            normalize_designation(subject.label),
            normalize_designation(object_node.label),
            edge.edge_id.value,
        ),
    )


def order(
    items: tuple[GovernedRetrievalItem, ...],
) -> tuple[GovernedRetrievalItem, ...]:
    """
    The documented total order.

    ``sort_key`` ends in a governed identity, so no two items can
    compare equal and the order is fully determined by the graph's
    content rather than by the sort's stability.
    """

    return tuple(sorted(items, key=lambda item: item.sort_key))


def classify(total_before_limit: int) -> GovernedMatchOutcome:
    """
    How many governed objects satisfied the query.

    Computed from the pre-limit total on purpose: a caller must be able
    to tell "the graph holds one of these" from "the graph holds nine
    and you asked for one".
    """

    if total_before_limit == 0:
        return GovernedMatchOutcome.NO_MATCH

    if total_before_limit == 1:
        return GovernedMatchOutcome.UNIQUE_MATCH

    return GovernedMatchOutcome.MULTIPLE_MATCHES


def deduplicate(
    items: tuple[GovernedRetrievalItem, ...],
) -> tuple[GovernedRetrievalItem, ...]:
    """
    Collapses items that name the same governed object under the same
    strategy, keeping the first.

    Reachable when two resolved assets share one quantity node, or when a
    document query selects a node and one of its edges names the same
    node again. Deduplication is by ``result_id``, which is derived from
    governed identity - never by label, which would merge two
    transformers that share a name.
    """

    seen: dict[str, GovernedRetrievalItem] = {}

    for item in items:
        seen.setdefault(item.result_id, item)

    return tuple(seen.values())
