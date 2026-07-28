"""
Construction of canonical PDF value objects, with the invariants enforced
at the moment of construction (Milestone 26.1).

The parser adapter calls this factory rather than instantiating the value
objects directly, so there is exactly one place a malformed
representation can be caught - and it is *before* the representation
exists, not after it reached storage and started being trusted.

The factory takes explicit, typed arguments. It never accepts a
dictionary: a parser's raw output shape is the adapter's problem, and
letting it through to here would make the domain depend on a library's
JSON layout.

**It adds nothing.** No sorting, no merging, no de-duplication, no
whitespace repair. It checks that what it was given is internally
coherent and refuses it otherwise - that is the whole job.
"""

from __future__ import annotations

from app.domain.canonical_pdf.canonical_pdf_exceptions import (
    InvalidCanonicalRepresentationError,
)
from app.domain.canonical_pdf.canonical_pdf_models import (
    BoundingBox,
    CanonicalBlockKind,
    CanonicalPdfBlock,
    CanonicalPdfDocument,
    CanonicalPdfPage,
    CanonicalPdfSpan,
    TextStyle,
)


def build_bounding_box(
    x0: float, y0: float, x1: float, y1: float
) -> BoundingBox:
    """A rectangle whose corners are the wrong way round is a parser
    fault, not a rectangle to be quietly straightened out - swapping the
    corners would hide the fault and produce a box that was never
    observed."""

    if x1 < x0 or y1 < y0:
        raise InvalidCanonicalRepresentationError(
            f"Bounding box ({x0}, {y0}, {x1}, {y1}) has a corner reversed."
        )

    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def build_span(
    *,
    reading_order: int,
    line_index: int,
    text: str,
    bounding_box: BoundingBox,
    font_family: str,
    font_size: float,
    bold: bool,
    italic: bool,
) -> CanonicalPdfSpan:
    if reading_order < 0 or line_index < 0:
        raise InvalidCanonicalRepresentationError(
            f"Span position ({reading_order}, line {line_index}) is "
            "negative."
        )

    if font_size < 0:
        raise InvalidCanonicalRepresentationError(
            f"Span font size {font_size} is negative."
        )

    return CanonicalPdfSpan(
        reading_order=reading_order,
        line_index=line_index,
        text=text,
        bounding_box=bounding_box,
        style=TextStyle(
            font_family=font_family,
            font_size=font_size,
            bold=bold,
            italic=italic,
        ),
    )


def build_block(
    *,
    reading_order: int,
    kind: CanonicalBlockKind,
    bounding_box: BoundingBox,
    spans: tuple[CanonicalPdfSpan, ...] = (),
) -> CanonicalPdfBlock:
    if reading_order < 0:
        raise InvalidCanonicalRepresentationError(
            f"Block reading order {reading_order} is negative."
        )

    if kind is CanonicalBlockKind.IMAGE and spans:
        raise InvalidCanonicalRepresentationError(
            f"Image block {reading_order} carries {len(spans)} text "
            "spans; the parser reported it as an image."
        )

    _require_contiguous_reading_order(
        tuple(span.reading_order for span in spans),
        f"block {reading_order}",
    )

    return CanonicalPdfBlock(
        reading_order=reading_order,
        kind=kind,
        bounding_box=bounding_box,
        spans=spans,
    )


def build_page(
    *,
    page_number: int,
    width: float,
    height: float,
    blocks: tuple[CanonicalPdfBlock, ...] = (),
) -> CanonicalPdfPage:
    if page_number < 1:
        raise InvalidCanonicalRepresentationError(
            f"Page number {page_number} is not 1-based."
        )

    if width < 0 or height < 0:
        raise InvalidCanonicalRepresentationError(
            f"Page {page_number} has a negative dimension "
            f"({width} x {height})."
        )

    _require_contiguous_reading_order(
        tuple(block.reading_order for block in blocks), f"page {page_number}"
    )

    return CanonicalPdfPage(
        page_number=page_number, width=width, height=height, blocks=blocks
    )


def build_document(
    *,
    document_id: int,
    content_checksum: str,
    checksum_algorithm: str,
    representation_version: str,
    parser_name: str,
    parser_version: str,
    pages: tuple[CanonicalPdfPage, ...] = (),
) -> CanonicalPdfDocument:
    """
    Pages must be 1..n, in order, with no gaps. A representation missing
    page 4 would be indistinguishable from a document that never had one,
    and every downstream page reference would be wrong from there on.
    """

    expected = tuple(range(1, len(pages) + 1))
    actual = tuple(page.page_number for page in pages)

    if actual != expected:
        raise InvalidCanonicalRepresentationError(
            f"Pages are {actual}; expected a contiguous 1-based sequence "
            f"{expected}."
        )

    if not content_checksum.strip():
        raise InvalidCanonicalRepresentationError(
            "A representation must record the checksum of the bytes it "
            "was built from; without it, nothing ties it to a document "
            "version."
        )

    return CanonicalPdfDocument(
        document_id=document_id,
        content_checksum=content_checksum,
        checksum_algorithm=checksum_algorithm,
        representation_version=representation_version,
        parser_name=parser_name,
        parser_version=parser_version,
        pages=pages,
    )


def _require_contiguous_reading_order(
    positions: tuple[int, ...], where: str
) -> None:
    """The parser's own order, preserved without holes. A gap would mean
    something was dropped on the way in - and a representation that
    quietly lost content is worse than one that failed loudly."""

    expected = tuple(range(len(positions)))

    if positions != expected:
        raise InvalidCanonicalRepresentationError(
            f"Reading order in {where} is {positions}; expected "
            f"{expected}."
        )
