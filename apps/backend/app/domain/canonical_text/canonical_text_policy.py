"""
The fixed policy of canonical text segmentation (Milestone 27.1).

Small on purpose: everything here must be *recorded* alongside a stored
segmentation for it to stay explainable, not tuned.
"""

from __future__ import annotations

from app.domain.canonical_pdf.canonical_pdf_policy import (
    CANONICAL_REPRESENTATION_VERSION,
)

# The segmentation's own version. Bumped when the *rules* change - a
# different tokenisation, a different normalisation form, a different
# notion of what a paragraph is - so a stored segmentation always says
# which contract produced it, and a re-segmentation is a deliberate,
# visible event rather than a silent drift.
CANONICAL_SEGMENTATION_VERSION = "1.0"

# Representation contracts this segmenter understands. A representation
# built under a newer contract is refused rather than segmented on a
# best-effort basis: it may carry fields whose meaning this code would
# misinterpret, and a wrong structure is worse than a visible refusal.
SUPPORTED_REPRESENTATION_VERSIONS: frozenset[str] = frozenset(
    {CANONICAL_REPRESENTATION_VERSION}
)


def is_supported_representation_version(version: str) -> bool:
    return version in SUPPORTED_REPRESENTATION_VERSIONS
