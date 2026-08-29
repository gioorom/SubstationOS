"""
Matching (the stage that decides *why* a governed object is an answer).

Pure functions over already-fetched governed nodes and edges. Nothing
here fetches, sorts, limits or classifies - the service owns reading and
``governed_result_assembly`` owns everything after a match is found.

**One object, one strategy.** A node whose label is exactly the
requested designation also matches the normalized and canonical folds,
and it is reported under the strongest strategy that held and under that
one only. "Why did this match?" has one answer, and it is the most
specific true one.

Matching operates exclusively on **typed governed fields** -
``label``, ``normalized_value``, ``kind``, ``state`` and the governed
identities. There is no property bag to match against and no field whose
meaning depends on which pipeline wrote it, which is the whole reason
the legacy matching strategies could not simply be repointed.
"""

from __future__ import annotations

from app.domain.governed_knowledge_graph.graph_models import GraphNode
from app.domain.governed_retrieval import governed_normalization
from app.domain.governed_retrieval.governed_match_policy import (
    DESIGNATION_STRATEGY_ORDER,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedMatchExplanation,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchStrategy,
)


def _holds(
    strategy: GovernedMatchStrategy, node: GraphNode, designation: str
) -> tuple[str, str] | None:
    """
    Whether one strategy matches, and the governed field that carried it.

    Returns ``(matched_field, matched_value)`` so the explanation names
    the column an engineer can go and read, never a paraphrase.
    """

    if strategy is GovernedMatchStrategy.EXACT_DESIGNATION:
        if node.label == designation:
            return ("label", node.label)

        return None

    if strategy is GovernedMatchStrategy.NORMALIZED_DESIGNATION:
        if governed_normalization.normalize_designation(
            node.label
        ) == governed_normalization.normalize_designation(designation):
            return ("label", node.label)

        return None

    if strategy is GovernedMatchStrategy.NORMALIZED_VALUE:
        if governed_normalization.normalize_designation(
            node.normalized_value
        ) == governed_normalization.normalize_designation(designation):
            return ("normalized_value", node.normalized_value)

        return None

    if strategy is GovernedMatchStrategy.CANONICAL_DESIGNATION:
        if governed_normalization.canonical_designation_key(
            node.label
        ) == governed_normalization.canonical_designation_key(designation):
            return ("label", node.label)

        return None

    return None


def match_designation(
    node: GraphNode, designation: str
) -> GovernedMatchExplanation | None:
    """
    The strongest designation strategy that holds for this node, or
    ``None`` if the node is not an answer to this designation.

    Deterministic and independent of the node's state: whether a
    historical node may answer is a **scope** decision the service makes
    when it reads, never a matching decision made here.
    """

    for strategy in DESIGNATION_STRATEGY_ORDER:
        matched = _holds(strategy, node, designation)

        if matched is None:
            continue

        matched_field, matched_value = matched

        return GovernedMatchExplanation(
            strategy=strategy,
            matched_field=matched_field,
            matched_value=matched_value,
            normalized_query=_normalized_query_for(strategy, designation),
        )

    return None


def _normalized_query_for(
    strategy: GovernedMatchStrategy, designation: str
) -> str:
    """The fold that was actually applied to the caller's own term."""

    if strategy is GovernedMatchStrategy.EXACT_DESIGNATION:
        return designation

    if strategy is GovernedMatchStrategy.CANONICAL_DESIGNATION:
        return governed_normalization.canonical_designation_key(designation)

    return governed_normalization.normalize_designation(designation)


def identity_match(
    matched_field: str, matched_value: str
) -> GovernedMatchExplanation:
    """The caller named this governed object's own id."""

    return GovernedMatchExplanation(
        strategy=GovernedMatchStrategy.GOVERNED_IDENTITY,
        matched_field=matched_field,
        matched_value=matched_value,
    )


def traversal_match(edge_id: str, edge_kind: str) -> GovernedMatchExplanation:
    """Reached by following one governed relationship."""

    return GovernedMatchExplanation(
        strategy=GovernedMatchStrategy.RELATIONSHIP_TRAVERSAL,
        matched_field=f"edge.{edge_kind}",
        matched_value=edge_id,
    )


def edge_kind_match(edge_kind: str) -> GovernedMatchExplanation:
    """Selected because it is a governed relationship of this kind."""

    return GovernedMatchExplanation(
        strategy=GovernedMatchStrategy.EDGE_KIND,
        matched_field="kind",
        matched_value=edge_kind,
    )


def document_scope_match(document_id: int) -> GovernedMatchExplanation:
    """Selected because its provenance names this document."""

    return GovernedMatchExplanation(
        strategy=GovernedMatchStrategy.DOCUMENT_SCOPE,
        matched_field="provenance.document_id",
        matched_value=str(document_id),
    )
