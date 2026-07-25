from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.canonicalization.canonicalization_models import (
    CanonicalFact,
)


class CanonicalFactRepository(ABC):
    """
    Port for persisting and querying Canonical Facts. The domain depends
    only on this contract; an infrastructure adapter (e.g.
    ``SqlAlchemyCanonicalFactRepository``) provides the implementation.

    Deliberately has no ``update``/``delete`` method: a ``CanonicalFact``
    is produced once, from one approved Review Candidate, and is never
    edited in place - re-canonicalizing the same candidate is idempotent
    (``get_by_review_candidate``), not a mutation.
    """

    @abstractmethod
    def save(self, fact: CanonicalFact) -> CanonicalFact:
        """Insert a new fact (``id`` must be ``None``) and return it
        with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, fact_id: int) -> CanonicalFact | None:
        """Return the fact with this id, or ``None`` if none exists."""

        raise NotImplementedError

    @abstractmethod
    def get_by_review_candidate(
        self,
        review_candidate_id: int,
    ) -> CanonicalFact | None:
        """
        Return the fact already canonicalized from this Review
        Candidate, if one exists - used to make canonicalization
        idempotent.
        """

        raise NotImplementedError

    @abstractmethod
    def list_by_project(self, project_id: int) -> list[CanonicalFact]:
        """Return every fact canonicalized in this project."""

        raise NotImplementedError

    @abstractmethod
    def list_by_document(self, document_id: int) -> list[CanonicalFact]:
        """Return every fact citing at least one evidence entry from
        this document."""

        raise NotImplementedError
