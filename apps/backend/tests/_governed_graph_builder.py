"""
Governed graph objects for tests that need knowledge without running the
whole pipeline (EPIC 31.2).

**Not a shortcut around governance.** Every object built here carries
complete provenance and is constructed through the same domain types
promotion uses, so a test cannot accidentally assert on a graph shape
that promotion could never produce. Tests that need to prove *governance
itself* - that a rejection retires knowledge, that a re-run orphans it -
drive the real pipeline and the real review API instead
(``tests/api/test_governed_retrieval_baseline.py``).

This builder exists for the other kind of test: the ones about
retrieval, ordering, ambiguity and projection, where the pipeline is not
the subject and running it would only make the test slower and harder to
read.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.governed_knowledge_graph.graph_identity import (
    edge_id_for,
    node_id_for,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirement,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_provenance import (
    GraphProvenance,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)

DEFAULT_CREATED_AT = datetime(2026, 1, 1, 5, 0, 0)


def governed_provenance(
    *,
    statement_key: str,
    document_id: int = 1,
    project_id: int | None = 1,
    review_id: int = 1,
    reviewer_display_name: str = "Ada Engineer",
    reviewed_at: datetime = DEFAULT_CREATED_AT,
    semantic_rule_version: str = "1.0",
) -> GraphProvenance:
    return GraphProvenance(
        statement_key=statement_key,
        document_id=document_id,
        content_checksum=f"checksum-{document_id}",
        review_id=review_id,
        reviewer_user_id=7,
        reviewer_display_name=reviewer_display_name,
        reviewed_at=reviewed_at,
        semantic_rule_id="rated_power_from_associated_quantity",
        semantic_rule_version=semantic_rule_version,
        semantic_contract_version="1.0",
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint=f"support-{statement_key}",
        project_id=project_id,
    )


def governed_asset(
    *,
    designation: str,
    entity_key: str | None = None,
    document_id: int = 1,
    project_id: int | None = 1,
    statement_key: str | None = None,
    state: GraphObjectState = GraphObjectState.ACTIVE,
    retirement_reason: GraphRetirementReason | None = None,
    created_at: datetime = DEFAULT_CREATED_AT,
) -> GraphNode:
    """
    One governed asset.

    ``entity_key`` defaults to a document-scoped key, so two documents
    that designate the same thing produce **two** nodes - the
    cross-document boundary the identity model requires, made the
    default rather than something a test has to remember.
    """

    key = entity_key or f"entity:{document_id}:{designation}"

    return GraphNode(
        node_id=node_id_for(GraphNodeKind.ENGINEERING_ASSET, key),
        kind=GraphNodeKind.ENGINEERING_ASSET,
        label=designation,
        normalized_value=designation.casefold(),
        unit=None,
        state=state,
        provenance=governed_provenance(
            statement_key=statement_key
            or f"statement:{document_id}:{designation}",
            document_id=document_id,
            project_id=project_id,
        ),
        created_at=created_at,
        retirement=(
            None
            if retirement_reason is None
            else GraphRetirement(
                reason=retirement_reason, retired_at=created_at
            )
        ),
    )


def governed_quantity(
    *,
    label: str = "630 kVA",
    normalized_value: str = "630.0",
    unit: str | None = "kVA",
    entity_key: str | None = None,
    document_id: int = 1,
    project_id: int | None = 1,
    statement_key: str | None = None,
    state: GraphObjectState = GraphObjectState.ACTIVE,
    created_at: datetime = DEFAULT_CREATED_AT,
) -> GraphNode:
    key = entity_key or f"quantity:{document_id}:{label}"

    return GraphNode(
        node_id=node_id_for(GraphNodeKind.ENGINEERING_QUANTITY, key),
        kind=GraphNodeKind.ENGINEERING_QUANTITY,
        label=label,
        normalized_value=normalized_value,
        unit=unit,
        state=state,
        provenance=governed_provenance(
            statement_key=statement_key or f"statement:{document_id}:{label}",
            document_id=document_id,
            project_id=project_id,
        ),
        created_at=created_at,
    )


def governed_edge(
    *,
    subject: GraphNode,
    object_node: GraphNode,
    statement_key: str,
    document_id: int = 1,
    project_id: int | None = 1,
    state: GraphObjectState = GraphObjectState.ACTIVE,
    retirement_reason: GraphRetirementReason | None = None,
    created_at: datetime = DEFAULT_CREATED_AT,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id_for(GraphEdgeKind.HAS_RATED_POWER, statement_key),
        kind=GraphEdgeKind.HAS_RATED_POWER,
        subject_node_id=subject.node_id.value,
        object_node_id=object_node.node_id.value,
        state=state,
        provenance=governed_provenance(
            statement_key=statement_key,
            document_id=document_id,
            project_id=project_id,
        ),
        created_at=created_at,
        retirement=(
            None
            if retirement_reason is None
            else GraphRetirement(
                reason=retirement_reason, retired_at=created_at
            )
        ),
    )


def governed_asset_with_quantity(
    *,
    designation: str,
    quantity_label: str = "630 kVA",
    # The declared quantity as the graph stores it: a bare decimal,
    # separate from the human label. Kept as its own parameter so a test
    # that needs two *different* governed values says so explicitly -
    # deriving it from the label would make a disagreement impossible to
    # express.
    quantity_value: str = "630.0",
    document_id: int = 1,
    project_id: int | None = 1,
    state: GraphObjectState = GraphObjectState.ACTIVE,
    created_at: datetime = DEFAULT_CREATED_AT,
) -> tuple[GraphNode, GraphNode, GraphEdge]:
    """The smallest complete piece of governed knowledge: an asset, a
    quantity, and the approved relationship between them."""

    statement_key = f"statement:{document_id}:{designation}:rated-power"

    asset = governed_asset(
        designation=designation,
        document_id=document_id,
        project_id=project_id,
        statement_key=statement_key,
        state=state,
        created_at=created_at,
    )
    quantity = governed_quantity(
        label=quantity_label,
        normalized_value=quantity_value,
        entity_key=f"quantity:{document_id}:{designation}:{quantity_label}",
        document_id=document_id,
        project_id=project_id,
        statement_key=statement_key,
        state=state,
        created_at=created_at,
    )
    edge = governed_edge(
        subject=asset,
        object_node=quantity,
        statement_key=statement_key,
        document_id=document_id,
        project_id=project_id,
        state=state,
        created_at=created_at,
    )

    return (asset, quantity, edge)
