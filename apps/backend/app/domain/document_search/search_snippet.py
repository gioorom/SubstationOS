"""
The piece of a segment an engineer is shown, and where the match is
inside it.

A hit is only useful if the reader can see *why* it is a hit. A snippet
therefore always carries the offsets of the terms that matched, so what
is highlighted is what was searched for and nothing else is emphasised
on its behalf.

Snippets are cut from the **source text**, never from the normalized
form. The engineer must read what the document says - ``150/20 kV``,
``-Q1`` - not what the matcher made of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.document_search.search_normalization import (
    tokenize_with_spans,
)

#: The most source characters a snippet shows.
#:
#: Wide enough for a drawing's title block line or a spreadsheet cell to
#: arrive whole, narrow enough that a result list stays readable.
MAX_SNIPPET_CHARACTERS = 240

#: How much text is kept before the first match when a segment has to be
#: cut. Enough to see what the match is part of.
LEADING_CONTEXT_CHARACTERS = 60


@dataclass(frozen=True, slots=True)
class Highlight:
    """
    A matched term's position **within the snippet**, not within the
    segment, because the snippet is what the reader is looking at.
    """

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Snippet:
    """
    What to show for one hit.

    ``truncated_before`` and ``truncated_after`` say that text was cut,
    so the reader is never left believing a line was shorter than it is.
    """

    text: str
    highlights: tuple[Highlight, ...]
    truncated_before: bool
    truncated_after: bool
    source_start: int = 0
    """
    Where this snippet begins inside the segment it was cut from.

    Carried so a highlight can be turned back into a position in the
    segment - which is how a hit in a spreadsheet row works out which
    cell it is really in.
    """


#: How far a cut may travel to reach a word boundary.
#:
#: Bounded, because the boundary might not exist: a drawing's text can
#: arrive as one unbroken run of characters, and a snap that searched
#: for a space it would never find would return the whole line and quietly
#: undo the limit it was meant to respect. Beyond this distance the cut
#: is made where it falls.
BOUNDARY_TOLERANCE_CHARACTERS = 40


def _snap_forward(text: str, index: int) -> int:
    """The next word boundary at or shortly after ``index``."""

    limit = min(len(text), index + BOUNDARY_TOLERANCE_CHARACTERS)
    boundary = index

    while boundary < limit and not text[boundary].isspace():
        boundary += 1

    return boundary if boundary < limit else index


def _snap_backward(text: str, index: int) -> int:
    """The previous word boundary at or shortly before ``index``."""

    limit = max(0, index - BOUNDARY_TOLERANCE_CHARACTERS)
    boundary = index

    while boundary > limit and not text[boundary - 1].isspace():
        boundary -= 1

    return boundary if boundary > limit else index


def _untargeted(text: str) -> Snippet:
    """The opening of ``text``, highlighting nothing."""

    end = (
        len(text)
        if len(text) <= MAX_SNIPPET_CHARACTERS
        else _snap_forward(text, MAX_SNIPPET_CHARACTERS)
    )

    return Snippet(
        text=text[:end],
        highlights=(),
        truncated_before=False,
        truncated_after=end < len(text),
    )


def build(text: str, matched_terms: tuple[str, ...]) -> Snippet:
    """
    A snippet of ``text`` centred on the first of ``matched_terms`` that
    it contains, with every matched term inside the window highlighted.

    A segment shorter than ``MAX_SNIPPET_CHARACTERS`` is returned whole:
    most are one line of a drawing or one cell of a workbook, and
    trimming those would hide the context for no gain.

    When none of the terms is found - which should not happen for a hit,
    but a display must not depend on that - the opening of the text is
    returned with nothing highlighted. Nothing is invented to fill the
    gap.
    """

    wanted = frozenset(matched_terms)
    spans = [
        span for span in tokenize_with_spans(text) if span.term in wanted
    ]

    if not spans:
        return _untargeted(text)

    if len(text) <= MAX_SNIPPET_CHARACTERS:
        start, end = 0, len(text)
    else:
        start = _snap_backward(
            text, max(0, spans[0].start - LEADING_CONTEXT_CHARACTERS)
        )
        end = _snap_forward(
            text, min(len(text), start + MAX_SNIPPET_CHARACTERS)
        )

    highlights = tuple(
        Highlight(start=span.start - start, end=span.end - start)
        for span in spans
        if span.start >= start and span.end <= end
    )

    return Snippet(
        text=text[start:end],
        highlights=highlights,
        truncated_before=start > 0,
        truncated_after=end < len(text),
        source_start=start,
    )
