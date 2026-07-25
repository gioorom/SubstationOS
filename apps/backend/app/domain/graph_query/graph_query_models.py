from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class GraphNodeView:
    """
    Graph Query's own read-oriented projection of a persisted graph
    node - deliberately not a reuse of
    ``app.domain.project_knowledge_graph.graph_node_models.ProjectGraphNode``.
    Graph Query owns its own read model: it depends on the shared
    ``GraphEntityId`` vocabulary (already common between Graph Builder
    and Graph Persistence), never on Graph Persistence's own domain
    types or its ``GraphStore`` write port.
    """

    project_id: int
    graph_entity_id: GraphEntityId
    entity_type: str
    canonical_id: str
    properties: dict[str, str]
    created_at: datetime
    updated_at: datetime
    created_by_execution_id: int | None = None
    updated_by_execution_id: int | None = None


@dataclass(frozen=True, slots=True)
class GraphRelationshipView:
    """Graph Query's own read-oriented projection of a persisted graph
    relationship - see ``GraphNodeView``'s docstring for why this is not
    a reuse of Graph Persistence's own domain type."""

    project_id: int
    source_entity_id: GraphEntityId
    relationship_type: GraphRelationshipType
    target_entity_id: GraphEntityId
    properties: dict[str, str]
    created_at: datetime
    updated_at: datetime
    created_by_execution_id: int | None = None
    updated_by_execution_id: int | None = None


@dataclass(frozen=True, slots=True)
class GraphTraversalResult:
    """
    The general, direction-agnostic outcome of a bounded-depth traversal
    from one origin entity. ``depth`` is always ``1`` this milestone (no
    recursive traversal, no graph algorithms) - represented explicitly,
    as an actual field rather than an implicit assumption, so a future
    milestone could extend traversal depth without reshaping this type.
    """

    origin: GraphEntityId
    depth: int
    visited_nodes: tuple[GraphNodeView, ...]
    traversed_relationships: tuple[GraphRelationshipView, ...]


@dataclass(frozen=True, slots=True)
class GraphNeighborhood:
    """
    The direct (1-hop) neighborhood of one entity: the entity itself,
    every relationship one edge away (split by direction, since callers
    of the neighborhood query typically do care which way a
    relationship points - unlike the direction-agnostic
    ``GraphTraversalResult``), and the deduplicated set of neighbor
    nodes reached.
    """

    center: GraphNodeView
    outgoing: tuple[GraphRelationshipView, ...]
    incoming: tuple[GraphRelationshipView, ...]
    neighbors: tuple[GraphNodeView, ...]


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    """The full, read-only graph state of one project: every node and
    every relationship. Backs the ``project graph snapshot`` query
    capability; not exposed as its own API endpoint - the ``entities``
    and ``relationships`` endpoints already give a caller both halves."""

    project_id: int
    nodes: tuple[GraphNodeView, ...]
    relationships: tuple[GraphRelationshipView, ...]


@dataclass(frozen=True, slots=True)
class GraphStatistics:
    total_entities: int
    total_relationships: int
    entities_by_type: tuple[tuple[str, int], ...]
    relationships_by_type: tuple[tuple[str, int], ...]
    orphan_count: int


class GraphQueryKind(str, Enum):
    """Which deterministic query a ``GraphQuery`` describes - closed and
    exhaustive: every value here corresponds to one of this milestone's
    explicitly supported query types, never an open-ended free-text
    query shape."""

    ENTITY_BY_ID = "entity_by_id"
    ALL_ENTITIES = "all_entities"
    ENTITIES_BY_TYPE = "entities_by_type"
    ENTITIES_BY_ATTRIBUTE = "entities_by_attribute"
    OUTGOING_RELATIONSHIPS = "outgoing_relationships"
    INCOMING_RELATIONSHIPS = "incoming_relationships"
    NEIGHBORHOOD = "neighborhood"
    STATISTICS = "statistics"
    ORPHANS = "orphans"
    ALL_RELATIONSHIPS = "all_relationships"
    PROJECT_SNAPSHOT = "project_snapshot"


@dataclass(frozen=True, slots=True)
class GraphQuery:
    """What was asked: which deterministic query, against which
    project, and when. Carries no free-text or AI-interpretable
    content - every ``GraphQuery`` is one of a closed set of
    deterministic shapes (``GraphQueryKind``)."""

    project_id: int
    kind: GraphQueryKind
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class GraphQueryResult(Generic[T]):
    """
    The uniform envelope every Graph Query service function returns:
    what was asked (``query``) paired with the deterministic answer
    (``payload``) - the "Structured Query Result" this bounded
    context's pipeline produces. ``payload`` varies by query
    (a single ``GraphNodeView``, a tuple of views, ``GraphStatistics``,
    a ``GraphNeighborhood``, ...); the envelope around it never does.
    """

    query: GraphQuery
    payload: T
