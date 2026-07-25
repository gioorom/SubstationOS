from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecutionStatus,
)
from app.domain.project_knowledge_graph.graph_node_models import (
    GraphNodeProperties,
)
from app.domain.project_knowledge_graph.graph_relationship_models import (
    GraphRelationshipProperties,
)
from app.schemas.graph_builder import GraphEntityIdRead, GraphRelationshipTypeRead


def _properties_dict(value: object) -> object:
    if isinstance(value, (GraphNodeProperties, GraphRelationshipProperties)):
        return value.as_dict()

    return value


class ProjectGraphNodeRead(BaseModel):
    id: int
    project_id: int
    graph_entity_id: GraphEntityIdRead
    entity_type: str
    canonical_id: str
    properties: dict[str, str]
    created_by_execution_id: int | None
    updated_by_execution_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_properties = field_validator(
        "properties",
        mode="before",
    )(_properties_dict)


class ProjectGraphRelationshipRead(BaseModel):
    id: int
    project_id: int
    source_entity_id: GraphEntityIdRead
    relationship_type: GraphRelationshipTypeRead
    target_entity_id: GraphEntityIdRead
    properties: dict[str, str]
    created_by_execution_id: int | None
    updated_by_execution_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_properties = field_validator(
        "properties",
        mode="before",
    )(_properties_dict)


class GraphOperationExecutionResultRead(BaseModel):
    sequence: int
    kind: str
    succeeded: bool
    detail: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphExecutionRead(BaseModel):
    id: int
    batch_id: int
    batch_fingerprint: str
    project_id: int
    status: GraphExecutionStatus
    started_at: datetime
    completed_at: datetime | None
    operation_count: int
    failure_type: str | None
    failure_message: str | None
    operation_results: list[GraphOperationExecutionResultRead]

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphExecutionResultRead(BaseModel):
    execution: GraphExecutionRead
    created: bool

    model_config = ConfigDict(
        from_attributes=True,
    )
