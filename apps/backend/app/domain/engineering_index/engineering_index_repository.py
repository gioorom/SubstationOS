from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry


class EngineeringIndexRepository(ABC):
    """
    Port for persisting and querying Engineering Index entries. The
    domain depends only on this contract; an infrastructure adapter
    (e.g. ``SqlAlchemyEngineeringIndexRepository``) provides the
    implementation.
    """

    @abstractmethod
    def save(self, entry: IndexEntry) -> IndexEntry:
        """Insert a new entry and return it with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, entry_id: int) -> IndexEntry | None:
        """Return the entry with this id, or ``None`` if none exists."""

        raise NotImplementedError

    @abstractmethod
    def list_by_document(self, document_id: int) -> list[IndexEntry]:
        """Return every entry recorded for this document."""

        raise NotImplementedError

    @abstractmethod
    def list_by_project(
        self,
        project_id: int,
        *,
        kind: EngineeringIndexEntryKind | None = None,
    ) -> list[IndexEntry]:
        """
        Return every entry recorded for this project, optionally
        filtered to a single kind.
        """

        raise NotImplementedError

    @abstractmethod
    def search_by_identifier(
        self,
        project_id: int,
        identifier: str,
    ) -> list[IndexEntry]:
        """
        Return every entry in this project whose identifier matches
        (case-insensitively) - "which documents mention X?"
        (architecture doc §5).
        """

        raise NotImplementedError

    @abstractmethod
    def replace_for_document(
        self,
        document_id: int,
        project_id: int,
        entries: list[IndexEntry],
    ) -> list[IndexEntry]:
        """
        Atomically replace every entry recorded for ``document_id`` with
        ``entries``: the previous entries are removed and the new ones
        inserted as a single transaction, so a rebuild is idempotent
        (same input leaves the same state, never accumulates
        duplicates) and never leaves the document's index partially
        replaced.
        """

        raise NotImplementedError

    @abstractmethod
    def delete_by_document(self, document_id: int) -> None:
        """
        Remove every entry recorded for ``document_id``, without
        touching the document itself.
        """

        raise NotImplementedError
