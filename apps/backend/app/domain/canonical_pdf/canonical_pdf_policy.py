"""
The fixed policy of the canonical PDF representation (Milestone 26.1).

Small on purpose. Everything here is a decision that must be *recorded*
alongside a representation for it to stay explainable years later, not a
knob to tune.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import ClassifiedFormat

# The representation's own version. Bumped when the *shape* of what is
# recorded changes - a new field, a different grouping - so a stored
# representation always says which contract it was built under. It is not
# the parser's version, which is recorded separately: the same shape can
# be produced by two parser releases, and the same parser can produce two
# shapes.
CANONICAL_REPRESENTATION_VERSION = "1.0"

# Only PDF participates in this milestone. Everything else - DWG, DXF,
# spreadsheets, images - produces a typed unsupported result rather than
# a partial or a guessed representation. A drawing is not badly-formed
# text; it is a different problem, and pretending otherwise would put
# nonsense into the one artefact every future extraction trusts.
SUPPORTED_CANONICALIZATION_FORMATS: frozenset[str] = frozenset(
    {ClassifiedFormat.PDF.value}
)


def is_canonicalizable_format(document_format: str) -> bool:
    return document_format in SUPPORTED_CANONICALIZATION_FORMATS
