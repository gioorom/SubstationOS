"""
Value objects for Document Ingestion (EPIC 2, Milestone 25.1).

This bounded context orchestrates a document's journey from *uploaded* to
*ready for extraction*. It is emphatically **not** extraction itself:

- it reads no document contents - no parsing, no OCR, no text extraction;
- it uses no LLM, no embeddings, no provider of any kind;
- it writes neither the Engineering Index nor the Project Knowledge
  Graph. Preparing a document to be extracted from and actually
  extracting from it are different milestones, and conflating them here
  would mean claiming knowledge nobody has reviewed.

What it produces is a typed, persisted record: *this document was
accepted, these are the facts we already hold about it, and it is (or is
not) ready for a future extractor to work on.*

Every type here is immutable. A job's history is a sequence of new
values, never a mutated one, so "what state was this in yesterday" stays
answerable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.document_ingestion.ingestion_lifecycle import IngestionState
from app.domain.project.project_document_scope import DocumentScope


class IngestionOutcome(str, Enum):
    """
    What one completed ingestion concluded.

    ``READY_FOR_EXTRACTION`` is a statement about *this pipeline's* checks
    only: the document exists, its format is one this system recognises,
    and its metadata was collected. It says nothing about whether the
    document contains anything worth extracting - nobody has read it.

    Deliberately two values. A "partially ready" outcome would leave a
    future extractor deciding what to do with a half-prepared document,
    which is the ambiguity this record exists to remove.
    """

    READY_FOR_EXTRACTION = "ready_for_extraction"
    FAILED = "failed"


class IngestionFailureCode(str, Enum):
    """A closed, provider-neutral failure taxonomy. Every value describes
    something about the document or the request; none describes a
    provider, a model or a network, because this context touches none of
    them."""

    DOCUMENT_NOT_FOUND = "document_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INVALID_LIFECYCLE_TRANSITION = "invalid_lifecycle_transition"
    DUPLICATE_INGESTION_REQUEST = "duplicate_ingestion_request"
    # Kept for a step that fails for a reason genuinely unknown. Every
    # cause below is named rather than collapsed into it: an engineer
    # reading "pipeline execution failure" learns nothing about where to
    # look.
    PIPELINE_EXECUTION_FAILURE = "pipeline_execution_failure"
    # Content access and identity (Milestone 25.2). Four distinct reasons
    # kept apart because they send an engineer to four different places:
    # the record points nowhere, the file is there but unreadable, it is
    # empty, or reading it broke partway through.
    CONTENT_NOT_FOUND = "content_not_found"
    CONTENT_INACCESSIBLE = "content_inaccessible"
    EMPTY_CONTENT = "empty_content"
    CHECKSUM_FAILURE = "checksum_failure"
    # Format classification (Milestone 25.2). ``UNKNOWN_FORMAT`` means no
    # source had an opinion; ``CONFLICTING_FORMAT_EVIDENCE`` means two
    # did and disagreed with nothing authoritative to arbitrate. Distinct
    # because the first is a gap and the second is a contradiction.
    UNKNOWN_FORMAT = "unknown_format"
    CONFLICTING_FORMAT_EVIDENCE = "conflicting_format_evidence"
    INVALID_STORED_METADATA = "invalid_stored_metadata"


@dataclass(frozen=True, slots=True)
class IngestionFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception and never a stack trace."""

    code: IngestionFailureCode
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentContentIdentitySnapshot:
    """
    The bytes' own identity at ingestion time (Milestone 25.2).

    Recorded on the job so a later question - "did this document change
    since we ingested it?" - is answerable without re-reading anything,
    and so two jobs over the same bytes are recognisably over the same
    bytes.

    ``checksum_algorithm`` is stored rather than assumed, so a future
    change of algorithm makes old identities recognisably old instead of
    silently incomparable.

    Identity is **not** deduplication: identical checksums are recorded
    and nothing is concluded from them.
    """

    storage_reference: str
    checksum_algorithm: str
    checksum: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class DocumentFormatSnapshot:
    """
    What the classifier decided, and on what evidence (Milestone 25.2).

    ``decided_by`` is the provenance an engineer needs to trust the
    answer: a format settled by the file's own leading bytes is a
    different quality of fact from one settled by its extension.

    ``stored_format`` is what the document *record* said, kept alongside
    so a divergence between the record and the bytes is visible rather
    than silently overwritten.
    """

    detected_format: str
    decided_by: str
    stored_format: str
    disagreeing_evidence: tuple[str, ...] = ()

    @property
    def matches_stored_format(self) -> bool:
        return self.detected_format == self.stored_format


@dataclass(frozen=True, slots=True)
class IngestedDocumentSnapshot:
    """
    The facts about a document at the moment it was ingested, copied onto
    the job.

    A snapshot rather than a live read, on purpose: a document's revision
    or category can change after ingestion, and a job that silently
    started describing the *current* document would make its own outcome
    unexplainable. Every field here is one the document repository
    already holds - nothing is derived, computed or inferred.
    """

    document_id: int
    project_id: int | None
    title: str
    document_format: str
    document_category: str
    revision: str
    scope: DocumentScope
    # Milestone 25.2. Both are ``None`` on a job that failed before the
    # relevant step ran, and on every job recorded before 25.2 existed -
    # a historical job stays readable and keeps meaning exactly what it
    # meant when it was written.
    content: DocumentContentIdentitySnapshot | None = None
    format: DocumentFormatSnapshot | None = None


@dataclass(frozen=True, slots=True)
class IngestionJob:
    """
    One document's ingestion, as a typed immutable record.

    ``id`` is ``None`` until persisted, the same convention
    ``IndexEntry`` already uses.

    ``attempt_count`` increments on each retry of the *same* job, so the
    history of a document that failed twice before succeeding is visible
    on the record an engineer is already looking at rather than spread
    across three rows.

    ``outcome`` and ``completed_at`` are ``None`` until the job reaches a
    terminal state, and ``failure`` is populated only on ``FAILED`` -
    never both an outcome of ``READY_FOR_EXTRACTION`` and a failure.
    """

    id: int | None
    project_id: int | None
    document_id: int
    state: IngestionState
    pipeline_version: str
    created_at: datetime
    updated_at: datetime
    attempt_count: int = 1
    completed_at: datetime | None = None
    outcome: IngestionOutcome | None = None
    failure: IngestionFailure | None = None
    document: IngestedDocumentSnapshot | None = None

    @property
    def is_terminal(self) -> bool:
        from app.domain.document_ingestion.ingestion_lifecycle import (
            TERMINAL_STATES,
        )

        return self.state in TERMINAL_STATES

    @property
    def is_ready_for_extraction(self) -> bool:
        """The one question a future extraction milestone asks of this
        record."""

        return self.outcome is IngestionOutcome.READY_FOR_EXTRACTION


@dataclass(frozen=True, slots=True)
class IngestionPipelineResult:
    """
    What one pipeline execution concluded, before it is written back onto
    the job.

    Separate from ``IngestionJob`` because the pipeline is pure: it
    decides an outcome from the inputs it was given and returns it, and
    the service is what turns that into a new persisted job state. Nothing
    in the pipeline writes.
    """

    outcome: IngestionOutcome
    pipeline_version: str
    document: IngestedDocumentSnapshot | None = None
    failure: IngestionFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is IngestionOutcome.READY_FOR_EXTRACTION
