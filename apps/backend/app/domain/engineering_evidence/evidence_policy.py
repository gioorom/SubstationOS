"""
The fixed policy of Engineering Evidence Extraction (Milestone 28.1).

Everything here must be recorded alongside a stored evidence set for it
to stay explainable, and none of it is a knob to tune.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_policy import (
    CANONICAL_SEGMENTATION_VERSION,
)

# The extraction policy's own version. Bumped when the *catalogue*
# changes - a rule added, a rule version raised, a unit declared - so a
# stored evidence set always says which body of rules produced it, and a
# re-extraction is a deliberate, visible event rather than a silent
# reinterpretation.
#
# 2.0 (EPIC 32.E2): two rule versions raised and two designation shapes
# added. This field is the reuse key, so leaving it at 1.0 would have
# been the exact failure it exists to prevent - documents extracted
# before the change would be served forever with `+GSH002` stored as a
# DESIGNATION, while documents extracted after record it as a
# LOCATION_ASPECT, both claiming policy 1.0.
EXTRACTION_POLICY_VERSION = "2.0"

# Segmentation contracts this extractor understands. A canonical text
# built under a newer contract is refused rather than extracted on a
# best-effort basis: it may group tokens differently, and provenance
# recorded against the wrong grouping would point at the wrong
# characters - which is worse than no evidence at all.
SUPPORTED_SEGMENTATION_VERSIONS: frozenset[str] = frozenset(
    {CANONICAL_SEGMENTATION_VERSION}
)


def is_supported_segmentation_version(version: str) -> bool:
    return version in SUPPORTED_SEGMENTATION_VERSIONS
