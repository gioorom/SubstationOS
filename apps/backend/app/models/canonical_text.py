from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class CanonicalTextDocumentRecord(Base):
    """
    One document's canonical text segmentation (Milestone 27.1).

    Stored **separately from the canonical representation** and never
    modifying it: the representation records what the parser observed,
    this records the structure segmented over it, and a change of
    segmentation rules rebuilds one without touching the other.

    Five tables mirroring the value hierarchy, for the same reason
    Milestone 26.1 used four: the hierarchy is the contract every future
    extractor reads, and a serialised blob would be unqueryable,
    unmigratable, and unreviewable by anyone without a Python shell.
    """

    __tablename__ = "canonical_text_documents"

    __table_args__ = (
        # The idempotency backstop. One segmentation per document per
        # representation per set of rules: re-running cannot produce a
        # second row whatever the caller does, while a new checksum (the
        # document changed) or a new segmentation version (the rules
        # changed) is a new row alongside - never over - the old one.
        UniqueConstraint(
            "document_id",
            "content_checksum",
            "segmentation_version",
            name="uq_canonical_text_document_checksum_version",
        ),
        Index(
            "ix_canonical_text_documents_document_created",
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

    representation_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    segmentation_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    section_count: Mapped[int] = mapped_column(Integer, nullable=False)

    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    sections: Mapped[list["CanonicalTextSectionRecord"]] = relationship(
        "CanonicalTextSectionRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="CanonicalTextSectionRecord.section_index",
    )


class CanonicalTextSectionRecord(Base):
    """
    One page. Deliberately **not** a chapter, heading or engineering
    section - see ``canonical_text_models``. ``page_number`` is on the row
    precisely so nobody has to wonder.
    """

    __tablename__ = "canonical_text_sections"

    __table_args__ = (
        UniqueConstraint(
            "text_document_id",
            "section_index",
            name="uq_canonical_text_section_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    text_document_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_text_documents.id"),
        nullable=False,
        index=True,
    )

    section_index: Mapped[int] = mapped_column(Integer, nullable=False)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped["CanonicalTextDocumentRecord"] = relationship(
        "CanonicalTextDocumentRecord",
        back_populates="sections",
    )

    paragraphs: Mapped[list["CanonicalTextParagraphRecord"]] = relationship(
        "CanonicalTextParagraphRecord",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="CanonicalTextParagraphRecord.paragraph_index",
    )


class CanonicalTextParagraphRecord(Base):
    """One PDF block, as the parser delimited it - not a semantic
    paragraph, a table or a list."""

    __tablename__ = "canonical_text_paragraphs"

    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "paragraph_index",
            name="uq_canonical_text_paragraph_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    section_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_text_sections.id"),
        nullable=False,
        index=True,
    )

    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    block_reading_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    section: Mapped["CanonicalTextSectionRecord"] = relationship(
        "CanonicalTextSectionRecord",
        back_populates="paragraphs",
    )

    lines: Mapped[list["CanonicalTextLineRecord"]] = relationship(
        "CanonicalTextLineRecord",
        back_populates="paragraph",
        cascade="all, delete-orphan",
        order_by="CanonicalTextLineRecord.id",
    )


class CanonicalTextLineRecord(Base):
    """
    One line, as the parser grouped its spans.

    Ordered by ``id`` rather than by ``line_index``, because the
    segmenter preserves the parser's first-appearance order and a line
    index is not guaranteed to be dense or ascending. Sorting by it here
    would quietly re-order lines the parser presented differently.
    """

    __tablename__ = "canonical_text_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    paragraph_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_text_paragraphs.id"),
        nullable=False,
        index=True,
    )

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    paragraph: Mapped["CanonicalTextParagraphRecord"] = relationship(
        "CanonicalTextParagraphRecord",
        back_populates="lines",
    )

    tokens: Mapped[list["CanonicalTextTokenRecord"]] = relationship(
        "CanonicalTextTokenRecord",
        back_populates="line",
        cascade="all, delete-orphan",
        order_by="CanonicalTextTokenRecord.position",
    )


class CanonicalTextTokenRecord(Base):
    """
    One whitespace-delimited run of characters, inside one span.

    The provenance columns are **denormalised onto the token on purpose**.
    The read every future extractor performs is "find this term, and tell
    me exactly where in the document it sits" - and that must not cost
    four joins back up the hierarchy. The chain
    ``page → block → span → characters`` is therefore readable from the
    token row alone.

    Both ``text`` and ``normalized_text`` are stored. The original is
    what the document says; the normalised form is what two documents can
    be compared on; neither substitutes for the other.
    """

    __tablename__ = "canonical_text_tokens"

    __table_args__ = (
        UniqueConstraint(
            "line_id",
            "position",
            name="uq_canonical_text_token_position",
        ),
        # "Where does this term appear?" - the one read this table exists
        # to serve, answered without walking the hierarchy.
        Index(
            "ix_canonical_text_tokens_normalized",
            "normalized_text",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    line_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_text_lines.id"),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Provenance back to the canonical representation --------------

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    block_reading_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    span_reading_order: Mapped[int] = mapped_column(Integer, nullable=False)

    line_index: Mapped[int] = mapped_column(Integer, nullable=False)

    character_start: Mapped[int] = mapped_column(Integer, nullable=False)

    character_end: Mapped[int] = mapped_column(Integer, nullable=False)

    line: Mapped["CanonicalTextLineRecord"] = relationship(
        "CanonicalTextLineRecord",
        back_populates="tokens",
    )
