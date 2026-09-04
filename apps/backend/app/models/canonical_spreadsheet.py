from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCellType,
    WorkbookDateSystem,
    WorksheetVisibility,
)


class CanonicalWorkbookRecord(Base):
    """
    One canonical representation of one workbook, at one content
    checksum (ADR-0034).

    Stored **independently of the original workbook**: nothing here
    references or modifies the uploaded file, which stays authoritative
    and untouched. A document accumulates representations over its life -
    one per distinct checksum - and each stays readable, so a conclusion
    drawn from last year's revision remains explainable.

    Four tables mirroring the value-object hierarchy rather than one
    table holding a serialised blob, for the reason Milestone 26.1 used
    four: the hierarchy is the contract every future consumer reads, and
    an opaque payload would be unqueryable, unmigratable and unreviewable
    by anyone without a Python shell.

    The words ``page``, ``block``, ``span``, ``bounding_box``,
    ``reading_order``, ``line_index``, ``paragraph`` and ``section``
    appear nowhere in this schema. A worksheet is not a page and a row is
    not a line; naming them so would push an invented geometry into every
    consumer downstream.
    """

    __tablename__ = "canonical_workbooks"

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
            name="uq_canonical_workbook_artifact_identity",
        ),
        Index(
            "ix_canonical_workbooks_document_created",
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

    # The library that read the grid, and which release of it. Both are
    # inputs to this artifact's identity: two library versions can
    # legitimately disagree about a difficult workbook, and an upgrade
    # that silently reused the old representation would carry a stale
    # reading through every stage below.
    reader_name: Mapped[str] = mapped_column(String(50), nullable=False)

    reader_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # The epoch the workbook's serial dates are counted from. Two
    # workbooks holding the identical serial denote dates four years
    # apart under the two systems, and a representation that did not say
    # which one applied could not explain its own dates later.
    date_system: Mapped[WorkbookDateSystem] = mapped_column(
        SqlEnum(WorkbookDateSystem),
        nullable=False,
    )

    # Observations about provenance, not capabilities: no macro is ever
    # parsed or executed, and no linked workbook is ever followed. A
    # register whose values come from a file this system has never seen
    # is a register to be read with care, and that has to be visible.
    has_vba_project: Mapped[bool] = mapped_column(Boolean, nullable=False)

    has_external_links: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )

    worksheet_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # The deterministic identity of this artifact, and of the artifact it
    # was derived from. Together they are what makes reuse a provable
    # claim rather than a guess: a change anywhere upstream changes the
    # upstream identity, which changes this one.
    #
    # Nullable for one reason only: rows stored before the identity chain
    # existed. An unknown row can never satisfy a reuse lookup, so it is
    # recomputed rather than trusted, and nothing is written back to it.
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

    worksheets: Mapped[list["CanonicalWorksheetRecord"]] = relationship(
        "CanonicalWorksheetRecord",
        back_populates="workbook",
        cascade="all, delete-orphan",
        order_by="CanonicalWorksheetRecord.worksheet_index",
    )


class CanonicalWorksheetRecord(Base):
    """
    One worksheet at its ordinal position in the workbook, under its own
    name.

    ``worksheet_index`` is 0-based because it is a position in the
    workbook's own ordering; row and column numbers below are 1-based
    because those are exactly what the workbook shows. Mixing the two
    bases is deliberate: each matches the thing it addresses.

    The four ``used_*`` columns are the rectangle the observed cells
    actually occupy, derived from those cells and **never** from the
    file's declared ``dimension`` element, which producers routinely omit
    or get wrong. All four are nullable together: a worksheet that
    materialised no cell has no extent, and a rectangle recorded for it
    would claim one it does not have.

    Hidden and very-hidden worksheets are recorded in full. A cable
    register left on a hidden worksheet is still what the document
    contains, and skipping it would be this system deciding which parts
    of a delivered document count.
    """

    __tablename__ = "canonical_worksheets"

    __table_args__ = (
        UniqueConstraint(
            "workbook_id",
            "worksheet_index",
            name="uq_canonical_worksheet_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    workbook_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_workbooks.id"),
        nullable=False,
        index=True,
    )

    worksheet_index: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    visibility: Mapped[WorksheetVisibility] = mapped_column(
        SqlEnum(WorksheetVisibility),
        nullable=False,
    )

    used_first_row: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    used_last_row: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    used_first_column: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    used_last_column: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    workbook: Mapped["CanonicalWorkbookRecord"] = relationship(
        "CanonicalWorkbookRecord",
        back_populates="worksheets",
    )

    rows: Mapped[list["CanonicalRowRecord"]] = relationship(
        "CanonicalRowRecord",
        back_populates="worksheet",
        cascade="all, delete-orphan",
        order_by="CanonicalRowRecord.row_number",
    )


class CanonicalRowRecord(Base):
    """
    One row, by the workbook's own 1-based number.

    The numbers are the file's, so a gap between row 12 and row 40 is a
    fact about the register and stays visible as one - rows are never
    re-indexed to close it, and a row that materialised no cell is never
    recorded at all.
    """

    __tablename__ = "canonical_rows"

    __table_args__ = (
        UniqueConstraint(
            "worksheet_id",
            "row_number",
            name="uq_canonical_row_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    worksheet_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_worksheets.id"),
        nullable=False,
        index=True,
    )

    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    worksheet: Mapped["CanonicalWorksheetRecord"] = relationship(
        "CanonicalWorksheetRecord",
        back_populates="rows",
    )

    cells: Mapped[list["CanonicalCellRecord"]] = relationship(
        "CanonicalCellRecord",
        back_populates="row",
        cascade="all, delete-orphan",
        order_by="CanonicalCellRecord.column_number",
    )


class CanonicalCellRecord(Base):
    """
    One cell at its own 1-based column number, carrying **either** a
    literal **or** a formula, never both.

    ## Why literal and cached values live in different columns

    ``literal_*`` is what the engineer typed. ``cached_*`` is what some
    other application computed into the file for a formula. They are kept
    in **distinct columns** so that no SQL query can conflate them: a
    single ``value`` column would let every consumer forget, silently and
    by default, which of the two it was reading - and that is the one
    distinction this context exists to keep (ADR-0034 §3).

    ``formula_expression`` with every ``cached_*`` column null says
    exactly one thing: **no application has ever computed a value into
    this file for this cell** - the normal state of a workbook produced
    by a script and never opened. It is emphatically not a blank cell, an
    empty string, a zero, or a read failure. Nothing in this system
    evaluates the expression to fill those columns in.

    ## The numeric columns

    ``literal_number`` and ``cached_number`` are `Numeric`, **never**
    `Float`: a rated current that read back as 630.0000000000001 A would
    be a defect nobody could explain to an engineer, and binary floating
    point makes that inevitable. SQLAlchemy returns `Decimal` from these
    columns, which is what the domain holds.

    ``literal_text``/``cached_text`` remain the authoritative rendering
    either way - ADR-0034 records that a non-integer's own lexical form
    is already gone by the time the reader sees it, and the recorded text
    is the reader's rendering of the parsed value.

    ## What has no column here, deliberately

    No ``header_row``, no ``column_name``, no ``field_name``, no
    ``record``, no ``merged_range`` and no ``hidden`` flag. The first
    four are inferences this context reads nothing that could check; the
    last two were never reported by a streaming reader, and defaulting
    them would assert something no reader ever said.
    """

    __tablename__ = "canonical_cells"

    __table_args__ = (
        UniqueConstraint(
            "row_id",
            "column_number",
            name="uq_canonical_cell_column",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    row_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_rows.id"),
        nullable=False,
        index=True,
    )

    column_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # The display format string the file states. Recorded because it is
    # the only thing that distinguishes a serial date from a plain number
    # in the source, not so that anything renders from it.
    number_format: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # --- What the engineer typed --------------------------------------

    literal_type: Mapped[CanonicalCellType | None] = mapped_column(
        SqlEnum(CanonicalCellType, name="canonicalcelltype"),
        nullable=True,
    )

    literal_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    literal_number: Mapped[object | None] = mapped_column(
        Numeric(38, 12),
        nullable=True,
    )

    literal_boolean: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    #: ISO-8601, naive. A workbook records a wall-clock reading with no
    #: zone; attaching one would be an invented fact about where the
    #: substation is.
    literal_instant: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    literal_duration: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    #: The error the file itself carries (``#DIV/0!``) - a value the
    #: workbook genuinely holds, not a failure of this system to read the
    #: cell. Dropping it would make a broken register look complete.
    literal_error_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    # --- What the file computes, and what another application cached --

    formula_expression: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    cached_type: Mapped[CanonicalCellType | None] = mapped_column(
        SqlEnum(CanonicalCellType, name="canonicalcelltype"),
        nullable=True,
    )

    cached_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    cached_number: Mapped[object | None] = mapped_column(
        Numeric(38, 12),
        nullable=True,
    )

    cached_boolean: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    cached_instant: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    cached_duration: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    cached_error_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    row: Mapped["CanonicalRowRecord"] = relationship(
        "CanonicalRowRecord",
        back_populates="cells",
    )
