"""
Tests for the canonical text assembler (Milestone 26.2).

Pure domain tests. The assembly policy is what a downstream consumer
actually reads, so these pin it precisely - including the parts that
exist to *prevent* something, like the rule that original text is used
and never the normalised form.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_assembler import (
    PAGE_MARKER_TEMPLATE,
    assemble_document_text,
)
from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from tests.domain._canonical_text_support import (
    image_block,
    page,
    representation,
    simple_representation,
    span,
    text_block,
)


def _assembled(source) -> str:
    return assemble_document_text(segment_canonical_document(source))


# --- The policy ------------------------------------------------------------


def test_a_single_page_renders_its_marker_and_text() -> None:
    text = _assembled(simple_representation("Rated voltage 145 kV"))

    assert text == "--- PAGINA 1 ---\nRated voltage 145 kV"


def test_the_page_marker_format_is_pinned() -> None:
    """Kept verbatim from the pre-26.2 extractor. This string is part of
    what a downstream consumer reads, so changing its wording changes
    that consumer's input."""

    assert PAGE_MARKER_TEMPLATE == "--- PAGINA {page_number} ---"


def test_pages_are_separated_and_numbered() -> None:
    text = _assembled(
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21"))),
            page(2, text_block(0, span(0, 0, "Bay 22"))),
        )
    )

    assert text == (
        "--- PAGINA 1 ---\nBay 21\n\n--- PAGINA 2 ---\nBay 22"
    )


def test_lines_within_a_paragraph_are_separated_by_a_newline() -> None:
    text = _assembled(
        representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 0, "Rated voltage"),
                    span(1, 1, "145 kV"),
                ),
            )
        )
    )

    assert text == "--- PAGINA 1 ---\nRated voltage\n145 kV"


def test_paragraphs_are_separated_by_a_blank_line() -> None:
    """The block boundary is something the parser observed, so the
    assembler shows it."""

    text = _assembled(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "Rated voltage")),
                text_block(1, span(0, 0, "145 kV")),
            )
        )
    )

    assert text == "--- PAGINA 1 ---\nRated voltage\n\n145 kV"


def test_a_page_with_no_text_is_omitted_and_numbering_keeps_its_gap(
) -> None:
    """The gap is honest: it says page 2 carried nothing this system
    could read. A renumbered marker would quietly claim page 2 was
    something it is not."""

    text = _assembled(
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21"))),
            page(2),
            page(3, text_block(0, span(0, 0, "Bay 23"))),
        )
    )

    assert text == (
        "--- PAGINA 1 ---\nBay 21\n\n--- PAGINA 3 ---\nBay 23"
    )


def test_an_image_block_contributes_nothing() -> None:
    """It carries no text, and the assembler has no way to read an
    image - that would be OCR."""

    text = _assembled(
        representation(
            page(1, text_block(0, span(0, 0, "Site photograph")), image_block(1))
        )
    )

    assert text == "--- PAGINA 1 ---\nSite photograph"


def test_an_empty_segmentation_renders_to_an_empty_string() -> None:
    assert _assembled(representation()) == ""


# --- Ordering ---------------------------------------------------------------


def test_ordering_follows_the_segmentation_exactly() -> None:
    """Pages, then paragraphs, then lines - each in the order the
    segmentation fixed, which is the order the parser produced. Nothing
    is re-ordered geometrically."""

    text = _assembled(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "first")),
                text_block(1, span(0, 0, "second")),
            ),
            page(2, text_block(0, span(0, 0, "third"))),
        )
    )

    assert text.index("first") < text.index("second") < text.index("third")


def test_assembly_is_deterministic() -> None:
    source = representation(
        page(
            1,
            text_block(0, span(0, 0, "Rated voltage"), span(1, 1, "145 kV")),
            image_block(1),
        ),
        page(2, text_block(0, span(0, 0, "Frequency 50 Hz"))),
    )

    assert _assembled(source) == _assembled(source)


# --- Engineering symbols survive ---------------------------------------------


def test_superscripts_reach_the_consumer_unchanged() -> None:
    """The whole reason the assembler uses original text. ``mm²``
    normalises to ``mm2`` for comparison purposes, and a consumer reading
    the normalised form would silently lose the distinction."""

    text = _assembled(simple_representation("Cavo 240 mm²"))

    assert "240 mm²" in text
    assert "mm2" not in text


def test_cubic_and_other_superscripts_survive() -> None:
    text = _assembled(simple_representation("Volume 3 m³ olio"))

    assert "m³" in text
    assert "m3" not in text


def test_greek_symbols_survive() -> None:
    text = _assembled(
        simple_representation("Impedenza 0,5 Ω per fase, Δ-Y, cos φ 0,9")
    )

    assert "Ω" in text
    assert "Δ" in text
    assert "φ" in text


def test_electrical_and_mathematical_symbols_survive() -> None:
    text = _assembled(
        simple_representation("Temperatura ±5 °C, tolleranza ≤ 2 %, 3×400 V")
    )

    for symbol in ("±", "°", "≤", "×", "%"):
        assert symbol in text


def test_subscripts_survive() -> None:
    text = _assembled(simple_representation("Corrente I₁ nominale"))

    assert "I₁" in text
    assert "I1" not in text


def test_case_is_preserved() -> None:
    """``kV`` and ``KV`` are different things, and so are ``mV`` and
    ``MV``."""

    text = _assembled(simple_representation("145 kV / 20 kV, 400 mV, MV"))

    assert "kV" in text
    assert "mV" in text
    assert "MV" in text


def test_designations_reach_the_consumer_verbatim() -> None:
    text = _assembled(
        simple_representation("+E01-QA1 152 AT-TR TRASFORMATORE AT/MT")
    )

    assert "+E01-QA1" in text
    assert "152 AT-TR" in text
    assert "TRASFORMATORE AT/MT" in text


# --- Nothing is inferred ------------------------------------------------------


def test_abbreviations_are_not_expanded() -> None:
    text = _assembled(simple_representation("CB 1 e DS 2 in cabina"))

    assert "CB 1" in text
    assert "circuit breaker" not in text.lower()


def test_spelling_is_not_corrected() -> None:
    text = _assembled(simple_representation("Sezionatoer 189 SS"))

    assert "Sezionatoer" in text


def test_no_heading_or_table_structure_is_introduced() -> None:
    """The assembler emits page markers, newlines and the document's own
    words. Nothing else - no bullets, no pipes, no headings."""

    text = _assembled(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "DATI TECNICI")),
                text_block(0 + 1, span(0, 0, "Tensione 145 kV")),
            )
        )
    )

    assert text == (
        "--- PAGINA 1 ---\nDATI TECNICI\n\nTensione 145 kV"
    )
    for marker in ("#", "|", "*", "- ", "<"):
        assert marker not in text.replace("--- PAGINA 1 ---", "")


def test_the_assembler_never_uses_the_normalized_form() -> None:
    """Proved on a token whose two forms differ: the ligature is what the
    document contains, and the consumer gets it."""

    segmentation = segment_canonical_document(
        simple_representation("ﬁeld test")
    )
    token = list(segmentation.tokens())[0]

    assert token.text == "ﬁeld"
    assert token.normalized_text == "field"
    assert "ﬁeld" in assemble_document_text(segmentation)
