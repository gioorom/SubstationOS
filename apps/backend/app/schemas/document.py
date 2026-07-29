"""
The public document contract.

Until this milestone there was no such thing: ``GET /documents/``
declared no response model, so its rows were the ORM columns FastAPI
happened to be able to serialise - including ``file_path``, a
server-side storage location that has no business leaving the backend.

**Every field below is an explicit decision.** The fields deliberately
excluded, and why:

| Field | Why it is not public |
|---|---|
| ``file_path`` | A storage location. Private backend state, always. |
| ``project`` relationship | An ORM relationship; the caller asked for a document |
| ``content_storage_reference`` | Same as ``file_path``, under the ingestion record's name |

A test asserts no schema in this module declares a field whose name
contains ``path``, and another walks live responses looking for the
storage root.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentDetail,
    DocumentFormat,
    DocumentSummary,
)
from app.domain.project.project_document_scope import DocumentScope
from app.schemas.pagination import PageMetadata


class DocumentSummaryRead(BaseModel):
    """
    What a registry list or a document picker needs.

    Kept deliberately small: a page of a hundred of these should carry a
    hundred answers to "which document is this?", and nothing else.
    """

    id: int = Field(description="Stable document identifier.")
    project_id: int | None
    project_name: str
    filename: str
    file_format: DocumentFormat
    category: DocumentCategory
    revision: str
    scope: DocumentScope
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def of(cls, summary: DocumentSummary) -> "DocumentSummaryRead":
        return cls(
            id=summary.document_id,
            project_id=summary.project_id,
            project_name=summary.project_name,
            filename=summary.filename,
            file_format=summary.document_format,
            category=summary.category,
            revision=summary.revision,
            scope=summary.scope,
            uploaded_at=summary.uploaded_at,
        )


class DocumentDetailRead(DocumentSummaryRead):
    """
    One document in full.

    ``content_checksum`` is public on purpose: the deterministic pipeline
    binds every artefact to it, so an engineer comparing a canonical
    representation against its document needs to see it. It identifies
    *the bytes*, never *where they are*.

    ``content_available`` answers "can I download this?" honestly - it is
    resolved through the content port, and is ``false`` for a document
    whose bytes have gone missing under a registry row that remains.
    """

    content_checksum: str | None
    checksum_algorithm: str | None
    size_bytes: int | None
    content_available: bool
    ingestion_state: str | None
    ingestion_outcome: str | None

    @classmethod
    def of_detail(cls, detail: DocumentDetail) -> "DocumentDetailRead":
        return cls(
            id=detail.document_id,
            project_id=detail.project_id,
            project_name=detail.project_name,
            filename=detail.filename,
            file_format=detail.document_format,
            category=detail.category,
            revision=detail.revision,
            scope=detail.scope,
            uploaded_at=detail.uploaded_at,
            content_checksum=detail.content_checksum,
            checksum_algorithm=detail.checksum_algorithm,
            size_bytes=detail.size_bytes,
            content_available=detail.content_available,
            ingestion_state=detail.ingestion_state,
            ingestion_outcome=detail.ingestion_outcome,
        )


class DocumentListResponse(BaseModel):
    """One page of the document registry."""

    items: tuple[DocumentSummaryRead, ...]
    pagination: PageMetadata


# --- Upload -------------------------------------------------------------


class UploadPipelineFailureRead(BaseModel):
    """Which stage of the post-upload analysis stopped, and why."""

    stage: str
    code: str
    message: str


class UploadAnalysisRead(BaseModel):
    """
    What the Knowledge Graph made of the uploaded document.

    Informational: **a failure here never fails the upload.** The
    document is stored, identified and registered whatever the analysis
    made of it - losing an uploaded file because a downstream step
    stumbled would be the worst possible trade.
    """

    status: str = Field(
        description=(
            "completed | skipped | failed | no_text | "
            "unsupported_file_type"
        )
    )

    entities_found: int
    failure: UploadPipelineFailureRead | None


class DocumentUploadResponse(BaseModel):
    """
    The result of ``POST /documents/upload``.

    Replaces the ad-hoc dictionary this endpoint used to return, which
    carried ``file_path`` and could not be described in OpenAPI at all.

    **There is no ``reused`` field.** Upload does not deduplicate:
    Milestone 25.2 established that an identical checksum is recorded and
    nothing is concluded from it, so a document is always newly
    registered here. Reporting ``reused: false`` on every response would
    imply a comparison that never happens.
    """

    document: DocumentDetailRead

    scope: DocumentScope = Field(
        description="The scope the upload was accepted under."
    )

    analysis: UploadAnalysisRead

    warnings: tuple[str, ...] = Field(
        default=(),
        description=(
            "Non-fatal observations about the stored document - an "
            "unclassifiable format, a filename that had to be sanitised "
            "for storage. Empty when there is nothing to say."
        ),
    )
