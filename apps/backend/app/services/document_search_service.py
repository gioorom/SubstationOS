"""
Indexing a document, and searching a project.

Two use cases, kept together because they are two halves of one
promise: what indexing writes is exactly what searching can find, and
nothing else in the system may add to the index behind their backs.

**Searching is scoped to a project and cannot be talked out of it.**
Every method here takes a ``project_id`` and passes it to the
repository, which applies it inside the query. There is no path through
this service that searches more than one project.
"""

from __future__ import annotations

from app.domain.document_search.search_models import (
    DocumentMatches,
    SearchHit,
    SearchOutcome,
    SearchSegment,
    TermSuggestion,
)
from app.domain.document_search.search_normalization import (
    prefixed_variants,
    terms as parse_terms,
    unprefixed,
)
from app.domain.document_search.search_repository import (
    DocumentSearchRepository,
)
from app.domain.document_search.segment_reader import DocumentSegmentReader

#: The most segments one page of results may contain.
#:
#: A ceiling the caller cannot raise: a page size is a display choice,
#: but an unbounded one is a way to read a whole project's text through
#: a search endpoint.
#:
#: Named apart from ``app.domain.shared_kernel.pagination``'s constants
#: rather than reusing them, because a search page carries a snippet per
#: row and is far heavier than a page of the registry, and because two
#: different values under one name is how a caller ends up importing the
#: wrong ceiling.
SEARCH_MAX_PAGE_SIZE = 50

SEARCH_DEFAULT_PAGE_SIZE = 20

#: The most terms one query may ask for.
#:
#: Each term becomes a separate ``LIKE`` over the project's text, so an
#: unbounded query is an unbounded amount of work bought with one
#: request - and past roughly a thousand, SQLite refuses the expression
#: tree outright and the endpoint fails with no explanation. A query
#: longer than this is not an engineer looking for a designation.
MAX_QUERY_TERMS = 24


class DocumentSearchService:
    """Builds and queries the searchable projection of documents."""

    def __init__(
        self,
        repository: DocumentSearchRepository,
        reader: DocumentSegmentReader,
    ) -> None:
        self._repository = repository
        self._reader = reader

    def index_document(self, document_id: int) -> int:
        """
        Make the index for this document match its canonical
        representation, and return how many segments it now holds.

        Safe to call again at any time: it replaces rather than adds, so
        re-processing a document cannot double its hits. A document with
        no canonical representation indexes to nothing, which also
        clears anything indexed for it earlier - a document that can no
        longer be read must stop answering searches.
        """

        segments: tuple[SearchSegment, ...] = self._reader.segments_for(
            document_id
        )

        return self._repository.replace_for_document(document_id, segments)

    def search(
        self,
        *,
        project_id: int,
        query: str,
        limit: int = SEARCH_DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> SearchOutcome:
        """
        What this project's documents say that matches ``query``.

        The query is split into terms and every term must appear in the
        same segment. Hits are grouped under the document they came
        from, because an engineer looks for a document first and a
        position inside it second.

        A query with no terms in it - empty, or nothing but punctuation
        - returns an empty outcome rather than everything. Asking for
        nothing is not asking for all of it.
        """

        wanted = parse_terms(query)[:MAX_QUERY_TERMS]

        if not wanted:
            return SearchOutcome(terms=())

        page = self._repository.search(
            project_id=project_id,
            terms=wanted,
            limit=_bounded(limit),
            offset=max(0, offset),
        )

        if page.total_segments == 0:
            return SearchOutcome(
                terms=wanted,
                suggestions=self._explain(project_id, wanted),
            )

        # An empty page of a non-empty result - somebody scrolled past
        # the end. The totals still describe the whole result, and no
        # explanation is owed for a query that matched.
        return SearchOutcome(
            terms=wanted,
            documents=_group(page.hits),
            total_segments=page.total_segments,
            total_documents=page.total_documents,
        )

    def _explain(
        self, project_id: int, wanted: tuple[str, ...]
    ) -> tuple[TermSuggestion, ...]:
        """
        Why a search found nothing, told in terms of what the project
        does contain.

        A suggestion is offered only for a term that matches nothing **on
        its own**. In ``TR1 XYZ`` it is ``XYZ`` that failed; telling the
        engineer that ``TR1`` was the problem, because the query as a
        whole returned nothing, would be saying something untrue about
        their own query.

        For each failing term, the designations that differ from it only
        by an IEC 81346 aspect prefix are reported. They are never
        substituted: ``-Q1`` and ``Q1`` are different designations and
        only the engineer can say which they meant.
        """

        candidates: set[str] = set(wanted)

        for term in wanted:
            candidates.update(_variants_of(term))

        present = self._repository.terms_present(
            project_id=project_id, candidates=tuple(sorted(candidates))
        )

        return tuple(
            TermSuggestion(
                term=term,
                present_variants=tuple(
                    variant
                    for variant in _variants_of(term)
                    if variant in present
                ),
            )
            for term in wanted
            if term not in present
        )


def _variants_of(term: str) -> tuple[str, ...]:
    """Every aspect-prefix relative of ``term``, in a fixed order."""

    bare = unprefixed(term)

    return (bare,) if bare is not None else prefixed_variants(term)


def _bounded(limit: int) -> int:
    """
    ``limit`` brought inside what a page may hold.

    The router already refuses anything outside the range, so this is
    the guarantee for any other caller of this service rather than a
    second line of defence for that one.
    """

    if limit < 1:
        return SEARCH_DEFAULT_PAGE_SIZE

    return min(limit, SEARCH_MAX_PAGE_SIZE)


def _group(hits: tuple[SearchHit, ...]) -> tuple[DocumentMatches, ...]:
    """
    Consecutive hits from the same document *and the same source
    family*, gathered together.

    Grouping relies on the repository's ordering placing a document's
    hits together, which it guarantees. The kind is part of the key
    because a group reports one ``kind`` for all its hits: a document
    that somehow carried both a PDF representation and a workbook would
    otherwise have half its hits labelled with the other family's
    source type.

    Documents keep the order their first hit arrived in, so the result
    is as deterministic as the query that produced it.
    """

    groups: list[DocumentMatches] = []
    current: list[SearchHit] = []

    for hit in hits:
        if current and (hit.document_id, hit.kind) != (
            current[0].document_id,
            current[0].kind,
        ):
            groups.append(_close(current))
            current = []

        current.append(hit)

    if current:
        groups.append(_close(current))

    return tuple(groups)


def _close(hits: list[SearchHit]) -> DocumentMatches:
    """One document's hits, under that document's identity."""

    first = hits[0]

    return DocumentMatches(
        document_id=first.document_id,
        document_filename=first.document_filename,
        content_checksum=first.content_checksum,
        kind=first.kind,
        hits=tuple(hits),
    )
