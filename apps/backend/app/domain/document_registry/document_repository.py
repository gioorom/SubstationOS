"""
The port onto the document registry.

Two reads, and the shape of the first is the point of this milestone:
``list_page`` takes a governed query and returns **one page plus a
total**. It does not return a list for someone else to slice. An adapter
that loaded the table and paginated in Python would satisfy the type and
defeat the purpose, so a test asserts the query is bounded.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.document_registry.document_models import (
    DocumentDetail,
    DocumentSummary,
)
from app.domain.document_registry.document_query import DocumentQuery
from app.domain.shared_kernel.pagination import Page


class DocumentRegistryRepository(ABC):
    """Read-only access to the registry of documents."""

    @abstractmethod
    def list_page(self, query: DocumentQuery) -> Page[DocumentSummary]:
        """
        Return the requested page of documents and the total number
        matching the query.

        The filtering, ordering, offset, limit and count are all the
        adapter's work. The caller never sees more rows than it asked
        for.
        """

        raise NotImplementedError

    @abstractmethod
    def find_detail(self, document_id: int) -> DocumentDetail | None:
        """
        Return the full public record of one document, or ``None`` if no
        such document exists.

        ``None`` is *not found* and nothing else. A registry read that
        fails for an infrastructure reason raises
        ``DocumentPersistenceError`` - conflating the two would report a
        broken database as a missing document.

        ``content_available`` on the returned detail is resolved through
        the content port by the caller's composition root, not here: this
        port answers questions about the registry, not about storage.
        """

        raise NotImplementedError
