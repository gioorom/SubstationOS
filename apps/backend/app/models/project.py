from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
    )