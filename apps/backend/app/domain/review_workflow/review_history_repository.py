from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.review_workflow.review_workflow_models import (
    ReviewHistoryEvent,
)


class ReviewHistoryRepository(ABC):
    """
    Port for the append-only Review History ledger. There is no update
    or delete method by design: history is immutable (CLAUDE.md SS16
    Auditability) - changing a review's outcome again always appends a
    new event, never edits or removes a prior one.
    """

    @abstractmethod
    def append(self, event: ReviewHistoryEvent) -> ReviewHistoryEvent:
        """Insert a new history event and return it with ``id``
        populated."""

        raise NotImplementedError

    @abstractmethod
    def list_by_candidate(
        self,
        review_candidate_id: int,
    ) -> list[ReviewHistoryEvent]:
        """Return every event recorded for this candidate, oldest
        first."""

        raise NotImplementedError
