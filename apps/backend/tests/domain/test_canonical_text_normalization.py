"""
Tests for deterministic token normalisation (Milestone 27.1).

The normaliser is one pure function, and these tests are mostly about
what it refuses to do. Every forbidden transformation here is one that
would look helpful in isolation and would quietly destroy evidence at
scale.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_normalization import (
    UNICODE_NORMALIZATION_FORM,
    normalize_token_text,
)


# --- What it does ---------------------------------------------------------


def test_ordinary_text_is_unchanged() -> None:
    assert normalize_token_text("Interruttore") == "Interruttore"


def test_surrounding_whitespace_is_stripped() -> None:
    assert normalize_token_text(" 145 ") == "145"


def test_compatibility_forms_are_folded() -> None:
    """PDFs are full of ligatures and presentation variants that look
    identical to a reader and compare unequal to a machine. Folding them
    is exactly what a future extractor needs."""

    assert normalize_token_text("ﬁeld") == "field"
    assert normalize_token_text("ＫＶ") == "KV"


def test_normalization_is_deterministic() -> None:
    for text in ("145 kV", "Sezionatore", "ﬁeld", "mm²"):
        assert normalize_token_text(text) == normalize_token_text(text)


def test_whitespace_only_text_normalizes_to_empty() -> None:
    """Total rather than raising. What to do about an empty token is the
    segmenter's business, not the normaliser's."""

    assert normalize_token_text("     ") == ""


def test_the_normalization_form_is_recorded() -> None:
    """Named rather than inlined, so a stored segmentation's version can
    be traced to the rule that produced it."""

    assert UNICODE_NORMALIZATION_FORM == "NFKC"


# --- What it refuses to do -------------------------------------------------


def test_case_is_preserved() -> None:
    """``mV``, ``kV`` and ``MV`` are three different things. A matcher
    that wants case-insensitivity can fold at match time, with the
    information still intact."""

    assert normalize_token_text("kV") == "kV"
    assert normalize_token_text("MV") == "MV"
    assert normalize_token_text("kV") != normalize_token_text("KV")


def test_abbreviations_are_not_expanded() -> None:
    """``CB`` becoming ``circuit breaker`` is an ontology lookup wearing
    a normaliser's clothes."""

    assert normalize_token_text("CB") == "CB"
    assert normalize_token_text("CT") == "CT"


def test_spelling_is_not_corrected() -> None:
    """A misspelling in a technical document is evidence about the
    document."""

    assert normalize_token_text("Sezionatoer") == "Sezionatoer"


def test_quantities_are_not_reinterpreted() -> None:
    """No splitting of value from unit, no decimal-separator conversion,
    no conversion of any kind. Units and quantities are the electrical
    ontology's business."""

    assert normalize_token_text("145kV") == "145kV"
    assert normalize_token_text("0,4") == "0,4"
    assert normalize_token_text("1.250") == "1.250"


def test_punctuation_is_preserved() -> None:
    """A trailing colon or a hyphen may be part of a designation. Trimming
    it would be a tokenisation policy, decided here by accident."""

    assert normalize_token_text("Q0:") == "Q0:"
    assert normalize_token_text("-QA1") == "-QA1"


def test_internal_structure_is_never_rewritten() -> None:
    assert normalize_token_text("+E01-QA1") == "+E01-QA1"


def test_the_known_cost_of_nfkc_is_pinned() -> None:
    """
    NFKC folds superscripts, so a cable cross-section written ``mm²``
    normalises to ``mm2``. This is a real loss of a distinction an
    electrical engineer cares about, and it is asserted here rather than
    left to be discovered: the token's ``text`` keeps the original
    verbatim and its provenance points at the exact characters, so
    nothing is destroyed - but anyone changing this rule should have to
    change this test deliberately.
    """

    assert normalize_token_text("mm²") == "mm2"
