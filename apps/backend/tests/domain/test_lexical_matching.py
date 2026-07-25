from __future__ import annotations

from app.domain.structured_retrieval.lexical_matching import (
    matches_prefix,
    normalize_identifier,
    normalize_token,
    tokenize,
)


def test_normalize_token_lowercases_and_strips():
    assert normalize_token("  Cable  ") == "cable"


def test_normalize_identifier_strips_separators_and_case():
    assert normalize_identifier("C-295") == "c295"
    assert normalize_identifier("c 295") == "c295"
    assert normalize_identifier("C295") == "c295"


def test_normalize_identifier_variants_are_equal():
    assert normalize_identifier("C-295") == normalize_identifier("c295")


def test_tokenize_splits_on_whitespace_and_common_separators():
    assert tokenize("Cable, Transformer/Breaker; relay") == (
        "cable",
        "transformer",
        "breaker",
        "relay",
    )


def test_tokenize_drops_empty_fragments():
    assert tokenize("  cable   transformer ") == ("cable", "transformer")


def test_matches_prefix_is_case_insensitive():
    assert matches_prefix("cab", "CABLE")
    assert matches_prefix("CAB", "cable")


def test_matches_prefix_requires_the_field_to_start_with_the_term():
    assert not matches_prefix("295", "C-295")
    assert matches_prefix("C-2", "C-295")
