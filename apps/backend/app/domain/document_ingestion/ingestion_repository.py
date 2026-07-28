from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.document_ingestion.ingestion_models import IngestionJob


class IngestionJobRepository(ABC):
    """
    Port for persisting and querying ingestion jobs. The domain depends
    only on this contract; an infrastructure adapter provides the
    implementation.

    Deliberately narrow: this context stores jobs and reads them back. It
    has no port onto document contents, the Engineering Index, or the
    Project Knowledge Graph, because it writes to none of them.
    """

    @abstractmethod
    def save(self, job: IngestionJob) -> IngestionJob:
        """Insert a new job and return it with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def update(self, job: IngestionJob) -> IngestionJob:
        """Persist a job's advanced state. The job must already have an
        ``id``."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, job_id: int) -> IngestionJob | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_document(self, document_id: int) -> list[IngestionJob]:
        """Every job ever recorded for this document, oldest first - the
        audit trail a re-ingested document accumulates."""

        raise NotImplementedError

    @abstractmethod
    def find_active_for_document(
        self, document_id: int
    ) -> IngestionJob | None:
        """The job currently in flight for this document, if any. What
        makes a duplicate request detectable before a second one is
        created."""

        raise NotImplementedError

    @abstractmethod
    def list_by_project(self, project_id: int) -> list[IngestionJob]:
        raise NotImplementedError
