"""
The segmenter (Milestone 27.1) - the pure function that turns a Canonical
PDF Representation into a Canonical Text Document.

```
CanonicalPdfDocument            CanonicalTextDocument
  page               ------->     section      (page transition)
    block            ------->       paragraph  (block boundary)
      span.line_index ------>         line     (line boundary)
        span text     ------>           token  (whitespace)
```

Four mappings, and each one is a boundary **the parser already
observed**: a page transition, a block boundary, the line index Milestone
26.1 preserved on every span, and whitespace. Nothing here measures a
gap, compares a font size, or decides that a short line in bold is a
heading. Those are the inferences this milestone exists to not make.

Pure and deterministic: same representation in, equal segmentation out,
every time. No I/O, no clock, no randomness, and - because the value
objects carry no timestamp - the equality that proves it is directly
assertable.

**It never reopens the PDF.** It cannot: it takes value objects, and this
module imports nothing that could read a file.
"""

from __future__ import annotations

from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalPdfBlock,
    CanonicalPdfDocument,
    CanonicalPdfPage,
    CanonicalPdfSpan,
)
from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
    CanonicalTextLine,
    CanonicalTextParagraph,
    CanonicalTextSection,
    CanonicalTextToken,
    SpanProvenance,
)
from app.domain.canonical_text.canonical_text_normalization import (
    normalize_token_text,
)
from app.domain.canonical_text.canonical_text_policy import (
    CANONICAL_SEGMENTATION_VERSION,
)


def segment_canonical_document(
    representation: CanonicalPdfDocument,
    *,
    segmentation_version: str = CANONICAL_SEGMENTATION_VERSION,
) -> CanonicalTextDocument:
    """
    Segment one Canonical PDF Representation.

    Empty structures are **kept**, not pruned: a page with no text is
    still a page, and dropping it would renumber everything after it and
    break the correspondence between a section and the page an engineer
    is looking at. The same holds for a block that tokenises to nothing.
    """

    return CanonicalTextDocument(
        document_id=representation.document_id,
        content_checksum=representation.content_checksum,
        representation_version=representation.representation_version,
        segmentation_version=segmentation_version,
        sections=tuple(
            _segment_page(section_index, page)
            for section_index, page in enumerate(representation.pages)
        ),
    )


def _segment_page(
    section_index: int, page: CanonicalPdfPage
) -> CanonicalTextSection:
    """One page becomes one section. The page transition is a boundary
    the parser observed; a chapter is not."""

    return CanonicalTextSection(
        section_index=section_index,
        page_number=page.page_number,
        paragraphs=tuple(
            _segment_block(paragraph_index, page.page_number, block)
            for paragraph_index, block in enumerate(page.blocks)
        ),
    )


def _segment_block(
    paragraph_index: int, page_number: int, block: CanonicalPdfBlock
) -> CanonicalTextParagraph:
    """
    One block becomes one paragraph.

    An image block yields a paragraph with no lines rather than being
    skipped: the parser saw something there, and a paragraph index that
    silently jumped would stop matching the representation's own block
    ordering.
    """

    return CanonicalTextParagraph(
        paragraph_index=paragraph_index,
        page_number=page_number,
        block_reading_order=block.reading_order,
        lines=_segment_lines(page_number, block),
    )


def _segment_lines(
    page_number: int, block: CanonicalPdfBlock
) -> tuple[CanonicalTextLine, ...]:
    """
    Spans are grouped by the ``line_index`` the parser gave them.

    Grouped in first-appearance order and never sorted: the parser's
    ordering is the one the representation records, and re-ordering here
    would reintroduce exactly the geometric guessing Milestone 26.1
    refused.
    """

    spans_by_line: dict[int, list[CanonicalPdfSpan]] = {}

    for span in block.spans:
        spans_by_line.setdefault(span.line_index, []).append(span)

    return tuple(
        _segment_line(page_number, block, line_index, spans)
        for line_index, spans in spans_by_line.items()
    )


def _segment_line(
    page_number: int,
    block: CanonicalPdfBlock,
    line_index: int,
    spans: list[CanonicalPdfSpan],
) -> CanonicalTextLine:
    tokens: list[CanonicalTextToken] = []

    for span in spans:
        for start, end in _token_boundaries(span.text):
            text = span.text[start:end]
            normalized = normalize_token_text(text)

            if not normalized:
                # A run of characters that normalises to nothing - a
                # lone soft hyphen, a zero-width space. Recording it
                # would give every extractor a token with no content to
                # match on; the original characters remain in the
                # representation either way.
                continue

            tokens.append(
                CanonicalTextToken(
                    position=len(tokens),
                    text=text,
                    normalized_text=normalized,
                    provenance=SpanProvenance(
                        page_number=page_number,
                        block_reading_order=block.reading_order,
                        span_reading_order=span.reading_order,
                        line_index=line_index,
                        character_start=start,
                        character_end=end,
                    ),
                )
            )

    return CanonicalTextLine(line_index=line_index, tokens=tuple(tokens))


def _token_boundaries(text: str) -> tuple[tuple[int, int], ...]:
    """
    The half-open character ranges of the whitespace-delimited runs in
    ``text``.

    Offsets rather than substrings, because the offsets are the
    provenance: a token has to be locatable inside the span it came from,
    not merely equal to some substring of it.

    Whitespace is ``str.isspace``, which is the Unicode definition -
    non-breaking and thin spaces included, both of which occur routinely
    in PDF text. Splitting on anything narrower would join words that the
    document shows apart.
    """

    boundaries: list[tuple[int, int]] = []
    start: int | None = None

    for index, character in enumerate(text):
        if character.isspace():
            if start is not None:
                boundaries.append((start, index))
                start = None
        elif start is None:
            start = index

    if start is not None:
        boundaries.append((start, len(text)))

    return tuple(boundaries)
