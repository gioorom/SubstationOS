"""
The port a search goes through.

Three operations and nothing else: replace what is indexed for one
document, find segments within one project, and ask which designations
that project actually contains.

There is deliberately no "search everything". A caller that could omit
the project would eventually omit it by accident, and the isolation
this system promises would depend on every call site remembering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.document_search.search_models import (
    SearchPage,
    SearchSegment,
)


class DocumentSearchRepository(ABC):
    """Stores and queries the searchable projection of a document."""

    @abstractmethod
    def replace_for_document(
        self, document_id: int, segments: tuple[SearchSegment, ...]
    ) -> int:
        """
        Make ``segments`` the whole of what is indexed for this document,
        and return how many were stored.

        Replace rather than append, because indexing runs again whenever
        a document is re-processed and a second run must not double
        every hit. Replacing with nothing is how a document stops being
        findable, so no separate deletion is offered: this codebase has
        no way to delete a document, and a port method for a caller that
        cannot exist is a promise nothing keeps.

        The index is a projection of the canonical representation: it is
        rebuildable, it is never a source of truth, and discarding it
        costs nothing but the work to rebuild.
        """

        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        *,
        project_id: int,
        terms: tuple[str, ...],
        limit: int,
        offset: int,
    ) -> SearchPage:
        """
        Every segment in this project whose text contains **all** the
        terms, each matched whole.

        ``project_id`` is required and is applied in the query itself,
        not by filtering afterwards. An empty ``terms`` returns nothing:
        a query that asked for nothing has not asked for everything.
        """

        raise NotImplementedError

    @abstractmethod
    def terms_present(
        self, *, project_id: int, candidates: tuple[str, ...]
    ) -> frozenset[str]:
        """
        Which of ``candidates`` appear anywhere in this project's
        indexed text.

        Asked only to explain an empty result - to tell an engineer who
        searched ``Q1`` that the project writes ``-Q1``. It never
        widens a search on their behalf.
        """

        raise NotImplementedError
