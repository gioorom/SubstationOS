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
    )

    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("project_entities.id"),
        nullable=False,
    )

    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("project_entities.id"),
        nullable=False,
    )

    relation_type: Mapped[RelationType] = mapped_column(
        SqlEnum(RelationType),
        nullable=False,
    )

    source_entity = relationship(
        "ProjectEntity",
        foreign_keys=[source_entity_id],
    )

    target_entity = relationship(
        "ProjectEntity",
        foreign_keys=[target_entity_id],
    )