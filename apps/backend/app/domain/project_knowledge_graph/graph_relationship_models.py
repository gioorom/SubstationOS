from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)


@dataclass(frozen=True, slots=True)
class GraphRelationshipProperties:
    """
    An immutable, deterministically ordered property bag for one
    ``ProjectGraphRelationship`` - shaped identically to
    ``GraphNodeProperties`` for the same reasons. Always empty in this
    milestone: only ``CREATE_RELATIONSHIP`` is executed, and Graph
    Builder's ``GraphRelationshipOperation`` carries no properties to
    set. Present now so ``UPDATE_RELATIONSHIP`` (defined, not yet
    executed) has somewhere to write to without a later schema change.
    """

    values: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)


@dataclass(frozen=True, slots=True)
class ProjectGraphRelationship:
    """
    One relationship in a Project Knowledge Graph: the persisted,
    executed counterpart of a Graph Builder ``GraphRelationshipOperation``.
    Its natural key is
    ``(project_id, source_entity_id, relationship_type, target_entity_id)``.
    Both endpoints must already exist as ``ProjectGraphNode``s in the
    same project - enforced by ``GraphStore.upsert_relationship``, not
    assumed here.
    """

    id: int | None
    project_id: int
    source_entity_id: GraphEntityId
    relationship_type: GraphRelationshipType
    target_entity_id: GraphEntityId
    properties: GraphRelationshipProperties
    created_by_execution_id: int | None
    updated_by_execution_id: int | None
    created_at: datetime
    updated_at: datetime
