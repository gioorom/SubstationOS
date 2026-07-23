from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import UNVERSIONED_CANONICAL_DOMAIN

if TYPE_CHECKING:
    from app.models.document import Document


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ENGINEERING = "engineering"
    CONSTRUCTION = "construction"
    COMMISSIONING = "commissioning"
    ENERGIZED = "energized"
    CLOSED = "closed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
        index=True,
    )

    customer: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    epc: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    voltage_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[ProjectStatus] = mapped_column(
        SqlEnum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.PLANNING,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    lifecycle_state: Mapped[ProjectLifecycleState] = mapped_column(
        SqlEnum(ProjectLifecycleState),
        nullable=False,
        default=ProjectLifecycleState.DRAFT,
    )

    canonical_domain_version: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default=UNVERSIONED_CANONICAL_DOMAIN,
    )

    created_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
    )