from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.canonical_pdf.canonical_pdf_models import CanonicalBlockKind


class CanonicalPdfRepresentation(Base):
    """
    One canonical representation of one PDF, at one content checksum
    (Milestone 26.1).

    Stored **independently of the original document**: nothing here
    references or modifies the stored PDF, which stays authoritative and
    untouched. A document accumulates representations over its life - one
    per distinct checksum - and each stays readable, so a conclusion
    drawn from last year's revision remains explainable.

    Four tables mirroring the value-object hierarchy rather than one
    table holding a serialised blob. The hierarchy is the contract every
    future extractor reads; collapsing it into an opaque payload would
    make it unqueryable, unmigratable, and unreviewable by anyone without
    a Python shell.
    """

    __tablename__ = "canonical_pdf_representations"

    __table_args__ = (
        # The idempotency backstop, and the whole reuse rule in one
        # line: one artifact per deterministic identity per document.
        # Re-deriving the same computation cannot produce a second row,
        # while any change upstream or in this stage's own contract is a
        # different identity and therefore a new row alongside - never
        # over - the old one.
        UniqueConstraint(
            "document_id",
            "artifact_identity",
            name="uq_canonical_pdf_artifact_identity",
        ),
        Index(
            "ix_canonical_pdf_representations_document_created",
            "document_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    content_checksum: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    checksum_algorithm: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    representation_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    parser_name: Mapped[str] = mapped_column(String(50), nullable=False)

    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)

    page_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # The deterministic identity of this artifact, and of the artifact it
    # was derived from. Together they are what makes reuse a provable
    # claim rather than a guess: a change anywhere upstream changes the
    # upstream identity, which changes this one.
    #
    # Nullable for one reason only: rows stored before the identity chain
    # existed. An unknown row can never satisfy a reuse lookup, so it is
    # recomputed rather than trusted, and nothing is written back to it.
    #
    # This table is the one whose identity *is* reconstructible - it is a
    # pure function of the six provenance columns beside it, which have
    # always been NOT NULL. The canonical text stage relies on exactly
    # that to recompose a representation's identity without guessing.
    # The column is still not backfilled: a migration recording an
    # identity would be asserting a derivation it never observed.
    artifact_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    upstream_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    pages: Mapped[list["CanonicalPdfPageRecord"]] = relationship(
        "CanonicalPdfPageRecord",
        back_populates="representation",
        cascade="all, delete-orphan",
        order_by="CanonicalPdfPageRecord.page_number",
    )


class CanonicalPdfPageRecord(Base):
    """One page. ``page_number`` is 1-based, as an engineer reads it."""

    __tablename__ = "canonical_pdf_pages"

    __table_args__ = (
        UniqueConstraint(
            "representation_id",
            "page_number",
            name="uq_canonical_pdf_page_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    representation_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_pdf_representations.id"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    width: Mapped[float] = mapped_column(Float, nullable=False)

    height: Mapped[float] = mapped_column(Float, nullable=False)

    representation: Mapped["CanonicalPdfRepresentation"] = relationship(
        "CanonicalPdfRepresentation",
        back_populates="pages",
    )

    blocks: Mapped[list["CanonicalPdfBlockRecord"]] = relationship(
        "CanonicalPdfBlockRecord",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="CanonicalPdfBlockRecord.reading_order",
    )


class CanonicalPdfBlockRecord(Base):
    """
    One block, in the parser's own order.

    ``reading_order`` is the parser's index, not an order this system
    worked out - see the note on ``CanonicalPdfBlock``.
    """

    __tablename__ = "canonical_pdf_blocks"

    __table_args__ = (
        UniqueConstraint(
            "page_id",
            "reading_order",
            name="uq_canonical_pdf_block_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    page_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_pdf_pages.id"),
        nullable=False,
        index=True,
    )

    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)

    kind: Mapped[CanonicalBlockKind] = mapped_column(
        SqlEnum(CanonicalBlockKind),
        nullable=False,
    )

    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)

    page: Mapped["CanonicalPdfPageRecord"] = relationship(
        "CanonicalPdfPageRecord",
        back_populates="blocks",
    )

    spans: Mapped[list["CanonicalPdfSpanRecord"]] = relationship(
        "CanonicalPdfSpanRecord",
        back_populates="block",
        cascade="all, delete-orphan",
        order_by="CanonicalPdfSpanRecord.reading_order",
    )


class CanonicalPdfSpanRecord(Base):
    """
    One run of same-styled text, stored **verbatim**.

    ``text`` is `Text` rather than a bounded `String`: a span is whatever
    the parser produced, and truncating it at an arbitrary column would
    silently lose document content - the one thing this representation
    exists to preserve.
    """

    __tablename__ = "canonical_pdf_spans"

    __table_args__ = (
        UniqueConstraint(
            "block_id",
            "reading_order",
            name="uq_canonical_pdf_span_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    block_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_pdf_blocks.id"),
        nullable=False,
        index=True,
    )

    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)

    font_family: Mapped[str] = mapped_column(String(150), nullable=False)

    font_size: Mapped[float] = mapped_column(Float, nullable=False)

    bold: Mapped[bool] = mapped_column(Boolean, nullable=False)

    italic: Mapped[bool] = mapped_column(Boolean, nullable=False)

    block: Mapped["CanonicalPdfBlockRecord"] = relationship(
        "CanonicalPdfBlockRecord",
        back_populates="spans",
    )
