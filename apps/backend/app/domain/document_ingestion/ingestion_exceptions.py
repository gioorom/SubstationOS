from __future__ import annotations

from app.domain.document_ingestion.ingestion_lifecycle import IngestionState


class DocumentIngestionError(Exception):
    """Base class for every exception raised by the Document Ingestion
    bounded context."""


class IngestedDocumentNotFoundError(DocumentIngestionError):
    def __init__(self, document_id: int) -> None:
        self.document_id = document_id

        super().__init__(
            f"Document '{document_id}' not found; nothing can be ingested "
            "for it."
        )


class UnsupportedDocumentFormatError(DocumentIngestionError):
    """
    The document records a format value this system does not define.

    A data-integrity condition (a row from a different schema version),
    never a judgement about an unclassified document - a document whose
    format was never set ingests normally.
    """

    def __init__(self, document_id: int, document_format: str) -> None:
        self.document_id = document_id
        self.document_format = document_format

        super().__init__(
            f"Document '{document_id}' has format '{document_format}', "
            "which is not supported for ingestion."
        )


class InvalidIngestionTransitionError(DocumentIngestionError):
    """
    An illegal lifecycle move. Raised rather than tolerated: a job that
    reached ``PROCESSED`` without passing through ``PROCESSING`` would be
    a record of something that never happened.
    """

    def __init__(
        self, job_id: int | None, current: IngestionState, target: IngestionState
    ) -> None:
        self.job_id = job_id
        self.current = current
        self.target = target

        super().__init__(
            f"Ingestion job '{job_id}' cannot move from '{current.value}' to "
            f"'{target.value}'."
        )


class DuplicateIngestionRequestError(DocumentIngestionError):
    """
    An ingestion was requested for a document that already has one in
    flight.

    Refused rather than queued twice: two jobs racing over the same
    document would produce two records of what "the" ingestion concluded,
    and nothing would say which is authoritative.
    """

    def __init__(
        self, document_id: int, existing_job_id: int | None,
        existing_state: IngestionState,
    ) -> None:
        self.document_id = document_id
        self.existing_job_id = existing_job_id
        self.existing_state = existing_state

        super().__init__(
            f"Document '{document_id}' already has ingestion job "
            f"'{existing_job_id}' in state '{existing_state.value}'."
        )


class IngestionJobNotFoundError(DocumentIngestionError):
    def __init__(self, job_id: int) -> None:
        self.job_id = job_id

        super().__init__(f"Ingestion job '{job_id}' not found.")


class IngestionJobNotRetryableError(DocumentIngestionError):
    """Only a failed job can be retried. A completed one is re-ingested by
    requesting a new job, so the record of what was processed when is
    never overwritten."""

    def __init__(self, job_id: int, state: IngestionState) -> None:
        self.job_id = job_id
        self.state = state

        super().__init__(
            f"Ingestion job '{job_id}' is in state '{state.value}' and "
            "cannot be retried; only a failed job can."
        )
