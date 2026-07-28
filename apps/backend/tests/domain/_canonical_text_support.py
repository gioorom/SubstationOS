"""
Canonical PDF Representations, built by hand, for the Milestone 27.1
tests.

Hand-built rather than parsed from a PDF on purpose: segmentation's input
is the representation, not a file, and its tests should be able to state
exactly what spans and line indices go in. The PyMuPDF adapter has its
own tests for turning bytes into these values.

Built **through the canonical factory**, so a test can never construct a
representation the system itself could not produce - a page sequence with
a hole in it, say, which the factory refuses and which would make a
passing test meaningless.
"""

from __future__ import annotations

from app.domain.canonical_pdf import canonical_pdf_factory
from app.domain.canonical_pdf.canonical_pdf_models import (
    BoundingBox,
    CanonicalBlockKind,
    CanonicalPdfBlock,
    CanonicalPdfPage,
    CanonicalPdfSpan,
    TextStyle,
)

CHECKSUM = "c" * 64
BOX = BoundingBox(0.0, 0.0, 10.0, 10.0)
STYLE = TextStyle(font_family="Helvetica", font_size=11.0, bold=False, italic=False)


def span(
    reading_order: int, line_index: int, text: str
) -> CanonicalPdfSpan:
    return CanonicalPdfSpan(
        reading_order=reading_order,
        line_index=line_index,
        text=text,
        bounding_box=BOX,
        style=STYLE,
    )


def text_block(reading_order: int, *spans: CanonicalPdfSpan):
    return CanonicalPdfBlock(
        reading_order=reading_order,
        kind=CanonicalBlockKind.TEXT,
        bounding_box=BOX,
        spans=spans,
    )


def image_block(reading_order: int) -> CanonicalPdfBlock:
    return CanonicalPdfBlock(
        reading_order=reading_order,
        kind=CanonicalBlockKind.IMAGE,
        bounding_box=BOX,
    )


def page(page_number: int, *blocks: CanonicalPdfBlock) -> CanonicalPdfPage:
    return CanonicalPdfPage(
        page_number=page_number, width=595.0, height=842.0, blocks=blocks
    )


def representation(*pages: CanonicalPdfPage, **overrides):
    defaults = dict(
        document_id=7,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
        representation_version="1.0",
        parser_name="pymupdf",
        parser_version="1.28.0",
        pages=pages,
    )
    defaults.update(overrides)

    return canonical_pdf_factory.build_document(**defaults)


def simple_representation(text: str = "Rated voltage 145 kV", **overrides):
    """One page, one block, one line, one span."""

    return representation(
        page(1, text_block(0, span(0, 0, text))), **overrides
    )
