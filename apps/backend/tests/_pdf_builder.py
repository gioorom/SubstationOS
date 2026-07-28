"""
Real PDFs, built in memory, for the Milestone 26.1 tests.

Deliberately generated rather than committed as binary fixtures: a
checked-in PDF is opaque to review - nobody can see what it contains
without opening it in a viewer - while these say in Python exactly what
text sits at what coordinates, which is what the assertions are about.

Uses PyMuPDF to *write*, which is not the code under test. The parser
reads bytes and cannot tell how they were produced.
"""

from __future__ import annotations

import fitz

# A page big enough for coordinates to be meaningful, small enough to
# read in a failure message. A4 in points.
PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0


def single_page_pdf(
    text: str = "Rated voltage 145 kV",
    *,
    font_size: float = 11.0,
    position: tuple[float, float] = (72.0, 100.0),
) -> bytes:
    """One page carrying one line of text."""

    return build_pdf([[(text, position, font_size)]])


def multi_page_pdf(*page_texts: str) -> bytes:
    """One page per argument, each carrying one line."""

    return build_pdf(
        [[(text, (72.0, 100.0), 11.0)] for text in page_texts]
    )


def pdf_with_empty_page() -> bytes:
    """Page 1 carries text; page 2 is deliberately blank - a fact about
    the document, not an error."""

    return build_pdf([[("Bay 21 layout", (72.0, 100.0), 11.0)], []])


def empty_page_only_pdf() -> bytes:
    """A valid PDF with one page and no content at all - the shape a
    scanned-but-unOCRed or genuinely blank document takes."""

    return build_pdf([[]])


def build_pdf(pages) -> bytes:
    """
    ``pages`` is a sequence of pages, each a sequence of
    ``(text, (x, y), font_size)`` placements.
    """

    document = fitz.open()

    for placements in pages:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

        for text, (x, y), font_size in placements:
            page.insert_text((x, y), text, fontsize=font_size)

    content = document.tobytes()
    document.close()

    return content


def encrypted_pdf(password: str = "substation") -> bytes:
    """A password-protected PDF. Intact bytes that nobody without the
    password may read - deliberately different from a corrupted one."""

    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text((72.0, 100.0), "Confidential relay settings")

    content = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
    )
    document.close()

    return content


def corrupted_pdf() -> bytes:
    """A PDF header followed by damage - it announces itself as a PDF and
    is not one, which is exactly the case that must not be mistaken for
    "unsupported format"."""

    return b"%PDF-1.7\n" + b"\x00\xff" * 64


def pdf_with_image() -> bytes:
    """A page carrying a raster image and one line of text, so an image
    block is observed alongside a text block."""

    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text((72.0, 100.0), "Site photograph")

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    pixmap.set_rect(pixmap.irect, (200, 30, 30))
    page.insert_image(fitz.Rect(72, 200, 172, 300), pixmap=pixmap)

    content = document.tobytes()
    document.close()

    return content
