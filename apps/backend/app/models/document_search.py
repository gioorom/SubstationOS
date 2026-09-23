"""
The searchable projection of a document's canonical representation.

**A projection, never a source of truth.** Every row here is derived
from a canonical representation that remains authoritative, and the
whole table can be dropped and rebuilt from those representations
without losing anything. Nothing reads it to establish a fact; it
exists so that finding a fact does not require reading every document.

That is why it carries no identity of its own, no checksum it computed,
and no lifecycle. It copies ``document_id`` and ``content_checksum``
from the document it was built from, so a hit can say which version of
which document it came from - and if the two ever disagreed, the
document row wins and this table is rebuilt.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DocumentSearchSegment(Base):
    __tablename__ = "document_search_segments"

    __table_args__ = (
        # Every search is scoped to one project and every re-index is
        # scoped to one document. Both reads are covered here so neither
        # has to scan the table.
        Index(
            "ix_document_search_segments_project",
            "project_id",
        ),
        Index(
            "ix_document_search_segments_document",
            "document_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    project_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    """
    Copied from the document, not a foreign key.

    Nullable because a Canonical Library document belongs to no project
    (ADR-0005), and those segments are simply never returned by a
    project-scoped search.
    """

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
    )

    content_checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    """Which version of the document this segment was read from."""

    kind: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    """
    Which source family the segment was read from, stored as the value
    of ``app.domain.document_search.search_models.SegmentKind``.

    A plain string rather than a database enum, and annotated as the
    ``str`` it actually is: the vocabulary belongs to the domain, and a
    second copy of it here would be one more thing that can disagree
    with the first. The adapter converts in both directions and raises
    ``UnknownSegmentKindError`` on a value it cannot read.
    """

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    line_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    worksheet_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    worksheet_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cell_offsets: Mapped[str | None] = mapped_column(Text, nullable=True)
    """
    Where each cell of a spreadsheet row starts inside ``text``, as
    JSON: ``[[column_number, start_offset], ...]`` in column order.

    JSON in one column rather than a child table because these
    boundaries are meaningless apart from the row they describe, are
    written and read only with it, and are never queried. A table would
    promise a life of their own that they do not have.
    """

    text: Mapped[str] = mapped_column(Text, nullable=False)
    """What the source says, verbatim, for the reader to recognise."""

    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    """
    What the matcher compares against: case- and accent-folded, with
    every separator collapsed to a space and the whole wrapped in
    spaces so a term can be matched with its boundaries intact.

    Stored rather than computed per query because a search reads far
    more rows than an index writes, and because the normalization a hit
    was matched by should be the one that was stored with it.
    """
