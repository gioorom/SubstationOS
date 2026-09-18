from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.project.project_document_scope import DocumentScope

if TYPE_CHECKING:
    from app.models.project import Project


class DocumentFormat(str, Enum):
    """
    The persisted format vocabulary. ``DXF`` and ``IMAGE`` were added in
    Milestone 25.2, when classification made them distinguishable - before
    that every document was stored as ``OTHER`` regardless.

    ``OTHER`` means **unclassified**, not "examined and found unusable".
    ``app.domain.document_identity.ClassifiedFormat`` is the domain's own
    restatement of this set; a test asserts the two agree.
    """

    PDF = "pdf"
    DWG = "dwg"
    DXF = "dxf"
    MODEL_3D = "model_3d"
    XLSX = "xlsx"
    DOCX = "docx"
    IMAGE = "image"
    OTHER = "other"


class DocumentCategory(str, Enum):
    FUNCTIONAL_SCHEMATIC = "functional_schematic"
    WIRING_TERMINAL = "wiring_terminal"
    GENERAL_TECHNICAL = "general_technical"
    CABLE_LIST = "cable_list"
    RELAY_SETTINGS = "relay_settings"
    COMMISSIONING_REPORT = "commissioning_report"
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    file_format: Mapped[DocumentFormat] = mapped_column(
        SqlEnum(DocumentFormat),
        nullable=False,
        default=DocumentFormat.OTHER,
    )

    category: Mapped[DocumentCategory] = mapped_column(
        SqlEnum(DocumentCategory),
        nullable=False,
        default=DocumentCategory.GENERAL_TECHNICAL,
    )

    revision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="00",
    )

    project_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="Unknown",
    )

    scope: Mapped[DocumentScope] = mapped_column(
        SqlEnum(DocumentScope),
        nullable=False,
        default=DocumentScope.PROJECT,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # ADR-0036. The document's own content identity, recorded when the
    # row is created and never updated afterwards. Together with ``id``
    # it is what the pipeline already calls this document's *version*:
    # every downstream stage refuses to build when its checksum and its
    # upstream's disagree.
    #
    # Nullable because a row created before this milestone has none, and
    # no migration may invent one - an identity a migration computed
    # would be a claim about bytes it never saw. ``NULL`` therefore means
    # *honestly unknown*, never "empty" and never "zero", and two of them
    # are never the same unknown.

    content_checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    content_checksum_algorithm: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    content_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    project: Mapped["Project | None"] = relationship(
        "Project",
        back_populates="documents",
    )