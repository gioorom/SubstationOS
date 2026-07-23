from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
)


class ReviewCandidateRepository(ABC):
    """
    Port for persisting and querying Review Candidates. The domain
    depends only on this contract; an infrastructure adapter (e.g.
    ``SqlAlchemyReviewCandidateRepository``) provides the
    implementation.
    """

    @abstractmethod
    def create(self, candidate: ReviewCandidate) -> ReviewCandidate:
        """Insert a new candidate (``id`` must be ``None``) and return
        it with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def update(self, candidate: ReviewCandidate) -> ReviewCandidate:
        """Persist a candidate's new state (``id`` must already be
        set)."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> ReviewCandidate | None:
        """Return the candidate with this id, or ``None`` if none
        exists."""

        raise NotImplementedError

    @abstractmethod
    def get_open_by_claim(
        self,
        proposed_claim_id: int,
    ) -> ReviewCandidate | None:
        """
        Return the open (``PENDING`` or ``NEEDS_CHANGES``) candidate for
        this Proposed Claim, if one exists - used to enforce "at most
        one open candidate per claim".
        """

        raise NotImplementedError

    @abstractmethod
    def list_pending(self) -> list[ReviewCandidate]:
        """Return every ``PENDING`` candidate across every project - the
        reviewer's global queue."""

        raise NotImplementedError

    @abstractmethod
    def list_by_project(
        self,
        project_id: int,
        *,
        status: ReviewStatus | None = None,
    ) -> list[ReviewCandidate]:
        """Return every candidate recorded for this project, optionally
        filtered to a single status."""

        raise NotImplementedError
