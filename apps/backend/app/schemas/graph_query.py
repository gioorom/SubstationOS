from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.graph_builder import GraphEntityIdRead, GraphRelationshipTypeRead


class GraphNodeViewRead(BaseModel):
    project_id: int
    graph_entity_id: GraphEntityIdRead
    entity_type: str
    canonical_id: str
    properties: dict[str, str]
    created_at: datetime
    updated_at: datetime
    created_by_execution_id: int | None = None
    updated_by_execution_id: int | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphRelationshipViewRead(BaseModel):
    project_id: int
    source_entity_id: GraphEntityIdRead
    relationship_type: GraphRelationshipTypeRead
    target_entity_id: GraphEntityIdRead
    properties: dict[str, str]
    created_at: datetime
    updated_at: datetime
    created_by_execution_id: int | None = None
    updated_by_execution_id: int | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphNeighborhoodRead(BaseModel):
    center: GraphNodeViewRead
    outgoing: list[GraphRelationshipViewRead]
    incoming: list[GraphRelationshipViewRead]
    neighbors: list[GraphNodeViewRead]

    model_config = ConfigDict(
        from_attributes=True,
    )


def _type_count_dict(value: object) -> object:
    """``GraphStatistics.entities_by_type``/``relationships_by_type``
    are tuples of ``(type, count)`` pairs, kept sorted and hashable in
    the domain layer - unwrap to a plain mapping for the API."""

    if isinstance(value, tuple):
        return dict(value)

    return value


class GraphStatisticsRead(BaseModel):
    total_entities: int
    total_relationships: int
    entities_by_type: dict[str, int]
    relationships_by_type: dict[str, int]
    orphan_count: int

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_entities_by_type = field_validator(
        "entities_by_type",
        mode="before",
    )(_type_count_dict)
    _unwrap_relationships_by_type = field_validator(
        "relationships_by_type",
        mode="before",
    )(_type_count_dict)
