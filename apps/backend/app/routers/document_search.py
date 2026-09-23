"""
Searching the documents of one project.

One endpoint, and it is nested under the project on purpose: there is
no route here that can be called without saying which project is being
searched, so isolation is a property of the URL rather than of every
caller remembering a parameter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.document_search import search_location, search_snippet
from app.domain.document_search.search_models import (
    DocumentMatches,
    SearchHit,
    SearchOutcome,
    SegmentKind,
)
from app.infrastructure.document_search.canonical_segment_reader import (
    CanonicalSegmentReader,
)
from app.infrastructure.document_search.sqlalchemy_document_search_repository import (  # noqa: E501
    SqlAlchemyDocumentSearchRepository,
)
from app.models.project import Project
from app.schemas.document_search import (
    ProjectSearchResponse,
    SearchDocumentResult,
    SearchHighlight,
    SearchLocation,
    SearchMatch,
    SearchSnippet,
    SearchSourceType,
    SearchTermSuggestion,
)
from app.services.document_search_service import (
    SEARCH_DEFAULT_PAGE_SIZE,
    SEARCH_MAX_PAGE_SIZE,
    DocumentSearchService,
)

router = APIRouter(
    prefix="/projects",
    tags=["Project Document Search"],
)

#: The longest query the endpoint will accept.
#:
#: The service keeps only the first handful of terms, but the string
#: itself still has to be folded and tokenized before that happens, and
#: an endpoint that accepts a megabyte of text does that work for
#: whoever asks. Long enough for any designation and a sentence around
#: it.
MAX_QUERY_CHARACTERS = 200

#: Which source family a result came from, said plainly.
_SOURCE_TYPES = {
    SegmentKind.PDF_LINE: SearchSourceType.PDF,
    SegmentKind.SPREADSHEET_ROW: SearchSourceType.SPREADSHEET,
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _service(db: Session) -> DocumentSearchService:
    return DocumentSearchService(
        SqlAlchemyDocumentSearchRepository(db),
        CanonicalSegmentReader(db),
    )


@router.get(
    "/{project_id}/search",
    response_model=ProjectSearchResponse,
    summary="Find what this project's documents say",
)
def search_project_documents(
    project_id: int,
    q: str = Query(
        default="",
        max_length=MAX_QUERY_CHARACTERS,
        description=(
            "What to look for. Terms are matched whole and every term "
            "must appear in the same place. Engineering designations "
            "keep their aspect prefix: -Q1 and Q1 are different."
        ),
    ),
    limit: int = Query(
        default=SEARCH_DEFAULT_PAGE_SIZE, ge=1, le=SEARCH_MAX_PAGE_SIZE
    ),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProjectSearchResponse:
    """
    Search the documents filed under one project.

    Only this project's documents are searched, and the project must
    exist: searching a project that does not exist is a mistake worth
    reporting, not an empty result that looks like "nothing found here".
    """

    if db.get(Project, project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} does not exist.",
        )

    outcome = _service(db).search(
        project_id=project_id, query=q, limit=limit, offset=offset
    )

    return _response(project_id, q, outcome)


def _response(
    project_id: int, query: str, outcome: SearchOutcome
) -> ProjectSearchResponse:
    """The outcome as the API presents it."""

    return ProjectSearchResponse(
        project_id=project_id,
        query=query,
        terms=list(outcome.terms),
        total_matches=outcome.total_segments,
        total_documents=outcome.total_documents,
        documents=[
            _document(group, outcome.terms) for group in outcome.documents
        ],
        suggestions=[
            SearchTermSuggestion(
                term=suggestion.term,
                present_variants=list(suggestion.present_variants),
            )
            for suggestion in outcome.suggestions
            if suggestion.present_variants
        ],
    )


def _document(
    group: DocumentMatches, terms: tuple[str, ...]
) -> SearchDocumentResult:
    """One document's matches, under its own identity."""

    return SearchDocumentResult(
        document_id=group.document_id,
        filename=group.document_filename,
        source_type=_SOURCE_TYPES[group.kind],
        content_checksum=group.content_checksum,
        matches=[_match(hit, terms) for hit in group.hits],
    )


def _match(hit: SearchHit, terms: tuple[str, ...]) -> SearchMatch:
    """
    One matching place: what it says, and where it is.

    The position of the first highlight is handed to the location so a
    hit inside a spreadsheet row can name the cell it actually fell in
    rather than only the row.
    """

    snippet = search_snippet.build(hit.text, terms)

    match_offset = (
        snippet.source_start + snippet.highlights[0].start
        if snippet.highlights
        else None
    )

    descriptor = search_location.describe(
        hit.kind, hit.location, match_offset=match_offset
    )

    return SearchMatch(
        location=SearchLocation(
            determined=descriptor.determined,
            page_number=descriptor.page_number,
            worksheet_name=descriptor.worksheet_name,
            row_number=descriptor.row_number,
            cell_reference=descriptor.cell_reference,
        ),
        snippet=SearchSnippet(
            text=snippet.text,
            highlights=[
                SearchHighlight(start=h.start, end=h.end)
                for h in snippet.highlights
            ],
            truncated_before=snippet.truncated_before,
            truncated_after=snippet.truncated_after,
        ),
    )
