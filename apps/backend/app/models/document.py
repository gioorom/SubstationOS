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

    # A document id is not reused after a row is removed - while the
    # schema stays at or above the revision that added this. A downgrade
    # and re-upgrade resets the high-water mark SQLite keeps, which the
    # migration records as a known, reproduced defect it deliberately
    # does not fix.
    #
    # Without this, SQLite assigns ``max(id) + 1``, so deleting the
    # highest-numbered document hands its id to the next upload. That
    # upload then inherits the deleted document's ingestion jobs and the
    # rows in the twelve tables that reference ``documents.id`` - a new
    # file silently acquiring another document's provenance.
    #
    # No code path deletes a document, and since the cascade came off
    # ``Project.documents`` none can. This guards the case that remains:
    # a row removed by hand, in a database, by someone fixing something
    # else.
    #
    # **Any migration that rebuilds this table must repeat it.** Alembic's
    # batch mode reflects a table to recreate it, and reflection does not
    # carry ``sqlite_autoincrement``; ``--autogenerate`` will not emit it
    # either. ``alter_column`` and ``drop_column`` choose a rebuild on
    # their own, so an ordinary migration that never mentions ids can
    # remove this guard in passing. Pass
    # ``table_kwargs={"sqlite_autoincrement": True}`` to any
    # ``batch_alter_table("documents", ...)`` that recreates.
    # ``tests/infrastructure/test_the_migration_chain_protects_document_ids.py``
    # runs the chain and fails if the keyword is gone.
    #
    # **Repeating the keyword restores the keyword, not the mark.** A
    # rebuild reseeds SQLite's counter from the highest *surviving*
    # row, so every id spent on a document that has since been removed
    # is handed out again - with ``AUTOINCREMENT`` present and that
    # test green. A future rebuild therefore has the same effect as
    # the downgrade named above, and there is no cheap way to carry
    # the mark across one: writing it needs a data statement, which
    # ``test_no_migration_fabricates_an_identity`` forbids.
    __table_args__ = {"sqlite_autoincrement": True}

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
    # it is what the pipeline already calls this document's *version*.
    #
    # Each derived stage does refuse to build when its checksum and its
    # *upstream artefact's* disagree - but nothing compares either of
    # them to the value recorded here, so a representation derived from
    # bytes that changed on disk is bound to those bytes while this row
    # still names the ones uploaded. ADR-0036 §18 says the discrepancy
    # is detectable, not that anything detects it; an earlier version of
    # this comment promised a refusal that does not exist.
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
