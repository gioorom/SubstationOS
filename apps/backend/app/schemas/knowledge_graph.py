from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.knowledge_graph import (
    EntityType,
    RelationType,
)


class KnowledgeGraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    entity_type: EntityType
    name: str
    description: str | None = None
    source_document: str | None = None
    created_at: datetime


class KnowledgeGraphEdge(BaseModel):
    id: int
    source: int
    target: int
    relation_type: RelationType


class KnowledgeGraphResponse(BaseModel):
    project_id: int
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]


class EntityDetailResponse(KnowledgeGraphNode):
    related_entities: list[KnowledgeGraphNode]