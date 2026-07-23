from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)


class EngineeringIndexEntry(Base):
    """
    Persistence model for one Engineering Index candidate mention
    (docs/architecture/project_intelligence_architecture.md §5). Kept
    deliberately flat and free of any relationship column: the Index
    records mentions, never typed relationships between them - that is
    the Project Knowledge Graph's responsibility (ADR-0002), a separate
    table this model must never merge with.

    The natural-key uniqueness constraint below is the persistence-level
    idempotency backstop: it makes a literal duplicate row (same
    document, kind, identifier and source locator) impossible to insert,
    regardless of caller. The primary idempotency guarantee for a
    rebuild is still replace semantics (``replace_for_document``); this
    constraint protects the additive, single-entry registration path
    too.
    """

    __tablename__ = "engineering_index_entries"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "kind",
            "identifier",
            "locator_kind",
            "locator_value",
            name="uq_engineering_index_entry_natural_key",
        ),
    )

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

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    kind: Mapped[EngineeringIndexEntryKind] = mapped_column(
        SqlEnum(EngineeringIndexEntryKind),
        nullable=False,
    )

    identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    locator_kind: Mapped[IndexEntryLocatorKind] = mapped_column(
        SqlEnum(IndexEntryLocatorKind),
        nullable=False,
        default=IndexEntryLocatorKind.PAGE,
    )

    locator_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    label: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
