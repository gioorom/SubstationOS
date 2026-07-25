"""
LEGACY - pre-dates the governed knowledge pipeline (Engineering Index ->
Proposed Claims -> Review Workflow -> Canonicalization -> Graph Builder ->
Project Knowledge Graph -> Graph Query, see
docs/architecture/knowledge_pipeline_overview.md). ``ProjectEntity``/
``EntityRelation`` are written directly by
``app.services.knowledge_graph.ingest_document`` with no review gate -
a live, tracked violation of ADR-0004, not a design this module claims
to be correct.

Still referenced (do not delete): ``app.routers.documents.upload_document``
calls ``ingest_document`` on every PDF upload to a project;
``app.routers.knowledge_graph`` serves reads from these tables. See
ADR-0009 (Legacy Knowledge Graph Isolation) for the full inventory and
the isolation rule this module is governed by:

No governed bounded context (Engineering Index, Proposed Claims, Review
Workflow, Canonicalization, Graph Builder, Project Knowledge Graph, Graph
Query) may import anything from this module. Enforced by
tests/architecture/test_bounded_context_dependencies.py.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class EntityType(str, Enum):
    SUBSTATION = "substation"
    BAY = "bay"
    PANEL = "panel"
    CIRCUIT_BREAKER = "circuit_breaker"
    DISCONNECTOR = "disconnector"
    TRANSFORMER = "transformer"
    CURRENT_TRANSFORMER = "current_transformer"
    VOLTAGE_TRANSFORMER = "voltage_transformer"
    PROTECTION_RELAY = "protection_relay"
    CABLE = "cable"
    SIGNAL = "signal"
    DOCUMENT = "document"
    TEST = "test"
    OTHER = "other"
    BUSBAR = "busbar"
    LINE = "line"


class RelationType(str, Enum):
    BELONGS_TO = "belongs_to"
    CONNECTED_TO = "connected_to"
    PROTECTED_BY = "protected_by"
    DOCUMENTED_IN = "documented_in"
    TESTED_BY = "tested_by"
    PART_OF = "part_of"
    OTHER = "other"


class ProjectEntity(Base):
    __tablename__ = "project_entities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[EntityType] = mapped_column(
        SqlEnum(EntityType),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Nuovo campo per gli attributi dinamici dell'entità
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    source_document: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")


class EntityRelation(Base):
    __tablename__ = "entity_relations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("project_entities.id"),
        nullable=False,
        index=True,
    )

    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("project_entities.id"),
        nullable=False,
        index=True,
    )

    relation_type: Mapped[RelationType] = mapped_column(
        SqlEnum(RelationType),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )

    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    source_document: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project")

    source_entity = relationship(
        "ProjectEntity",
        foreign_keys=[source_entity_id],
    )

    target_entity = relationship(
        "ProjectEntity",
        foreign_keys=[target_entity_id],
    )