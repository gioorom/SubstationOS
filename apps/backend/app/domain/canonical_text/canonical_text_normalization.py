"""
Deterministic token normalisation (Milestone 27.1).

The **one** place a token's normalised form is decided, so two callers
can never disagree about whether two tokens are the same string.

## The rule

1. **Unicode NFKC**, then
2. **whitespace stripped** from both ends.

That is the whole rule. It is a pure function of the input string: no
dictionary, no locale, no configuration, no wall clock.

## What it deliberately does not do

- **No case folding.** ``kV`` and ``KV`` stay different, because case
  carries meaning in this domain: ``mV``, ``kV`` and ``MV`` are three
  different things, and a matcher that wants case-insensitivity can fold
  at match time with the information still intact.
- **No abbreviation expansion.** ``CB`` does not become ``circuit
  breaker``. That is an ontology lookup wearing a normaliser's clothes,
  and it belongs to a milestone that can be reviewed as such.
- **No spelling correction.** A misspelling in a technical document is
  evidence about the document.
- **No engineering normalisation.** ``145kV`` is not split into a value
  and a unit, ``0,4`` is not reinterpreted as ``0.4``, and nothing is
  converted. Units and quantities are the electrical ontology's
  business.
- **No stemming, no lemmatisation, no stop-word removal.**

## Why NFKC rather than NFC

PDFs are full of compatibility characters: ligatures (``ﬁeld``),
full-width forms, and presentation variants that look identical to a
reader but compare unequal to a machine. NFKC folds those together, which
is exactly what a future extractor needs when it compares a token to a
catalogue entry.

**The known cost, stated plainly:** NFKC also folds superscripts, so a
cable cross-section written ``mm²`` normalises to ``mm2``. That is a real
loss of a distinction an electrical engineer cares about. It is
acceptable here for one reason only - ``CanonicalTextToken.text``
preserves the original substring verbatim, and the token's provenance
points at the exact characters of the exact span - so nothing is
destroyed, and any consumer that needs the superscript reads the original
form. If a future milestone finds that trade wrong, changing it is a
bump of ``CANONICAL_SEGMENTATION_VERSION`` and a re-segmentation, which
is why that version exists.
"""

from __future__ import annotations

import unicodedata

# The Unicode normalisation form applied to every token. Recorded as a
# named constant rather than inlined, so a stored segmentation's version
# can be traced back to the rule that produced it.
UNICODE_NORMALIZATION_FORM = "NFKC"


def normalize_token_text(text: str) -> str:
    """
    The normalised form of one token's text.

    Deterministic and total: every string has a normalised form, and the
    same string always has the same one. Whitespace-only input
    normalises to the empty string rather than raising - deciding what
    to do about an empty token is the segmenter's business, not the
    normaliser's.
    """

    return unicodedata.normalize(UNICODE_NORMALIZATION_FORM, text).strip()
