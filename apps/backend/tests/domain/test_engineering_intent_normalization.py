from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_normalization import (
    normalize_and_tokenize,
    normalize_text,
    tokenize,
)


def test_whitespace_is_trimmed_and_collapsed() -> None:
    assert normalize_text("   quale    TA   ") == "quale ta"


def test_text_is_case_folded() -> None:
    assert normalize_text("SPIEGAMI Lo Schema") == "spiegami lo schema"


def test_punctuation_becomes_a_token_separator() -> None:
    assert normalize_text("Quale TA e installato?") == "quale ta e installato"
    assert normalize_text("revisioni 01, 02.") == "revisioni 01 02"


def test_apostrophes_split_italian_elisions() -> None:
    assert tokenize(normalize_text("dell'impianto")) == ("dell", "impianto")


def test_hyphens_split_compound_terms() -> None:
    assert tokenize(normalize_text("media-tensione")) == ("media", "tensione")


def test_unicode_is_nfkc_normalized() -> None:
    # U+FF33 FULLWIDTH LATIN CAPITAL LETTER S folds to plain "s".
    assert normalize_text("Ｓchema") == "schema"


def test_accented_characters_are_preserved_after_case_folding() -> None:
    assert normalize_text("È installato") == "è installato"


def test_normalization_is_idempotent() -> None:
    once = normalize_text("  Confronta, le REVISIONI 01 e 02.  ")

    assert normalize_text(once) == once


def test_tokenize_splits_on_whitespace() -> None:
    assert tokenize("confronta le revisioni") == ("confronta", "le", "revisioni")


def test_normalize_and_tokenize_returns_both_forms() -> None:
    normalized, tokens = normalize_and_tokenize("Apri la PAGINA!")

    assert normalized == "apri la pagina"
    assert tokens == ("apri", "la", "pagina")


def test_text_with_only_punctuation_normalizes_to_empty() -> None:
    assert normalize_text("???!!!") == ""
