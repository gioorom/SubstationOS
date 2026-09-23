"""
What a search looks like from outside the backend.

These shapes are written for an electrical engineer, not for this
system's internals. Nothing here mentions segments, canonical
representations, spans or artifact identities: a reader is told which
document, where in it, and what it says. How the platform came to know
that is not their problem.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SearchSourceType(str, Enum):
    """The kind of document a result came from, named as a person would
    name it."""

    PDF = "pdf"
    SPREADSHEET = "spreadsheet"


class SearchHighlight(BaseModel):
    """Where a searched term sits inside the snippet."""

    start: int = Field(description="First character of the match.")
    end: int = Field(description="One past the last character.")


class SearchSnippet(BaseModel):
    """The text shown for a match, and what to emphasise in it."""

    text: str = Field(
        description="The source text, exactly as the document has it."
    )
    highlights: list[SearchHighlight] = Field(
        default_factory=list,
        description="Positions of the searched terms within the text.",
    )
    truncated_before: bool = Field(
        default=False,
        description="Text was cut from the start of this snippet.",
    )
    truncated_after: bool = Field(
        default=False,
        description="Text was cut from the end of this snippet.",
    )


class SearchLocation(BaseModel):
    """
    Where a match is inside its document.

    ``determined`` is false when the source did not record a position.
    In that case every other field is null and no position is implied -
    the platform does not guess at a page number.
    """

    determined: bool = Field(
        description="Whether the position inside the document is known."
    )
    page_number: int | None = Field(
        default=None, description="1-based page, for a PDF."
    )
    worksheet_name: str | None = Field(
        default=None, description="Sheet name, for a spreadsheet."
    )
    row_number: int | None = Field(
        default=None, description="1-based row, for a spreadsheet."
    )
    cell_reference: str | None = Field(
        default=None,
        description="Cell in A1 notation, when the exact cell is known.",
    )


class SearchMatch(BaseModel):
    """One place in one document that matches the query."""

    location: SearchLocation
    snippet: SearchSnippet


class SearchDocumentResult(BaseModel):
    """
    Every match found in one document.

    Results arrive grouped this way because an engineer looks for a
    document first and a position inside it second.
    """

    document_id: int
    filename: str
    source_type: SearchSourceType
    content_checksum: str | None = Field(
        default=None,
        description=(
            "Digest of the document version these matches were read "
            "from. Null for documents stored before versions were "
            "recorded."
        ),
    )
    matches: list[SearchMatch] = Field(default_factory=list)


class SearchTermSuggestion(BaseModel):
    """
    A term that matched nothing, and the designations this project does
    contain that differ from it only by an IEC 81346 aspect prefix.

    Offered so an empty result can be understood. The search is not
    rerun with them: ``-Q1`` and ``Q1`` are different designations, and
    which one was meant is the engineer's call.
    """

    term: str
    present_variants: list[str] = Field(default_factory=list)


class ProjectSearchResponse(BaseModel):
    """The answer to one search within one project."""

    project_id: int
    query: str = Field(description="What was typed, unchanged.")
    terms: list[str] = Field(
        default_factory=list,
        description=(
            "What was actually searched for once case and accents were "
            "folded. Shown so the reader can see how their query was "
            "read."
        ),
    )
    total_matches: int = Field(
        default=0, description="Matching places across the project."
    )
    total_documents: int = Field(
        default=0, description="Documents containing at least one match."
    )
    documents: list[SearchDocumentResult] = Field(default_factory=list)
    suggestions: list[SearchTermSuggestion] = Field(
        default_factory=list,
        description="Populated only when nothing matched.",
    )
