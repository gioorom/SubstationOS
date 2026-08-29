"""
Application service for Governed Structured Retrieval (EPIC 31.2).

    GovernedRetrievalQuery
            |
       scope resolution        (which governed states may answer)
            |
       governed read           (GovernedKnowledgeReader - the only I/O)
            |
       matching                (governed_matching - pure)
            |
       assembly & ordering     (governed_result_assembly - pure)
            |
       GovernedRetrievalResult

The **only** module in this bounded context that performs I/O, and it
performs it through a port with no write method. Nothing here decides
whether knowledge is approved: the governed graph's promotion contract
already guarantees that an `ACTIVE` object was authorised by a review
that is currently `APPROVED` and whose applicability is `APPLIES`
(`promotion_rules`). Re-deriving that here would be a second governance
implementation, and the day the two disagreed neither would be
authoritative.

So this service reads `state`, and that is the whole of its governance
logic.

---

## What it refuses to do

- **No fallback.** A query that resolves no asset returns ``NO_MATCH``.
  It is never broadened to "everything in the project", because in this
  domain a confident answer about the wrong equipment is worse than an
  admitted gap - the same rule the Retrieval Bridge already follows.
- **No merging across documents.** Two governed assets that share a
  label are two answers, and the outcome says ``MULTIPLE_MATCHES``.
  Deciding they are the same transformer is cross-document entity
  resolution, which no governed rule performs.
- **No inference.** Nothing is derived, computed or completed. Every
  field on every item is copied from a governed row or is the reason it
  was selected.
"""

from __future__ import annotations

import time
from datetime import datetime

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphNodeKind,
)
from app.domain.governed_retrieval import (
    governed_matching,
    governed_result_assembly,
)
from app.domain.governed_retrieval.governed_knowledge_reader import (
    GovernedKnowledgeReader,
)
from app.domain.governed_retrieval.governed_match_policy import (
    DESIGNATION_STRATEGY_ORDER,
    GOVERNED_MATCHING_POLICY_VERSION,
)
from app.domain.governed_retrieval.governed_normalization import (
    GOVERNED_NORMALIZATION_VERSION,
    normalize_designation,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    AssetDesignationQuery,
    AssetQuantityQuery,
    DocumentKnowledgeQuery,
    GovernedGraphVersion,
    GovernedIdentityQuery,
    GovernedRetrievalDiagnostics,
    GovernedRetrievalItem,
    GovernedRetrievalQuery,
    GovernedRetrievalResult,
    RelationshipQuery,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedQueryType,
    RetrievalScope,
)

#: Which governed states each scope admits. The single definition -
#: every query shape reads it, so "historical never answers a current
#: question by default" is one line rather than a habit.
_STATES_FOR_SCOPE: dict[RetrievalScope, tuple[GraphObjectState, ...]] = {
    RetrievalScope.CURRENT_ONLY: (GraphObjectState.ACTIVE,),
    RetrievalScope.CURRENT_AND_HISTORICAL: (
        GraphObjectState.ACTIVE,
        GraphObjectState.HISTORICAL,
    ),
}


def retrieve(
    reader: GovernedKnowledgeReader,
    query: GovernedRetrievalQuery,
    *,
    now: datetime,
) -> GovernedRetrievalResult:
    """
    Executes one governed retrieval query.

    ``now`` is supplied by the caller rather than read from the clock, so
    the result is a pure function of the graph and the query except for
    the one timestamp that says when it was asked.
    """

    started = time.perf_counter()

    if isinstance(query, AssetDesignationQuery):
        matched, examined, strategies = _asset_by_designation(reader, query)
        normalized_query: str | None = normalize_designation(
            query.designation
        )
    elif isinstance(query, AssetQuantityQuery):
        matched, examined, strategies = _quantity_for_asset(reader, query)
        normalized_query = (
            None
            if query.designation is None
            else normalize_designation(query.designation)
        )
    elif isinstance(query, RelationshipQuery):
        matched, examined, strategies = _relationships(reader, query)
        normalized_query = None
    elif isinstance(query, DocumentKnowledgeQuery):
        matched, examined, strategies = _document_knowledge(reader, query)
        normalized_query = None
    else:
        matched, examined, strategies = _governed_identity(reader, query)
        normalized_query = None

    ordered = governed_result_assembly.order(
        governed_result_assembly.deduplicate(matched)
    )
    total_before_limit = len(ordered)
    limit = _limit_of(query)
    items = ordered[:limit]
    outcome = governed_result_assembly.classify(total_before_limit)

    diagnostics = GovernedRetrievalDiagnostics(
        query_type=query.query_type,
        scope=query.scope,
        normalized_query=normalized_query,
        strategies_attempted=strategies,
        candidates_examined=examined,
        matched_count=total_before_limit,
        returned_count=len(items),
        ambiguous=outcome is GovernedMatchOutcome.MULTIPLE_MATCHES,
        no_match=outcome is GovernedMatchOutcome.NO_MATCH,
        normalization_version=GOVERNED_NORMALIZATION_VERSION,
        matching_policy_version=GOVERNED_MATCHING_POLICY_VERSION,
        graph_version=_graph_version(reader),
        duration_seconds=time.perf_counter() - started,
    )

    return GovernedRetrievalResult(
        query=query,
        outcome=outcome,
        items=items,
        total_before_limit=total_before_limit,
        applied_limit=limit,
        diagnostics=diagnostics,
        retrieved_at=now,
    )


# --- Query shapes --------------------------------------------------------


def _asset_by_designation(
    reader: GovernedKnowledgeReader, query: AssetDesignationQuery
) -> tuple[
    tuple[GovernedRetrievalItem, ...], int, tuple[GovernedMatchStrategy, ...]
]:
    nodes = reader.nodes(
        states=_STATES_FOR_SCOPE[query.scope],
        kind=GraphNodeKind.ENGINEERING_ASSET,
        project_id=query.project_id,
        document_id=query.document_id,
    )

    items = tuple(
        governed_result_assembly.node_item(node, match)
        for node, match in _designation_matches(nodes, query.designation)
    )

    return (items, len(nodes), DESIGNATION_STRATEGY_ORDER)


def _quantity_for_asset(
    reader: GovernedKnowledgeReader, query: AssetQuantityQuery
) -> tuple[
    tuple[GovernedRetrievalItem, ...], int, tuple[GovernedMatchStrategy, ...]
]:
    """
    Resolves the asset, then follows its governed relationships.

    **Every** resolved asset is traversed, not just the first: two
    documents may each designate a ``TR1``, and answering with one of
    them would be the silent cross-document merge the identity model
    exists to refuse. The outcome reports the ambiguity instead.
    """

    subjects, examined, strategies = _resolve_subjects(reader, query)

    if not subjects:
        return ((), examined, strategies)

    by_id = {node.node_id.value: node for node in subjects}

    edges = reader.edges_from_subjects(
        tuple(by_id),
        states=_STATES_FOR_SCOPE[query.scope],
        kind=query.edge_kind,
    )

    objects = _nodes_by_id(reader, tuple(edge.object_node_id for edge in edges))

    items: list[GovernedRetrievalItem] = []

    for edge in edges:
        object_node = objects.get(edge.object_node_id)
        subject = by_id.get(edge.subject_node_id)

        if object_node is None or subject is None:
            # A governed edge whose endpoint is not readable is a
            # relationship this system cannot state honestly, so it is
            # left out rather than reported with a missing side. The
            # promotion contract makes it unreachable; leaving it
            # unhandled would mean discovering that the hard way.
            continue

        items.append(
            governed_result_assembly.traversed_node_item(
                object_node,
                edge,
                subject,
                governed_matching.traversal_match(
                    edge.edge_id.value, edge.kind.value
                ),
            )
        )

    return (
        tuple(items),
        examined + len(edges),
        strategies + (GovernedMatchStrategy.RELATIONSHIP_TRAVERSAL,),
    )


def _relationships(
    reader: GovernedKnowledgeReader, query: RelationshipQuery
) -> tuple[
    tuple[GovernedRetrievalItem, ...], int, tuple[GovernedMatchStrategy, ...]
]:
    edges = reader.edges(
        states=_STATES_FOR_SCOPE[query.scope],
        kind=query.edge_kind,
        project_id=query.project_id,
        document_id=query.document_id,
    )

    items = _relationship_items(
        reader,
        edges,
        lambda edge: governed_matching.edge_kind_match(edge.kind.value),
    )

    return (
        items,
        len(edges),
        (GovernedMatchStrategy.EDGE_KIND,),
    )


def _document_knowledge(
    reader: GovernedKnowledgeReader, query: DocumentKnowledgeQuery
) -> tuple[
    tuple[GovernedRetrievalItem, ...], int, tuple[GovernedMatchStrategy, ...]
]:
    """
    Everything the graph holds whose provenance names this document.

    Nodes **and** relationships: a document produces both, and reporting
    only one half would let "what did we learn from this drawing?"
    answer with assets nothing is asserted about.
    """

    states = _STATES_FOR_SCOPE[query.scope]
    match = governed_matching.document_scope_match(query.document_id)

    nodes = reader.nodes(
        states=states,
        project_id=query.project_id,
        document_id=query.document_id,
    )
    edges = reader.edges(
        states=states,
        project_id=query.project_id,
        document_id=query.document_id,
    )

    items = tuple(
        governed_result_assembly.node_item(node, match) for node in nodes
    ) + _relationship_items(reader, edges, lambda edge: match)

    return (
        items,
        len(nodes) + len(edges),
        (GovernedMatchStrategy.DOCUMENT_SCOPE,),
    )


def _governed_identity(
    reader: GovernedKnowledgeReader, query: GovernedIdentityQuery
) -> tuple[
    tuple[GovernedRetrievalItem, ...], int, tuple[GovernedMatchStrategy, ...]
]:
    strategies = (GovernedMatchStrategy.GOVERNED_IDENTITY,)
    states = _STATES_FOR_SCOPE[query.scope]

    if query.node_id is not None:
        node = reader.find_node(query.node_id)

        if node is None or node.state not in states:
            return ((), 0 if node is None else 1, strategies)

        return (
            (
                governed_result_assembly.node_item(
                    node,
                    governed_matching.identity_match(
                        "node_id", node.node_id.value
                    ),
                ),
            ),
            1,
            strategies,
        )

    edge = reader.find_edge(query.edge_id or "")

    if edge is None or edge.state not in states:
        return ((), 0 if edge is None else 1, strategies)

    items = _relationship_items(
        reader,
        (edge,),
        lambda selected: governed_matching.identity_match(
            "edge_id", selected.edge_id.value
        ),
    )

    return (items, 1, strategies)


# --- Shared steps --------------------------------------------------------


def _designation_matches(
    nodes: tuple[GraphNode, ...], designation: str
) -> list[tuple[GraphNode, object]]:
    matches = []

    for node in nodes:
        match = governed_matching.match_designation(node, designation)

        if match is not None:
            matches.append((node, match))

    return matches


def _resolve_subjects(
    reader: GovernedKnowledgeReader, query: AssetQuantityQuery
) -> tuple[tuple[GraphNode, ...], int, tuple[GovernedMatchStrategy, ...]]:
    """The asset(s) a quantity query is about - by identity or by
    designation, never by both (enforced at construction)."""

    if query.subject_node_id is not None:
        node = reader.find_node(query.subject_node_id)
        admitted = (
            ()
            if node is None
            or node.state not in _STATES_FOR_SCOPE[query.scope]
            or node.kind is not GraphNodeKind.ENGINEERING_ASSET
            else (node,)
        )

        return (
            admitted,
            0 if node is None else 1,
            (GovernedMatchStrategy.GOVERNED_IDENTITY,),
        )

    nodes = reader.nodes(
        states=_STATES_FOR_SCOPE[query.scope],
        kind=GraphNodeKind.ENGINEERING_ASSET,
        project_id=query.project_id,
        document_id=query.document_id,
    )

    return (
        tuple(
            node
            for node, _ in _designation_matches(
                nodes, query.designation or ""
            )
        ),
        len(nodes),
        DESIGNATION_STRATEGY_ORDER,
    )


def _relationship_items(
    reader: GovernedKnowledgeReader,
    edges: tuple[GraphEdge, ...],
    explain,
) -> tuple[GovernedRetrievalItem, ...]:
    endpoints = _nodes_by_id(
        reader,
        tuple(edge.subject_node_id for edge in edges)
        + tuple(edge.object_node_id for edge in edges),
    )

    items: list[GovernedRetrievalItem] = []

    for edge in edges:
        subject = endpoints.get(edge.subject_node_id)
        object_node = endpoints.get(edge.object_node_id)

        if subject is None or object_node is None:
            continue

        items.append(
            governed_result_assembly.relationship_item(
                edge, subject, object_node, explain(edge)
            )
        )

    return tuple(items)


def _nodes_by_id(
    reader: GovernedKnowledgeReader, node_ids: tuple[str, ...]
) -> dict[str, GraphNode]:
    return {
        node.node_id.value: node
        for node in reader.nodes_by_identity(node_ids)
    }


def _limit_of(query: GovernedRetrievalQuery) -> int:
    """An identity query returns one governed object, so it carries no
    limit field and needs none."""

    return 1 if isinstance(query, GovernedIdentityQuery) else query.limit


def _graph_version(
    reader: GovernedKnowledgeReader,
) -> GovernedGraphVersion:
    generation = reader.latest_generation()

    if generation is None:
        return GovernedGraphVersion(
            generation_number=None,
            generation_created_at=None,
            promotion_contract_version=None,
        )

    return GovernedGraphVersion(
        generation_number=generation.generation_number,
        generation_created_at=generation.created_at,
        promotion_contract_version=generation.promotion_contract_version,
    )


def explain(result: GovernedRetrievalResult) -> dict[str, str]:
    """
    A flat, deterministic explanation view: for every returned item, the
    strategy that put it there.

    Diagnostic information, not a natural-language explanation - the
    values are enum members, and nothing here is generated text.
    """

    return {
        item.result_id: item.match.strategy.value for item in result.items
    }


#: Every query type this service can execute. Used by the API and by an
#: architecture test that asserts the dispatch above stays exhaustive.
SUPPORTED_QUERY_TYPES: tuple[GovernedQueryType, ...] = tuple(
    GovernedQueryType
)
