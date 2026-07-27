"""
Deterministic text normalization for Engineering Request Classification
(Milestone 22). Pure, local, standard-library-only logic: Unicode NFKC
normalization, case folding, punctuation-to-whitespace substitution,
whitespace collapsing, and whitespace tokenization.

**No embeddings, no external NLP service, no LLM, no semantic
similarity model, no vector database, no provider SDK** is used here or
anywhere in this bounded context.

Tokenization is whole-token, which is what lets the rule engine avoid
false matches from words occurring inside unrelated words: matching the
token ``"apri"`` never fires on ``"aprile"``, and matching ``"vs"``
never fires on ``"vsat"`` - a naive substring search would fire on
both.
"""

from __future__ import annotations

import unicodedata

# Every character treated as a token separator. Deliberately explicit
# rather than a category-based rule, so the exact behaviour is
# reviewable and stable across Python/Unicode versions. Apostrophes and
# hyphens are included: "dell'impianto" tokenizes to ("dell",
# "impianto") and "media-tensione" to ("media", "tensione"), which is
# what makes whole-token rules match real Italian and English
# engineering phrasing.
PUNCTUATION_CHARACTERS = frozenset(
    ".,;:!?()[]{}<>\"'`|/\\@#$%^&*+=~_-–—‘’“”¿¡"
)


def normalize_text(text: str) -> str:
    """Unicode-NFKC-normalize, case-fold, replace every punctuation
    character with a space, and collapse whitespace. Deterministic and
    idempotent."""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.casefold()
    normalized = "".join(
        " " if character in PUNCTUATION_CHARACTERS else character
        for character in normalized
    )

    return " ".join(normalized.split())


def tokenize(normalized_text: str) -> tuple[str, ...]:
    """Whitespace tokenization of already-normalized text - never
    applied to raw text, so callers always normalize first."""

    return tuple(normalized_text.split())


def normalize_and_tokenize(text: str) -> tuple[str, tuple[str, ...]]:
    normalized = normalize_text(text)

    return normalized, tokenize(normalized)
