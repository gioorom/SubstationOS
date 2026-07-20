from dataclasses import dataclass, field
from typing import Any
from app.models.knowledge_graph import (
    EntityType,
    RelationType,
)


@dataclass
class ExtractedEntity:
    entity_type: EntityType
    name: str
    confidence: float = 1.0
    description: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedRelationship:
    source: str
    target: str

    relation_type: RelationType

    confidence: float = 1.0

    description: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)

    relationships: list[ExtractedRelationship] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)