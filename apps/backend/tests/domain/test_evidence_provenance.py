"""
Tests for evidence provenance and symbol preservation (Milestone 28.1).

Two questions decide whether this layer is trustworthy:

1. can a caller recover **exactly** which characters produced an
   observation, without searching for text; and
2. do engineering symbols survive the whole pipeline into the evidence?

Everything here is about one of those two.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_evidence.evidence_validation import (
    validate_evidence_set,
)
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)


def _from_spans(*span_texts: str, line_indices: tuple[int, ...] | None = None):
    """Canonical text whose spans are exactly ``span_texts``, all on one
    line unless ``line_indices`` says otherwise."""

    indices = line_indices or tuple(0 for _ in span_texts)
    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(order, indices[order], text)
                    for order, text in enumerate(span_texts)
                ],
            ),
        )
    )
    segmentation = segment_canonical_document(source)

    return segmentation, extract_evidence(segmentation)


def _recover(item, span_texts: tuple[str, ...]) -> str:
    """Re-read the observation from the source, using only its
    provenance - which is what an auditor would do."""

    return " ".join(
        span_texts[reference.span_reading_order][
            reference.character_start : reference.character_end
        ]
        for reference in item.provenance.spans
    )


# --- The chain is exact -------------------------------------------------------


def test_character_offsets_recover_the_observed_text() -> None:
    texts = ("Tensione nominale 20 kV in ingresso",)
    _, result = _from_spans(*texts)
    item = result.of_type(EvidenceType.VOLTAGE_VALUE)[0]

    assert _recover(item, texts) == "20 kV"
    assert item.observed_text == "20 kV"


def test_offsets_exclude_the_punctuation_that_was_trimmed() -> None:
    """``400 V,`` yields evidence whose range covers ``400 V`` and not
    the comma. Trimming without narrowing the range would be a small,
    permanent lie about where the observation came from."""

    texts = ("Tensione 400 V, corrente 1250 A.",)
    _, result = _from_spans(*texts)

    for item in result.evidence:
        assert _recover(item, texts) == item.observed_text


def test_every_observation_recovers_from_its_provenance() -> None:
    texts = ("Trasformatore (T1), 20 kV / 400 V, 630 kVA e 240 mm²",)
    _, result = _from_spans(*texts)

    assert result.evidence_count == 5
    for item in result.evidence:
        assert _recover(item, texts) == item.observed_text


def test_provenance_records_page_paragraph_line_and_tokens() -> None:
    source = representation(
        page(1, text_block(0, span(0, 0, "Cover"))),
        page(
            2,
            text_block(0, span(0, 0, "Bay 21")),
            text_block(1, span(0, 0, "Ignored"), span(1, 3, "Tensione 20 kV")),
        ),
    )
    result = extract_evidence(segment_canonical_document(source))
    item = result.of_type(EvidenceType.VOLTAGE_VALUE)[0]

    assert item.provenance.page_number == 2
    assert item.provenance.section_index == 1
    assert item.provenance.paragraph_index == 1
    assert item.provenance.block_reading_order == 1
    assert item.provenance.line_index == 3
    assert item.provenance.token_start == 1
    assert item.provenance.token_end == 3


# --- Span boundaries ------------------------------------------------------------


def test_an_observation_within_one_span_cites_one_span() -> None:
    _, result = _from_spans("Tensione 20 kV")
    item = result.of_type(EvidenceType.VOLTAGE_VALUE)[0]

    assert len(item.provenance.spans) == 1
    assert item.provenance.crosses_spans is False


def test_an_observation_across_two_spans_cites_both() -> None:
    """
    "20" and "kV" in different styles is one quantity drawn from two
    spans. Both references are recorded, because a single range across
    two spans would describe characters that exist in neither.
    """

    texts = ("Tensione 20", "kV nominale")
    _, result = _from_spans(*texts)
    item = result.of_type(EvidenceType.VOLTAGE_VALUE)[0]

    assert item.provenance.crosses_spans is True
    assert len(item.provenance.spans) == 2
    assert _recover(item, texts) == "20 kV"


def test_an_observation_never_crosses_a_line() -> None:
    """A rule sees one line at a time, so a quantity whose number and
    unit are on different lines is simply not observed - rather than
    recorded with a location that spans two places."""

    _, result = _from_spans("Tensione 20", "kV", line_indices=(0, 1))

    assert result.of_type(EvidenceType.VOLTAGE_VALUE) == ()


def test_an_observation_never_crosses_a_paragraph() -> None:
    source = representation(
        page(
            1,
            text_block(0, span(0, 0, "Tensione 20")),
            text_block(1, span(0, 0, "kV nominale")),
        )
    )
    result = extract_evidence(segment_canonical_document(source))

    assert result.of_type(EvidenceType.VOLTAGE_VALUE) == ()


def test_a_valid_set_passes_validation() -> None:
    segmentation, result = _from_spans(
        "Trasformatore T1 20 kV 630 kVA 240 mm²"
    )

    assert validate_evidence_set(result, segmentation) is None


# --- Engineering symbols survive -------------------------------------------------


def test_the_superscript_section_is_preserved_in_the_observed_text() -> None:
    """
    The regression this milestone most needs.

    Canonical text stores ``mm²`` as the original and ``mm2`` as its NFKC
    normalisation. The extractor reads the **original**, so the evidence
    records what the document wrote.
    """

    texts = ("Cavo 240 mm² tripolare",)
    _, result = _from_spans(*texts)
    item = result.of_type(EvidenceType.CABLE_SECTION_VALUE)[0]

    assert item.observed_text == "240 mm²"
    assert "mm2" not in item.observed_text
    assert _recover(item, texts) == "240 mm²"


def test_the_ascii_section_spelling_is_also_preserved_as_written() -> None:
    """Both spellings map to the canonical unit ``mm²`` - declared in the
    catalogue, not inferred - and each evidence item still records the
    form its document used, so the two remain distinguishable."""

    _, superscript = _from_spans("Cavo 240 mm²")
    _, ascii_form = _from_spans("Cavo 240 mm2")

    first = superscript.of_type(EvidenceType.CABLE_SECTION_VALUE)[0]
    second = ascii_form.of_type(EvidenceType.CABLE_SECTION_VALUE)[0]

    assert first.observed_text == "240 mm²"
    assert second.observed_text == "240 mm2"
    assert first.quantity.unit == second.quantity.unit == "mm²"
    assert first.quantity.value == second.quantity.value == Decimal("240")


def test_engineering_symbols_survive_into_the_evidence() -> None:
    """Every symbol the milestone brief names, checked against the
    canonical text the extractor reads."""

    symbols = ("mm²", "m³", "Ω", "Δ", "φ", "±", "°", "≤", "×", "I₁")
    line = "Dati: " + " ".join(symbols)
    segmentation, _ = _from_spans(line)
    originals = [token.text for token in segmentation.tokens()]

    for symbol in symbols:
        assert symbol in originals


def test_the_extractor_reads_original_text_not_the_normalized_form(
) -> None:
    """``I₁`` normalises to ``I1``, which matches the designation pattern.
    The extractor reads the original, so a subscripted signal name is not
    silently promoted to a designation."""

    segmentation, result = _from_spans("Corrente I₁ nominale")
    token = list(segmentation.tokens())[1]

    assert token.text == "I₁"
    assert token.normalized_text == "I1"
    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_greek_and_mathematical_symbols_are_not_mistaken_for_units(
) -> None:
    """``Ω`` is not in the unit catalogue, so ``5 Ω`` is not a quantity.
    Not guessing is the correct behaviour - an undeclared unit is not a
    unit, and impedance is not a supported evidence type."""

    _, result = _from_spans("Impedenza 5 Ω e sfasamento 30 °")

    assert result.evidence_count == 0
