"""
The governed graph's nodes and edges.

Both are **projections**. Neither is a source of truth, both may always
be rebuilt from the pipeline and the reviews, and neither contains a
pipeline artefact - only its identity and its provenance.

A node carries a `label` because a query result has to be readable, and
the label is copied from the governed entity. **It is never identity**:
`node_id` derives from the entity key, and `graph_identity` explains at
length why using the label instead would silently merge two transformers
that happen to share a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.governed_knowledge_graph.graph_identity import (
    GraphEdgeId,
    GraphNodeId,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirement,
)
from app.domain.governed_knowledge_graph.graph_provenance import (
    GraphProvenance,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)


@dataclass(frozen=True, slots=True)
class GraphNode:
    """
    One governed engineering concept.

    ``label`` and ``normalized_value`` are copied from the entity for
    readability and lookup. ``unit`` is present only on a quantity, and
    is ``None`` on an asset - a field that is meaningful for one kind and
    absent for the other, rather than a shared bag of properties that
    would let a quantity acquire a designation.
    """

    node_id: GraphNodeId
    kind: GraphNodeKind
    label: str
    normalized_value: str
    unit: str | None
    state: GraphObjectState
    provenance: GraphProvenance
    created_at: datetime
    retirement: GraphRetirement | None = None

    @property
    def entity_key(self) -> str:
        return self.node_id.entity_key

    @property
    def is_current(self) -> bool:
        return self.state is GraphObjectState.ACTIVE

    def retired(
        self, retirement: GraphRetirement
    ) -> "GraphNode":
        """
        The same node, no longer current.

        A new value rather than a mutation - and the provenance is
        untouched, because *why the graph once believed this* does not
        change when it stops being current.
        """

        return GraphNode(
            node_id=self.node_id,
            kind=self.kind,
            label=self.label,
            normalized_value=self.normalized_value,
            unit=self.unit,
            state=GraphObjectState.HISTORICAL,
            provenance=self.provenance,
            created_at=self.created_at,
            retirement=retirement,
        )


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """
    One governed engineering relationship.

    **Never anonymous.** Every field the EPIC required is here and is
    mandatory at construction: the originating semantic statement, the
    review identity, the rule version, the pipeline (policy) versions,
    the support fingerprint and the creation timestamp - all of them on
    `provenance`, which cannot be omitted.
    """

    edge_id: GraphEdgeId
    kind: GraphEdgeKind
    subject_node_id: str
    object_node_id: str
    state: GraphObjectState
    provenance: GraphProvenance
    created_at: datetime
    retirement: GraphRetirement | None = None

    @property
    def statement_key(self) -> str:
        return self.edge_id.statement_key

    @property
    def is_current(self) -> bool:
        return self.state is GraphObjectState.ACTIVE

    def retired(self, retirement: GraphRetirement) -> "GraphEdge":
        return GraphEdge(
            edge_id=self.edge_id,
            kind=self.kind,
            subject_node_id=self.subject_node_id,
            object_node_id=self.object_node_id,
            state=GraphObjectState.HISTORICAL,
            provenance=self.provenance,
            created_at=self.created_at,
            retirement=retirement,
        )

    def reactivated(self) -> "GraphEdge":
        """
        Current again, because a later review approved it.

        The retirement is cleared rather than kept alongside: the object
        is current, and a stale reason on a current object is the kind of
        contradiction that makes a record untrustworthy. What happened is
        in the audit trail and in the review history, which are the
        append-only records.
        """

        return GraphEdge(
            edge_id=self.edge_id,
            kind=self.kind,
            subject_node_id=self.subject_node_id,
            object_node_id=self.object_node_id,
            state=GraphObjectState.ACTIVE,
            provenance=self.provenance,
            created_at=self.created_at,
            retirement=None,
        )
