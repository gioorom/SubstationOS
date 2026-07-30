"""
The port the governed graph is written and read through.

Unlike Human Review's port, this one **does** declare mutating
operations - and that is correct rather than inconsistent. Reviews are a
record of what somebody decided and must never change. The graph is a
*projection* of those records: it is derived, it is rebuildable, and
keeping it in step with its sources means changing it.

What the port does **not** offer is any way to write knowledge that did
not come from a promotion. There is no `create_node(label=…)`, no
`add_edge(subject, object)` and no property setter. Every write here
takes an object the promotion service built from a governed statement and
an approving review, which is what makes "no other source may insert
engineering knowledge" a property of the interface rather than a promise.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.governed_knowledge_graph.graph_generation import (
    GraphGeneration,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.shared_kernel.pagination import Page, PageRequest


class GovernedGraphRepository(ABC):
    """Stores and reads the governed projection."""

    # --- Writing, only from promotions -----------------------------------

    @abstractmethod
    def upsert_node(self, node: GraphNode) -> GraphNode:
        """
        Stores a node, or updates the one with this identity.

        **Idempotent by identity**: promoting the same entity twice
        produces one node, which is the whole of the duplicate-prevention
        guarantee. The identity comes from the entity key, so "the same
        entity" is decided by the pipeline rather than by comparing
        labels.
        """

        raise NotImplementedError

    @abstractmethod
    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        """Stores an edge, or updates the one with this identity."""

        raise NotImplementedError

    @abstractmethod
    def record_generation(
        self, generation: GraphGeneration
    ) -> GraphGeneration:
        """Appends one rebuild record. Never updated."""

        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        Discards the whole projection.

        Only a rebuild calls this, and it is safe **only** because the
        graph is derived: everything it drops is reproducible from the
        pipeline and the reviews. Nothing else in this system has an
        operation like it, and nothing else may.
        """

        raise NotImplementedError

    # --- Reading ---------------------------------------------------------

    @abstractmethod
    def find_node(self, node_id: str) -> GraphNode | None:
        raise NotImplementedError

    @abstractmethod
    def find_edge(self, edge_id: str) -> GraphEdge | None:
        raise NotImplementedError

    @abstractmethod
    def find_edge_by_statement(
        self, statement_key: str
    ) -> GraphEdge | None:
        """
        The edge one semantic statement produced.

        The lookup incremental promotion uses to decide between creating,
        reactivating and retiring - and the one the Workspace uses to
        answer "is this statement in the graph?".
        """

        raise NotImplementedError

    @abstractmethod
    def list_nodes(
        self,
        *,
        page: PageRequest,
        kind: str | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
        label_search: str | None = None,
        include_historical: bool = False,
    ) -> Page[GraphNode]:
        """
        One page of nodes.

        ``label_search`` searches the **stored label of a governed
        entity**, which is a projection of pipeline output and not a
        similarity match: it finds nodes whose label contains the term,
        and it never decides that two nodes are the same thing.

        ``include_historical`` defaults to false, so a query answers with
        current governed knowledge unless a caller deliberately asks for
        what the graph used to assert.
        """

        raise NotImplementedError

    @abstractmethod
    def list_edges(
        self,
        *,
        page: PageRequest,
        kind: str | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
        include_historical: bool = False,
    ) -> Page[GraphEdge]:
        raise NotImplementedError

    @abstractmethod
    def edges_for_node(
        self, node_id: str, *, include_historical: bool = False
    ) -> tuple[GraphEdge, ...]:
        """
        Every relationship one node participates in, either end.

        Ordered deterministically, so two reads of the same graph return
        the same list - which is what lets a query result be attached to
        an engineering query.
        """

        raise NotImplementedError

    @abstractmethod
    def all_edges(self) -> tuple[GraphEdge, ...]:
        """
        Every edge, current and historical, ordered by identity.

        Used by reconciliation and by the rebuild-determinism check.
        Deliberately unpaged: a caller comparing two whole projections
        needs both whole.
        """

        raise NotImplementedError

    @abstractmethod
    def all_nodes(self) -> tuple[GraphNode, ...]:
        raise NotImplementedError

    @abstractmethod
    def latest_generation(self) -> GraphGeneration | None:
        raise NotImplementedError

    @abstractmethod
    def count_active(self) -> tuple[int, int]:
        """``(nodes, edges)`` currently answering queries."""

        raise NotImplementedError
