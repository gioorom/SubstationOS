"""
Tests for the PyMuPDF adapter behind ``PdfParserPort`` (Milestone 26.1),
against real PDFs built in memory.

These are the tests that decide whether the canonical representation can
be trusted: every downstream milestone reads what this adapter produced,
so "the same bytes always yield the same representation" is not a nicety
here, it is the contract.
"""

from __future__ import annotations

from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailureCode,
)
from app.domain.canonical_pdf.canonical_pdf_models import CanonicalBlockKind
from app.domain.canonical_pdf.canonical_pdf_policy import (
    CANONICAL_REPRESENTATION_VERSION,
)
from app.infrastructure.canonical_pdf.pymupdf_parser import PyMuPdfParser
from tests._pdf_builder import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    build_pdf,
    corrupted_pdf,
    empty_page_only_pdf,
    encrypted_pdf,
    multi_page_pdf,
    pdf_with_empty_page,
    pdf_with_image,
    single_page_pdf,
)

CHECKSUM = "b" * 64


def _parse(content: bytes, *, document_id: int = 7):
    return PyMuPdfParser().parse(
        content,
        document_id=document_id,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )


# --- Simple parsing -----------------------------------------------------


def test_a_simple_pdf_parses_into_a_representation() -> None:
    result = _parse(single_page_pdf("Rated voltage 145 kV"))

    assert result.parsed
    assert result.failure is None
    assert result.document.page_count == 1
    assert "Rated voltage 145 kV" in result.document.pages[0].text


def test_the_representation_records_its_provenance() -> None:
    """Which bytes, which parser, which contract - the first questions
    anyone asks when a downstream extraction looks wrong."""

    document = _parse(single_page_pdf()).document

    assert document.document_id == 7
    assert document.content_checksum == CHECKSUM
    assert document.checksum_algorithm == "sha256"
    assert document.parser_name == "pymupdf"
    assert document.parser_version
    assert (
        document.representation_version == CANONICAL_REPRESENTATION_VERSION
    )


def test_multiple_pages_are_preserved_in_order() -> None:
    document = _parse(
        multi_page_pdf("Bay 21 layout", "Bay 22 layout", "Cable schedule")
    ).document

    assert document.page_count == 3
    assert [page.page_number for page in document.pages] == [1, 2, 3]
    assert "Bay 22" in document.pages[1].text
    assert "Cable schedule" in document.pages[2].text


def test_an_empty_page_is_represented_rather_than_dropped() -> None:
    """Dropping it would renumber every page after it, and a document's
    own page references would stop matching the representation."""

    document = _parse(pdf_with_empty_page()).document

    assert document.page_count == 2
    assert document.pages[0].is_empty is False
    assert document.pages[1].is_empty is True
    assert document.pages[1].page_number == 2


def test_page_dimensions_are_preserved() -> None:
    document = _parse(single_page_pdf()).document

    assert document.pages[0].width == PAGE_WIDTH
    assert document.pages[0].height == PAGE_HEIGHT


# --- What is preserved --------------------------------------------------


def test_bounding_boxes_are_preserved_for_blocks_and_spans() -> None:
    document = _parse(
        single_page_pdf("145 kV", position=(72.0, 100.0))
    ).document
    block = document.pages[0].blocks[0]
    span = block.spans[0]

    assert span.bounding_box.x0 == 72.0
    assert span.bounding_box.width > 0
    assert span.bounding_box.height > 0
    # The block encloses its span - a geometric fact both came from the
    # same parser, asserted so a mapping slip between the two is caught.
    assert block.bounding_box.x0 <= span.bounding_box.x0
    assert block.bounding_box.y1 >= span.bounding_box.y1


def test_font_family_and_size_are_preserved() -> None:
    document = _parse(single_page_pdf("145 kV", font_size=17.0)).document
    style = document.pages[0].blocks[0].spans[0].style

    assert style.font_size == 17.0
    assert style.font_family


def test_text_style_flags_are_read_from_the_parser() -> None:
    """Read from the parser's own font flags, not sniffed from the font
    name. The default font here is neither bold nor italic, and the
    representation says so rather than leaving it unknown."""

    document = _parse(single_page_pdf()).document
    style = document.pages[0].blocks[0].spans[0].style

    assert style.bold is False
    assert style.italic is False


def test_spans_record_the_line_they_belonged_to() -> None:
    """Without it, a later reader could not tell whether two spans sat on
    the same line without re-deriving it from coordinates - which is
    inference."""

    document = _parse(
        build_pdf(
            [
                [
                    ("Rated voltage", (72.0, 100.0), 11.0),
                    ("145 kV", (72.0, 140.0), 11.0),
                ]
            ]
        )
    ).document
    lines = {
        span.line_index
        for block in document.pages[0].blocks
        for span in block.spans
    }

    assert len(lines) >= 1
    assert min(lines) == 0


def test_an_image_block_is_recorded_alongside_the_text() -> None:
    document = _parse(pdf_with_image()).document
    kinds = [block.kind for block in document.pages[0].blocks]

    assert CanonicalBlockKind.IMAGE in kinds
    assert CanonicalBlockKind.TEXT in kinds


def test_the_image_block_carries_no_text() -> None:
    """Reading it would be OCR, which this milestone does not perform."""

    document = _parse(pdf_with_image()).document
    images = [
        block
        for block in document.pages[0].blocks
        if block.kind is CanonicalBlockKind.IMAGE
    ]

    assert all(block.spans == () for block in images)


# --- What is not done ---------------------------------------------------


def test_text_is_recorded_verbatim_without_normalisation() -> None:
    """Whitespace an engineer would call noise is still what the document
    contains. Stripping it is an interpretation."""

    document = _parse(single_page_pdf("  145   kV  ")).document
    text = document.pages[0].text

    assert "  145   kV" in text


def test_blocks_keep_the_parsers_own_order_rather_than_a_sorted_one(
) -> None:
    """No geometric re-ordering. Reading order is recorded as the parser
    produced it, and is contiguous from zero on every page."""

    document = _parse(
        build_pdf(
            [
                [
                    ("Lower text", (72.0, 700.0), 11.0),
                    ("Upper text", (72.0, 100.0), 11.0),
                ]
            ]
        )
    ).document
    orders = [block.reading_order for block in document.pages[0].blocks]

    assert orders == list(range(len(orders)))


def test_adjacent_spans_are_not_merged() -> None:
    """Merging would be the parser's judgement replaced by ours."""

    document = _parse(
        build_pdf(
            [
                [
                    ("Rated voltage", (72.0, 100.0), 11.0),
                    ("145 kV", (72.0, 130.0), 11.0),
                ]
            ]
        )
    ).document
    spans = [
        span for block in document.pages[0].blocks for span in block.spans
    ]

    assert len(spans) >= 2


# --- Determinism --------------------------------------------------------


def test_parsing_the_same_bytes_twice_yields_an_equal_representation(
) -> None:
    content = multi_page_pdf("Bay 21", "Bay 22")

    assert _parse(content).document == _parse(content).document


def test_two_parser_instances_agree() -> None:
    """Determinism is a property of the bytes, not of a warmed-up
    object."""

    content = single_page_pdf()

    first = PyMuPdfParser().parse(
        content,
        document_id=7,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )
    second = PyMuPdfParser().parse(
        content,
        document_id=7,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )

    assert first.document == second.document


def test_different_documents_produce_different_representations() -> None:
    assert (
        _parse(single_page_pdf("145 kV")).document
        != _parse(single_page_pdf("400 kV")).document
    )


# --- Typed failures -----------------------------------------------------


def test_an_encrypted_pdf_is_reported_as_encrypted() -> None:
    """Distinct from corrupted: the bytes are intact and someone with the
    password could read them. There is no password to try, and this
    system must not guess one."""

    result = _parse(encrypted_pdf())

    assert result.parsed is False
    assert result.document is None
    assert result.failure.code is (
        CanonicalizationFailureCode.ENCRYPTED_DOCUMENT
    )


def test_a_corrupted_pdf_is_reported_as_corrupted() -> None:
    result = _parse(corrupted_pdf())

    assert result.failure.code is (
        CanonicalizationFailureCode.CORRUPTED_DOCUMENT
    )


def test_bytes_that_are_not_a_pdf_are_reported_as_corrupted() -> None:
    """A file the format said was a PDF and is not. Not "unsupported
    format" - that is a statement about the document record, this is a
    statement about the bytes."""

    result = _parse(b"This is a plain text file, not a PDF at all.")

    assert result.failure.code is (
        CanonicalizationFailureCode.CORRUPTED_DOCUMENT
    )


def test_empty_bytes_are_reported_as_empty_content() -> None:
    result = _parse(b"")

    assert result.failure.code is (
        CanonicalizationFailureCode.EMPTY_CONTENT
    )


def test_the_parser_never_raises_on_bad_input() -> None:
    """Every failure is a returned value. A caller should never have to
    catch whatever the library chose to throw this release."""

    for content in (b"", b"garbage", corrupted_pdf(), encrypted_pdf()):
        result = _parse(content)

        assert result.parsed is False
        assert result.failure is not None


def test_a_page_with_no_text_still_parses_successfully() -> None:
    """The parser reports what it saw - an empty page. Whether that is
    worth persisting is the service's decision, not the parser's."""

    result = _parse(empty_page_only_pdf())

    assert result.parsed is True
    assert result.document.page_count == 1
    assert result.document.has_text is False
