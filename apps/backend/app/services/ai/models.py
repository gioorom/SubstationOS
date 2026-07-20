from dataclasses import dataclass, field
from typing import Any

from app.models.knowledge_graph import EntityType


@dataclass
class ExtractedEntity:
    entity_type: EntityType
    name: str
    confidence: float = 1.0
    description: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedRelation:
    source: str
    relation: str
    target: str
    confidence: float = 1.0


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)