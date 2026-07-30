"""
The public Governed Knowledge Graph contract.

**Every response carries provenance.** There is no node schema and no
edge schema without it, so an API consumer cannot receive a graph answer
it is unable to trace back to the statement, the review, the rules and
the document it came from. That is the difference between this and a
property graph, expressed in the contract rather than in prose.

Nothing here carries a semantic statement, a fact, an entity or a piece
of evidence. The graph names governed artefacts by key and records their
identity; what they *said* is read from the engineering endpoints, which
stay their single account.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.governed_knowledge_graph.graph_generation import (
    GraphGenerationTrigger,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_knowledge_graph.promotion_rules import (
    PromotionRefusal,
)
from app.schemas.pagination import PageMetadata

# --- Provenance ----------------------------------------------------------


class GraphProvenanceRead(BaseModel):
    """
    Where one piece of governed knowledge came from.

    Mandatory on every node and every edge. Identity only - which
    statement, which review, which rules, which bytes - never the
    artefacts themselves.
    """

    statement_key: str
    document_id: int
    project_id: int | None
    content_checksum: str

    review_id: int
    reviewer_user_id: int
    reviewer_display_name: str
    reviewed_at: datetime

    semantic_rule_id: str
    semantic_rule_version: str
    semantic_contract_version: str
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    support_fingerprint: str

    model_config = ConfigDict(from_attributes=True)


class GraphRetirementRead(BaseModel):
    """Why knowledge stopped being current."""

    reason: GraphRetirementReason
    retired_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Nodes and edges -----------------------------------------------------


class GraphNodeRead(BaseModel):
    """
    One governed engineering concept.

    ``label`` is readable and is **never identity**: `node_id` derives
    from the governed entity key. Two nodes may legitimately share a
    label - see `knowledge_graph.md` on cross-document entity resolution.
    """

    node_id: str
    kind: GraphNodeKind
    entity_key: str
    label: str
    normalized_value: str
    unit: str | None
    state: GraphObjectState
    created_at: datetime
    retirement: GraphRetirementRead | None
    provenance: GraphProvenanceRead

    @classmethod
    def of(cls, node: GraphNode) -> "GraphNodeRead":
        return cls(
            node_id=node.node_id.value,
            kind=node.kind,
            entity_key=node.node_id.entity_key,
            label=node.label,
            normalized_value=node.normalized_value,
            unit=node.unit,
            state=node.state,
            created_at=node.created_at,
            retirement=(
                None
                if node.retirement is None
                else GraphRetirementRead.model_validate(node.retirement)
            ),
            provenance=GraphProvenanceRead.model_validate(node.provenance),
        )


class GraphEdgeRead(BaseModel):
    """One governed engineering relationship. Never anonymous."""

    edge_id: str
    kind: GraphEdgeKind
    statement_key: str
    subject_node_id: str
    object_node_id: str
    state: GraphObjectState
    created_at: datetime
    retirement: GraphRetirementRead | None
    provenance: GraphProvenanceRead

    @classmethod
    def of(cls, edge: GraphEdge) -> "GraphEdgeRead":
        return cls(
            edge_id=edge.edge_id.value,
            kind=edge.kind,
            statement_key=edge.edge_id.statement_key,
            subject_node_id=edge.subject_node_id,
            object_node_id=edge.object_node_id,
            state=edge.state,
            created_at=edge.created_at,
            retirement=(
                None
                if edge.retirement is None
                else GraphRetirementRead.model_validate(edge.retirement)
            ),
            provenance=GraphProvenanceRead.model_validate(edge.provenance),
        )


class GraphNodeListResponse(BaseModel):
    items: tuple[GraphNodeRead, ...]
    pagination: PageMetadata


class GraphEdgeListResponse(BaseModel):
    items: tuple[GraphEdgeRead, ...]
    pagination: PageMetadata


class RelatedNodeRead(BaseModel):
    """
    One relationship, from the point of view of a node.

    ``direction`` says which end this node is on, so a caller reading
    "TR1's relationships" can tell "TR1 has rated power X" from a
    relationship pointing the other way - without re-deriving it from the
    two node ids.
    """

    edge: GraphEdgeRead
    direction: str = Field(
        description="`outgoing` when this node is the subject, "
        "`incoming` when it is the object."
    )
    other_node: GraphNodeRead | None


class GraphNodeDetailResponse(BaseModel):
    """
    One node, everything asserted about it, and why.

    The answer to "find the rated power of TR1" and to "explain this
    answer" is the same response: the relationships are here, and each
    carries its own provenance.
    """

    node: GraphNodeRead
    relationships: tuple[RelatedNodeRead, ...]


# --- Promotion -----------------------------------------------------------


class PromotionEventRead(BaseModel):
    """One thing a promotion run did."""

    event_type: str
    statement_key: str | None
    edge_id: str | None
    reason: str | None
    refusal: PromotionRefusal | None


class PromotionResultResponse(BaseModel):
    """
    What a promotion run did.

    The counts and the events describe the same run; the events are the
    account, the counts are a summary of them rather than a separate
    tally that could drift.
    """

    promoted: int
    retired: int
    revalidated: int
    failed: int
    events: tuple[PromotionEventRead, ...]


class GraphGenerationRead(BaseModel):
    """
    One recomputation of the whole projection.

    Carries the versions that are **global**. The semantic rule and
    policy versions are deliberately absent: they differ per object and
    live on each edge's provenance, because one graph can legitimately
    span several rule versions and a single field here would be a lie.
    """

    generation_number: int
    trigger: GraphGenerationTrigger
    promotion_contract_version: str
    created_at: datetime
    node_count: int
    edge_count: int
    actor_user_id: int | None

    model_config = ConfigDict(from_attributes=True)


class RebuildResultResponse(BaseModel):
    result: PromotionResultResponse
    generation: GraphGenerationRead


class GraphStatusResponse(BaseModel):
    """What the graph currently holds."""

    active_nodes: int
    active_edges: int
    latest_generation: GraphGenerationRead | None
    promotion_contract_version: str


class GraphVocabularyResponse(BaseModel):
    """
    What the graph is allowed to contain.

    Served rather than duplicated in clients, and deliberately small: two
    node kinds and one edge kind, because that is what governed semantics
    produces today. `knowledge_graph.md` lists what each further concept
    would need upstream first.
    """

    node_kinds: tuple[GraphNodeKind, ...]
    edge_kinds: tuple[GraphEdgeKind, ...]
    node_kind_for_entity_type: dict[str, GraphNodeKind]
    edge_kind_for_statement_type: dict[str, GraphEdgeKind]
    promotion_contract_version: str


class StatementPromotionRead(BaseModel):
    """
    Whether one semantic statement is in the graph, and why or why not.

    What the Workspace asks per statement. ``refusal`` is populated when
    the statement is not promoted, so the panel can say *why* rather than
    only that it is absent.
    """

    statement_key: str
    promoted: bool
    refusal: PromotionRefusal | None
    edge: GraphEdgeRead | None
