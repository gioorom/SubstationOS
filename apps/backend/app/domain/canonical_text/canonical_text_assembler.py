"""
Rendering a canonical segmentation back into plain text (Milestone 26.2).

Some consumers - the Knowledge Graph's entity extractor, today - take a
single string. This is the smallest deterministic way to give them one
**from the segmentation**, so that no consumer needs its own PDF decoder.

## The policy, in full

```
for each page that produced any text, in page order:
    "--- PAGINA {page_number} ---"
    for each paragraph, in the parser's own order:
        for each line, in the parser's own order:
            the line's tokens, joined by single spaces
        lines joined by "\\n"
    paragraphs joined by "\\n\\n"
pages joined by "\\n\\n"
```

That is the whole rule. It is a pure function of the segmentation: no
configuration, no clock, no locale, no lookup.

## What it preserves

- **Original token text**, never the normalised form. This is the rule
  that matters most here. ``normalized_text`` exists for comparison and
  is NFKC-folded, which turns ``mm²`` into ``mm2``; feeding that to a
  semantic consumer would silently degrade the engineering text it reads.
  Superscripts, subscripts, Greek letters and electrical symbols reach
  downstream exactly as the document wrote them.
- **Page transitions**, marked, so a consumer can still tell which page
  something came from.
- **Paragraph and line transitions**, and the parser's own ordering of
  both. Nothing is re-ordered geometrically.

## What it must not do, and has no way to do

No heading inference, no table reconstruction, no merging of engineering
concepts, no abbreviation expansion, no spelling correction, no
reordering. It concatenates what the segmentation already decided, in the
order the segmentation already fixed. Every one of those judgements would
belong to a milestone that can be reviewed as a judgement.

## Known differences from the pre-26.2 text

The legacy extractor returned PyMuPDF's own ``get_text("text")`` output.
Two differences are deliberate and documented rather than smoothed over:

1. **Runs of whitespace inside a line collapse to a single space**,
   because tokenisation discarded the original spacing (Milestone 27.1).
   Any consumer matching on exact column alignment would see a
   difference; the current entity patterns are whitespace-tolerant.
2. **Paragraph transitions are a blank line**, where the legacy output
   used a single newline. The segmentation records the block boundary, so
   the assembler shows it.

Neither changes which characters a designation is made of - only the
whitespace between them.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
    CanonicalTextParagraph,
    CanonicalTextSection,
)

# Kept verbatim from the pre-26.2 extractor, deliberately. This marker is
# part of the string handed to a downstream consumer, so changing its
# wording would change that consumer's input for no reason anybody asked
# for. It is domain-realistic Italian, which CLAUDE.md permits for data.
PAGE_MARKER_TEMPLATE = "--- PAGINA {page_number} ---"

LINE_SEPARATOR = "\n"
PARAGRAPH_SEPARATOR = "\n\n"
PAGE_SEPARATOR = "\n\n"


def assemble_document_text(segmentation: CanonicalTextDocument) -> str:
    """
    Render a segmentation as plain text.

    Pages that produced no text are **omitted**, and the pages that
    remain keep their true page numbers - so a marker sequence may have
    gaps. That is honest: the gap says "page 4 carried nothing this
    system could read", where a renumbered marker would quietly claim
    page 4 was something it is not. It also matches what the pre-26.2
    extractor did.
    """

    return PAGE_SEPARATOR.join(
        _assemble_page(section)
        for section in segmentation.sections
        if not section.is_empty
    )


def _assemble_page(section: CanonicalTextSection) -> str:
    body = PARAGRAPH_SEPARATOR.join(
        _assemble_paragraph(paragraph)
        for paragraph in section.paragraphs
        if not paragraph.is_empty
    )

    marker = PAGE_MARKER_TEMPLATE.format(page_number=section.page_number)

    return f"{marker}\n{body}"


def _assemble_paragraph(paragraph: CanonicalTextParagraph) -> str:
    return LINE_SEPARATOR.join(
        line.text for line in paragraph.lines if not line.is_empty
    )
