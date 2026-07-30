"""
What "graph version" means.

The EPIC asked for graph version, generation timestamp, pipeline version,
review policy version, semantic rule version and promotion version. Those
live in **two different places**, and the split is the point:

| Version | Where | Why |
|---|---|---|
| Graph generation number | Here | One per rebuild. Global. |
| Generation timestamp | Here | When the rebuild ran. Global. |
| Promotion contract version | Here | Which promotion rules admitted the knowledge. Global. |
| Semantic rule and version | On each edge's `provenance` | **Differs per object.** Two edges in one graph can come from two rule versions. |
| Resolution / fact / semantic policy versions | On each edge's `provenance` | Same reason. |
| Content checksum | On each edge's `provenance` | Same reason - one graph spans many documents. |

Putting the per-object versions on the generation would be recording a
single value for something that genuinely varies, which is how a version
field becomes a lie. Asking "which rule versions is this graph built
from?" is a query over provenance, and it can return several - because
the honest answer sometimes is several.

---

## What a generation is

**One rebuild.** Incremental promotions attach to the current generation
rather than starting a new one: a generation says "this is the projection
as recomputed from scratch at this moment, under these promotion rules",
and an incremental promotion does not change the rules or recompute the
whole thing.

A generation is an immutable record, appended. Rebuilding twice produces
two generations whose *content* is identical - which is the property
`rebuild determinism` asserts - and two generation rows, because they
happened at different times.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.governed_knowledge_graph.promotion_rules import (
    PROMOTION_CONTRACT_VERSION,
)


class GraphGenerationTrigger(str, Enum):
    """Why this generation exists."""

    #: The whole projection was recomputed from the pipeline and the
    #: reviews. The only trigger that creates a generation.
    REBUILD = "rebuild"

    #: The first generation, created when the graph is first written to.
    INITIAL = "initial"


@dataclass(frozen=True, slots=True)
class GraphGeneration:
    """
    One recomputation of the whole projection.

    ``node_count``/``edge_count`` are the **active** counts at the moment
    the generation completed. They are a snapshot for operators, never a
    source the graph reads back - counting is a query.
    """

    generation_id: int | None
    generation_number: int
    trigger: GraphGenerationTrigger
    promotion_contract_version: str
    created_at: datetime
    node_count: int
    edge_count: int

    #: Who rebuilt it. ``None`` for the initial generation, which is
    #: created by the first promotion rather than by a person.
    actor_user_id: int | None = None

    @classmethod
    def of_rebuild(
        cls,
        *,
        generation_number: int,
        created_at: datetime,
        node_count: int,
        edge_count: int,
        actor_user_id: int | None,
    ) -> "GraphGeneration":
        return cls(
            generation_id=None,
            generation_number=generation_number,
            trigger=GraphGenerationTrigger.REBUILD,
            promotion_contract_version=PROMOTION_CONTRACT_VERSION,
            created_at=created_at,
            node_count=node_count,
            edge_count=edge_count,
            actor_user_id=actor_user_id,
        )
