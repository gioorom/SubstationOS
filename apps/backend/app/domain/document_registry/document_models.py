"""
The public identity of a document.

Two shapes, and the difference between them is a deliberate decision
about what a *list* needs versus what a *detail view* needs - not an
accident of which fields happened to be handy.

Neither has a storage field. That is the point: a schema cannot leak a
path that its source value object does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.project.project_document_scope import DocumentScope


class DocumentFormat(str, Enum):
    """
    The registry's own statement of the document format vocabulary.

    Restated here rather than imported from ``app.models.document``: a
    domain module must not depend on the persistence layer, and a public
    schema built from an ORM enum is an ORM detail on the wire. A test
    asserts this set equals the persisted one, so the two cannot drift.

    ``OTHER`` means **unclassified** - a document the classifier looked
    at and could not name - not "examined and found unusable".
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
    """The engineering role a document plays. Restated for the same
    reason as :class:`DocumentFormat`, and asserted equal by test."""

    FUNCTIONAL_SCHEMATIC = "functional_schematic"
    WIRING_TERMINAL = "wiring_terminal"
    GENERAL_TECHNICAL = "general_technical"
    CABLE_LIST = "cable_list"
    RELAY_SETTINGS = "relay_settings"
    COMMISSIONING_REPORT = "commissioning_report"
    OTHER = "other"


#: The media type served for each format when the original bytes are
#: downloaded. A closed table: an unclassified document is served as a
#: generic stream rather than having a type guessed for it, because
#: telling a browser a file is a PDF when nobody established that is a
#: worse answer than telling it nothing.
MEDIA_TYPES: dict[DocumentFormat, str] = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.DWG: "image/vnd.dwg",
    DocumentFormat.DXF: "image/vnd.dxf",
    DocumentFormat.MODEL_3D: "application/octet-stream",
    DocumentFormat.XLSX: (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
    ),
    DocumentFormat.DOCX: (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
    DocumentFormat.IMAGE: "application/octet-stream",
    DocumentFormat.OTHER: "application/octet-stream",
}


def media_type_for(document_format: DocumentFormat) -> str:
    return MEDIA_TYPES[document_format]


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """
    What a list or a selection control needs, and nothing more.

    Every field here answers "which document is this?" for an engineer
    choosing one. A field that only a detail view would use does not
    belong: a registry page that returns a hundred of these should not
    carry a hundred copies of anything a caller did not ask for.

    ``project_name`` is the one field that looks like a detail and is
    not: a registry table spanning several projects has to say which
    project each row belongs to, and a numeric id tells a human nothing.
    It is already denormalised onto the document row, so it costs no
    join.
    """

    document_id: int
    project_id: int | None
    project_name: str
    filename: str
    document_format: DocumentFormat
    category: DocumentCategory
    revision: str
    scope: DocumentScope
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentDetail:
    """
    One document, in full - as full as the registry can honestly be.

    Richer than :class:`DocumentSummary` by two things: the content
    identity, and the ingestion state.

    ``content_checksum`` is a **public** identifier and is meant to be:
    it is the value the whole deterministic pipeline binds its artefacts
    to, so an engineer comparing a canonical representation against a
    document needs to see it. It says nothing about where the bytes are.
    It and its algorithm and size are read from the document's own
    ingestion record - never recomputed here, and ``None`` for a document
    that has not been ingested, because an un-run identity is not a
    zero.

    ``content_available`` reports whether the registry can currently
    reach those bytes. It is the honest answer to "can I download this?"
    and is resolved through the content port, never by looking at a path.
    """

    document_id: int
    project_id: int | None
    project_name: str
    filename: str
    document_format: DocumentFormat
    category: DocumentCategory
    revision: str
    scope: DocumentScope
    uploaded_at: datetime
    content_checksum: str | None
    checksum_algorithm: str | None
    size_bytes: int | None
    content_available: bool
    ingestion_state: str | None
    ingestion_outcome: str | None

    @property
    def summary(self) -> DocumentSummary:
        return DocumentSummary(
            document_id=self.document_id,
            project_id=self.project_id,
            project_name=self.project_name,
            filename=self.filename,
            document_format=self.document_format,
            category=self.category,
            revision=self.revision,
            scope=self.scope,
            uploaded_at=self.uploaded_at,
        )
