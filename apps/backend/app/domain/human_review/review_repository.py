"""
The port reviews are appended and read through.

**Append and read. There is no update and no delete**, and their absence
is the contract rather than an omission - the same discipline the audit
trail follows, for the same reason. A judgement an application can edit
afterwards is not a record of what anybody decided.

An architecture test asserts this interface declares no mutating method,
so the guarantee survives somebody adding one to an implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.human_review.review_models import Review
from app.domain.human_review.review_target import ReviewTarget
from app.domain.shared_kernel.pagination import Page, PageRequest


class ReviewRepository(ABC):
    """Stores and reads engineering judgements."""

    @abstractmethod
    def append(self, review: Review) -> Review:
        """
        Records one review and returns it with its assigned id.

        The only write this context has. It never replaces a row, and an
        implementation that did would break the append-only guarantee the
        whole context rests on.
        """

        raise NotImplementedError

    @abstractmethod
    def history_for(
        self, target: ReviewTarget, page: PageRequest
    ) -> Page[Review]:
        """
        One page of a target's history, **newest first**.

        The ordering is part of the contract, not a convenience: the
        current decision is defined as the newest review, so a repository
        that returned them in another order would silently change which
        judgement is in force.

        Ties are broken by descending id, so two reviews recorded in the
        same clock tick have a stable order rather than one the database
        chose.
        """

        raise NotImplementedError

    @abstractmethod
    def latest_for(self, target: ReviewTarget) -> Review | None:
        """
        The newest review for one target, or ``None``.

        The projection's fast path: reading the current decision must not
        require paging through a history that only grows.
        """

        raise NotImplementedError

    @abstractmethod
    def latest_for_document(
        self, document_id: int
    ) -> tuple[Review, ...]:
        """
        The newest review of every reviewed target in one document.

        Exists so the Workspace can badge a list of statements with one
        request rather than one per statement. Ordered by target key, so
        two reads produce the same list.
        """

        raise NotImplementedError

    @abstractmethod
    def count_for(self, target: ReviewTarget) -> int:
        """How many reviews a target has, including superseded ones."""

        raise NotImplementedError
