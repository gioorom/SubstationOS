"""
The port Governed Structured Retrieval reads the governed graph through.

**There is no write method, and there is no room for one.** Retrieval
retrieves knowledge; it does not create it, approve it, or retire it.
Making that a property of the *interface* rather than a rule in a
document means a future handler cannot write the graph even by accident
- there is nothing on this port to call - and an architecture test
asserts the method set stays read-only.

This is deliberately **not** ``GovernedGraphRepository``. That port
carries ``upsert_node``, ``upsert_edge``, ``record_generation`` and
``clear``, all of which exist for promotion and none of which retrieval
may reach. Depending on it would make "retrieval never writes" a
convention; depending on this makes it a type.

---

## Why it returns ``GraphNode`` and ``GraphEdge``

Because they are already the right shape: immutable, typed, free of
property bags, and carrying mandatory provenance. Re-declaring a
parallel read model here would be ceremony that adds a mapping to
maintain and one more place for the two to disagree - and the governed
graph's own types are stable in a way ``graph_query``'s were not (they
projected a mutable property bag, which is exactly what retrieval had to
stop matching on).

Retrieval still owns its own **result** types
(``governed_retrieval_models``): the graph's types describe what is
stored, and the result types describe what was asked and why an answer
came back. Those are different concerns, and only the second is this
context's own vocabulary.

## Why states are a parameter and not a boolean

``include_historical=True`` reads as "and a bit more". A caller that
passes ``states=(ACTIVE, HISTORICAL)`` has written down exactly what it
is willing to answer an engineering question with, which is the decision
that matters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.governed_knowledge_graph.graph_generation import (
    GraphGeneration,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)


class GovernedKnowledgeReader(ABC):
    """
    Read-only access to the governed projection.

    Every implementation must return results in a **deterministic
    order**, independent of insertion order and of the database's own
    default sort. Retrieval sorts again for presentation, but a stable
    read order is what makes "two identical queries return identical
    results" true of the whole stack rather than only of the last step.
    """

    @abstractmethod
    def find_node(self, node_id: str) -> GraphNode | None:
        raise NotImplementedError

    @abstractmethod
    def find_edge(self, edge_id: str) -> GraphEdge | None:
        raise NotImplementedError

    @abstractmethod
    def nodes(
        self,
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphNodeKind | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> tuple[GraphNode, ...]:
        """
        Governed nodes in one scope, ordered by ``node_id``.

        Filtering is on **indexed, exact governed columns only** - kind,
        state, project, document. Designation matching is not a
        parameter here on purpose: it is a domain rule
        (``governed_matching``), and pushing it into SQL would make the
        result depend on a database's collation.
        """

        raise NotImplementedError

    @abstractmethod
    def nodes_by_identity(
        self, node_ids: tuple[str, ...]
    ) -> tuple[GraphNode, ...]:
        """
        The named nodes, ordered by ``node_id``.

        **State is not filtered.** Traversal resolves the endpoints of
        edges it has already selected, and hiding the far end of a
        governed relationship would produce a relationship with a
        missing side rather than an honest answer.
        """

        raise NotImplementedError

    @abstractmethod
    def edges(
        self,
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphEdgeKind | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> tuple[GraphEdge, ...]:
        """Governed relationships in one scope, ordered by ``edge_id``."""

        raise NotImplementedError

    @abstractmethod
    def edges_from_subjects(
        self,
        subject_node_ids: tuple[str, ...],
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphEdgeKind | None = None,
    ) -> tuple[GraphEdge, ...]:
        """
        The governed relationships these nodes are the **subject** of,
        ordered by ``edge_id``.

        Subject-only, and directional: ``has_rated_power`` relates an
        asset to a quantity in one direction, and answering "what are
        this quantity's assets?" from the same query would invert an
        engineering statement.
        """

        raise NotImplementedError

    @abstractmethod
    def latest_generation(self) -> GraphGeneration | None:
        """Which projection answered. ``None`` before the first rebuild."""

        raise NotImplementedError
