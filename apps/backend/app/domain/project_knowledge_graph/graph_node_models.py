from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.graph_builder.graph_builder_models import GraphEntityId


@dataclass(frozen=True, slots=True)
class GraphNodeProperties:
    """
    An immutable, deterministically ordered property bag for one
    ``ProjectGraphNode``. Backed by a tuple of ``(key, value)`` pairs,
    always kept sorted by key, so two properties objects with the same
    content are always equal and always serialize identically -
    required for the batch execution fingerprint and for predictable
    API responses.
    """

    values: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)

    def merged_with(self, attribute: str, value: str) -> GraphNodeProperties:
        """
        Returns a new ``GraphNodeProperties`` with ``attribute`` set to
        ``value``: overwrites the prior value for the same key if one
        existed, preserves every other key, and never produces a
        duplicate key.
        """

        merged = dict(self.values)
        merged[attribute] = value

        return GraphNodeProperties(values=tuple(sorted(merged.items())))


@dataclass(frozen=True, slots=True)
class ProjectGraphNode:
    """
    One node in a Project Knowledge Graph: the persisted, executed
    counterpart of a Graph Builder ``GraphNodeOperation``. Its natural
    key is ``(project_id, graph_entity_id)`` - ``id`` is a storage
    detail, never the identity a caller reasons about or that another
    node/relationship references.

    ``created_by_execution_id``/``updated_by_execution_id`` are
    provenance only: which ``GraphExecution`` first created this node,
    and which last changed it. Per this milestone's constraints, no
    ``CanonicalFact`` or ``ProposedClaim`` content is copied here -
    tracing back further than the execution id is a query into
    Canonicalization's/Proposed Claims' own persistence, not this
    bounded context's job.
    """

    id: int | None
    project_id: int
    graph_entity_id: GraphEntityId
    entity_type: str
    canonical_id: str
    properties: GraphNodeProperties
    created_by_execution_id: int | None
    updated_by_execution_id: int | None
    created_at: datetime
    updated_at: datetime
