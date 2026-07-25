"""
Controlled, deterministic lexical normalization and matching
primitives (Milestone 13). Deliberately minimal: case-insensitive exact
token matching, separator-normalized identifier matching, and prefix
matching on a small, explicit set of fields - no embeddings, no
fuzzy/edit-distance matching, no stemming library, no external search
engine, no synonym or ontology inference. Bump
``LEXICAL_NORMALIZATION_VERSION`` whenever a normalization rule changes,
so ``RetrievalExecutionMetadata`` can record which rules produced a
given result.
"""

from __future__ import annotations

import re

LEXICAL_NORMALIZATION_VERSION = "1.0"

_IDENTIFIER_STRIP_PATTERN = re.compile(r"[^a-z0-9]")
_TOKEN_SPLIT_PATTERN = re.compile(r"[\s,;/]+")


def normalize_token(text: str) -> str:
    """Case-insensitive, whitespace-trimmed normalization for exact
    token comparison."""

    return text.strip().lower()


def normalize_identifier(text: str) -> str:
    """
    Normalizes an identifier-like string for comparison across common
    separator variance - ``"C-295"``, ``"c 295"``, and ``"C295"`` all
    normalize identically - by lowercasing and stripping every
    non-alphanumeric character.
    """

    return _IDENTIFIER_STRIP_PATTERN.sub("", text.lower())


def tokenize(text: str) -> tuple[str, ...]:
    """Splits free text into normalized tokens on whitespace and common
    separators (comma, semicolon, slash) - no stemming, no NLP."""

    return tuple(
        normalize_token(token)
        for token in _TOKEN_SPLIT_PATTERN.split(text)
        if token.strip()
    )


def matches_prefix(term: str, field_value: str) -> bool:
    """
    Deterministic, explicitly-scoped prefix matching: the normalized
    field value starts with the normalized term. Applied only to
    canonical identifiers and relationship types (see
    ``candidate_matching.py``) - never to free-form attribute values,
    where a prefix match would be too noisy to explain.
    """

    return normalize_token(field_value).startswith(normalize_token(term))
