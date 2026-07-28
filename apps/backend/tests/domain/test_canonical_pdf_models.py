"""
Tests for the canonical PDF value objects and their factory
(Milestone 26.1).

Pure domain tests: no PDF, no parser, no database. They specify the shape
of the representation and the invariants that make it trustworthy - a
representation with a hole in its page sequence or its reading order is
refused at construction, because one that reached storage would be
believed by every future extractor.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.domain.canonical_pdf import canonical_pdf_factory as factory
from app.domain.canonical_pdf.canonical_pdf_exceptions import (
    InvalidCanonicalRepresentationError,
)
from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalBlockKind,
    CanonicalPdfDocument,
    CanonicalPdfPage,
)

BOX = (0.0, 0.0, 10.0, 10.0)


def _span(reading_order: int = 0, text: str = "145 kV", line: int = 0):
    return factory.build_span(
        reading_order=reading_order,
        line_index=line,
        text=text,
        bounding_box=factory.build_bounding_box(*BOX),
        font_family="Helvetica",
        font_size=11.0,
        bold=False,
        italic=False,
    )


def _block(reading_order: int = 0, spans=None):
    return factory.build_block(
        reading_order=reading_order,
        kind=CanonicalBlockKind.TEXT,
        bounding_box=factory.build_bounding_box(*BOX),
        spans=spans if spans is not None else (_span(),),
    )


def _page(page_number: int = 1, blocks=None):
    return factory.build_page(
        page_number=page_number,
        width=595.0,
        height=842.0,
        blocks=blocks if blocks is not None else (_block(),),
    )


def _document(pages=None, **overrides):
    defaults = dict(
        document_id=7,
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        representation_version="1.0",
        parser_name="pymupdf",
        parser_version="1.28.0",
        pages=pages if pages is not None else (_page(),),
    )
    defaults.update(overrides)

    return factory.build_document(**defaults)


# --- The hierarchy ------------------------------------------------------


def test_a_document_reports_its_page_count() -> None:
    document = _document(pages=(_page(1), _page(2), _page(3)))

    assert document.page_count == 3


def test_a_page_with_no_blocks_is_empty_and_still_valid() -> None:
    """A blank page in a drawing set is a fact about the document, not an
    error."""

    page = _page(blocks=())

    assert page.is_empty
    assert page.text == ""


def test_block_text_concatenates_its_spans_verbatim() -> None:
    """Verbatim: not joined with spaces, not stripped, not normalised.
    Inserting a separator would be inventing characters the document does
    not contain."""

    block = _block(
        spans=(
            _span(0, "Rated "),
            _span(1, "voltage"),
        )
    )

    assert block.text == "Rated voltage"


def test_a_document_reports_whether_any_text_was_found() -> None:
    with_text = _document()
    without_text = _document(pages=(_page(blocks=()),))

    assert with_text.has_text is True
    assert without_text.has_text is False


def test_spans_of_empty_text_do_not_count_as_text() -> None:
    document = _document(pages=(_page(blocks=(_block(spans=(_span(0, ""),)),)),))

    assert document.has_text is False


def test_an_image_block_carries_no_spans_and_is_still_recorded() -> None:
    """Recorded rather than dropped: "there was a figure here" is
    something the parser observed, and omitting it would misrepresent the
    page as sparser than it is."""

    block = factory.build_block(
        reading_order=0,
        kind=CanonicalBlockKind.IMAGE,
        bounding_box=factory.build_bounding_box(*BOX),
    )

    assert block.kind is CanonicalBlockKind.IMAGE
    assert block.spans == ()


def test_a_bounding_box_reports_its_own_dimensions() -> None:
    box = factory.build_bounding_box(10.0, 20.0, 40.0, 60.0)

    assert box.width == 30.0
    assert box.height == 40.0


# --- Immutability -------------------------------------------------------


def test_every_level_of_the_representation_is_frozen() -> None:
    """A representation cannot be edited after the fact - only rebuilt
    from bytes, which is the only thing that could legitimately change
    it."""

    document = _document()

    with pytest.raises(dataclasses.FrozenInstanceError):
        document.pages[0].blocks[0].spans[0].text = "tampered"

    with pytest.raises(dataclasses.FrozenInstanceError):
        document.document_id = 99


def test_two_representations_of_the_same_content_compare_equal() -> None:
    """Value equality is what makes determinism assertable at all."""

    assert _document() == _document()


def test_the_representation_carries_no_timestamp() -> None:
    """When it was built is a fact about the row, not about the
    representation - and a timestamp would break the value equality two
    runs over identical bytes must have."""

    field_names = {
        field.name for field in dataclasses.fields(CanonicalPdfDocument)
    }

    assert "created_at" not in field_names
    assert field_names == {
        "document_id",
        "content_checksum",
        "checksum_algorithm",
        "representation_version",
        "parser_name",
        "parser_version",
        "pages",
    }


def test_the_model_has_nowhere_to_record_an_interpretation() -> None:
    """No section, no table, no heading, no entity. The moment one of
    these appears, the line between observing and interpreting is gone."""

    forbidden = {
        "section",
        "sections",
        "table",
        "tables",
        "heading",
        "headings",
        "paragraph",
        "paragraphs",
        "entity",
        "entities",
        "list_items",
        "summary",
    }

    for model in (CanonicalPdfDocument, CanonicalPdfPage):
        names = {field.name for field in dataclasses.fields(model)}

        assert names & forbidden == set()


# --- Invariants ---------------------------------------------------------


def test_pages_must_be_a_contiguous_one_based_sequence() -> None:
    """A representation missing page 4 would be indistinguishable from a
    document that never had one, and every page reference after it would
    be wrong."""

    with pytest.raises(InvalidCanonicalRepresentationError):
        _document(pages=(_page(1), _page(2), _page(4)))


def test_pages_must_start_at_one() -> None:
    with pytest.raises(InvalidCanonicalRepresentationError):
        _document(pages=(_page(2),))


def test_a_page_number_below_one_is_refused() -> None:
    with pytest.raises(InvalidCanonicalRepresentationError):
        _page(page_number=0)


def test_block_reading_order_must_have_no_holes() -> None:
    """A gap means something was dropped on the way in, and a
    representation that quietly lost content is worse than one that
    failed loudly."""

    with pytest.raises(InvalidCanonicalRepresentationError):
        _page(blocks=(_block(0), _block(2)))


def test_span_reading_order_must_have_no_holes() -> None:
    with pytest.raises(InvalidCanonicalRepresentationError):
        _block(spans=(_span(0), _span(2)))


def test_a_reversed_bounding_box_is_refused_not_straightened() -> None:
    """Swapping the corners would hide a parser fault and produce a box
    that was never observed."""

    with pytest.raises(InvalidCanonicalRepresentationError):
        factory.build_bounding_box(100.0, 0.0, 10.0, 10.0)


def test_a_negative_font_size_is_refused() -> None:
    with pytest.raises(InvalidCanonicalRepresentationError):
        factory.build_span(
            reading_order=0,
            line_index=0,
            text="x",
            bounding_box=factory.build_bounding_box(*BOX),
            font_family="Helvetica",
            font_size=-1.0,
            bold=False,
            italic=False,
        )


def test_an_image_block_carrying_text_spans_is_refused() -> None:
    with pytest.raises(InvalidCanonicalRepresentationError):
        factory.build_block(
            reading_order=0,
            kind=CanonicalBlockKind.IMAGE,
            bounding_box=factory.build_bounding_box(*BOX),
            spans=(_span(),),
        )


def test_a_representation_without_a_checksum_is_refused() -> None:
    """Without it, nothing ties the representation to a document
    version, and "which bytes did this come from?" becomes
    unanswerable."""

    with pytest.raises(InvalidCanonicalRepresentationError):
        _document(content_checksum="   ")


def test_a_document_with_no_pages_is_constructible_and_reports_empty(
) -> None:
    """The factory permits it; the service refuses to persist it. Two
    different responsibilities: the model describes what the parser saw,
    the service decides what is worth storing."""

    document = _document(pages=())

    assert document.is_empty
    assert document.page_count == 0
