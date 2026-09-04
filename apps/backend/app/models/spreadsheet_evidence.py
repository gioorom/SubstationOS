from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)


class SpreadsheetEvidenceSetRecord(Base):
    """
    One extraction over one canonical workbook (ADR-0034).

    Stored **independently of the canonical workbook and of the Knowledge
    Graph**, and modifying neither. The four provenance columns -
    document, checksum, representation version, policy version - are what
    keep a historical set explainable years later.

    A **second** evidence store now exists, and nothing downstream
    consumes it yet: entity resolution reads
    ``engineering_evidence_sets`` and will not see a row here. That is
    deliberate for a foundation milestone and is recorded as debt in
    ADR-0034, not as a feature.
    """

    __tablename__ = "spreadsheet_evidence_sets"

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
            name="uq_spreadsheet_evidence_set_artifact_identity",
        ),
        Index(
            "ix_spreadsheet_evidence_sets_document_created",
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

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True,
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

    extraction_policy_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # The deterministic identity of this artifact, and of the artifact it
    # was derived from. Together they are what makes reuse a provable
    # claim rather than a guess: a change anywhere upstream changes the
    # upstream identity, which changes this one.
    #
    # Nullable for one reason only: rows stored before the identity chain
    # existed. Their identity cannot be reconstructed from anything
    # durable, so it stays unknown rather than guessed, and an unknown
    # row can never satisfy a reuse lookup.
    artifact_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    upstream_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    evidence: Mapped[list["SpreadsheetEvidenceRecord"]] = relationship(
        "SpreadsheetEvidenceRecord",
        back_populates="evidence_set",
        cascade="all, delete-orphan",
        order_by="SpreadsheetEvidenceRecord.id",
    )


class SpreadsheetEvidenceRecord(Base):
    """
    One observation about one cell.

    ## The provenance columns

    Seven columns, all ``NOT NULL``, and every one of them a coordinate
    the reader actually observed: which worksheet, at which position and
    under which name, which row, which column and its label, and which
    characters of **that cell's own text**.

    There is deliberately **no ``page_number``, no ``section_index``, no
    ``paragraph_index``, no ``block_reading_order``, no ``line_index``,
    no token range and no span child table.** A worksheet has no page
    until it is printed, a row is not a line, and nothing here was ever
    grouped into a span. Recording an observation about a cell through
    the PDF family's provenance would mean writing six invented values
    into ``NOT NULL`` columns, four of which enter a persisted identity -
    which under the evidence model's own rule would make the row an
    assertion rather than evidence.

    ``engineering_evidence`` and its provenance are correspondingly
    **not modified**: their columns stay ``NOT NULL``, their key formula
    stays fixed, and the two families never meet.

    ## The value columns

    ``quantity_value`` is `Numeric`, **never** `Float`: a rated voltage
    that read back as 20.000000000000004 kV would be a defect nobody
    could explain to an engineer.

    ``quantity_*`` and ``designation_normalized`` are separate typed
    columns rather than one ``value`` string, because a voltage and a
    designation are different kinds of thing. At most one group is
    populated, decided by ``evidence_type``; an ``AMBIGUOUS`` row
    populates neither, so a guess can never be read back as a
    measurement.

    ## What has no column here, deliberately

    No ``entity_id``, no ``equipment_type``, no ``belongs_to``, no
    ``related_evidence_id`` - and no ``from``, ``to``, ``cable``,
    ``circuit`` or ``connects``. That two observations sit in the same
    row is a fact about a grid; a connection is a judgement, and this
    milestone makes none.
    """

    __tablename__ = "spreadsheet_evidence"

    __table_args__ = (
        # The deterministic evidence key makes a duplicate observation
        # impossible to insert within one set, whatever the caller does.
        UniqueConstraint(
            "evidence_set_id",
            "evidence_key",
            name="uq_spreadsheet_evidence_key",
        ),
        # "Where has this designation been observed?" - the read a future
        # milestone that consumes this store performs.
        Index(
            "ix_spreadsheet_evidence_designation",
            "designation_normalized",
        ),
        Index(
            "ix_spreadsheet_evidence_type_status",
            "evidence_type",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    evidence_set_id: Mapped[int] = mapped_column(
        ForeignKey("spreadsheet_evidence_sets.id"),
        nullable=False,
        index=True,
    )

    evidence_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    evidence_type: Mapped[EvidenceType] = mapped_column(
        SqlEnum(EvidenceType),
        nullable=False,
    )

    status: Mapped[EvidenceStatus] = mapped_column(
        SqlEnum(EvidenceStatus),
        nullable=False,
    )

    observed_text: Mapped[str] = mapped_column(Text, nullable=False)

    rule_id: Mapped[str] = mapped_column(String(60), nullable=False)

    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- Typed values -------------------------------------------------

    quantity_value: Mapped[object | None] = mapped_column(
        Numeric(28, 6),
        nullable=True,
    )

    quantity_unit: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    quantity_base_value: Mapped[object | None] = mapped_column(
        Numeric(28, 6),
        nullable=True,
    )

    quantity_base_unit: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    designation_normalized: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    # --- Cell provenance ----------------------------------------------

    worksheet_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # The name as well as the position: an engineer looking for "Cable
    # Schedule" needs the name, and a later revision can move that
    # worksheet, at which point the position alone would silently point
    # somewhere else.
    worksheet_name: Mapped[str] = mapped_column(String(255), nullable=False)

    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    column_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # The workbook's own bijective base-26 label, so a recorded
    # observation can be pasted straight back into the source file.
    column_label: Mapped[str] = mapped_column(String(8), nullable=False)

    # Half-open, Python slice convention, into the **cell's own text**.
    character_start: Mapped[int] = mapped_column(Integer, nullable=False)

    character_end: Mapped[int] = mapped_column(Integer, nullable=False)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    evidence_set: Mapped["SpreadsheetEvidenceSetRecord"] = relationship(
        "SpreadsheetEvidenceSetRecord",
        back_populates="evidence",
    )
