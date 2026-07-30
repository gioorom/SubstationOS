"""
The domain events of the Governed Knowledge Graph.

Six, and they belong to **this** context. The pipeline does not emit
them, Human Review does not consume them, and nothing outside this
package constructs one.

Like the review context's events, these are **values rather than a
published stream**: they describe what a promotion run did, are returned
to the caller, and are written into the audit trail there. A subscriber,
a queue and a delivery guarantee would be infrastructure nothing in this
milestone needs - the promotion service already knows everything that
happened, because it is what made it happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.promotion_rules import (
    PromotionRefusal,
)


class GraphEventType(str, Enum):
    """The closed catalogue of things that happen to governed knowledge."""

    PROMOTED = "knowledge_promoted"
    HISTORICAL = "knowledge_historical"
    REMOVED = "knowledge_removed"
    REVALIDATED = "knowledge_revalidated"
    REBUILT = "graph_rebuilt"
    PROMOTION_FAILED = "promotion_failed"


@dataclass(frozen=True, slots=True)
class KnowledgePromoted:
    """An approved, applicable statement became a governed edge."""

    statement_key: str
    edge_id: str
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.PROMOTED


@dataclass(frozen=True, slots=True)
class KnowledgeHistorical:
    """
    Governed knowledge stopped being current.

    ``reason`` is the whole value of this event: "the graph shrank" is
    not actionable, "a rule change retired forty edges pending
    revalidation" is.
    """

    statement_key: str
    edge_id: str
    reason: GraphRetirementReason
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.HISTORICAL


@dataclass(frozen=True, slots=True)
class KnowledgeRemoved:
    """A rebuild found no promotable source for this identity at all."""

    edge_id: str
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.REMOVED


@dataclass(frozen=True, slots=True)
class KnowledgeRevalidated:
    """
    Retired knowledge became current again.

    A later review approved a statement whose edge had been retired. The
    edge is reactivated rather than recreated, so its identity - and
    every reference to it - survives the round trip.
    """

    statement_key: str
    edge_id: str
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.REVALIDATED


@dataclass(frozen=True, slots=True)
class GraphRebuilt:
    """
    The whole projection was recomputed.

    ``unchanged`` is the property a rebuild is *supposed* to have: a
    rebuild over the same pipeline and the same reviews produces the same
    graph. A rebuild reporting changes is either the first one, or a sign
    that something drifted - and either is worth seeing.
    """

    generation_number: int
    node_count: int
    edge_count: int
    unchanged: bool
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.REBUILT


@dataclass(frozen=True, slots=True)
class PromotionFailed:
    """
    A candidate could not be promoted.

    Emitted only for refusals that are **integrity problems** - an edge
    whose endpoints are the wrong kinds, a vocabulary gap. A statement
    nobody approved is not a failure and produces no event: it is the
    normal state of most statements, and an event per unreviewed
    statement would bury the ones that matter.
    """

    statement_key: str
    refusal: PromotionRefusal
    occurred_at: datetime
    event_type: GraphEventType = GraphEventType.PROMOTION_FAILED


GraphEvent = (
    KnowledgePromoted
    | KnowledgeHistorical
    | KnowledgeRemoved
    | KnowledgeRevalidated
    | GraphRebuilt
    | PromotionFailed
)

#: Refusals worth an event. Everything else is a statement waiting for a
#: reviewer, which is not news.
FAILURE_REFUSALS = frozenset(
    {
        PromotionRefusal.UNGOVERNED_STATEMENT_TYPE,
        PromotionRefusal.UNGOVERNED_ENTITY_TYPE,
        PromotionRefusal.INVALID_ENDPOINTS,
    }
)
