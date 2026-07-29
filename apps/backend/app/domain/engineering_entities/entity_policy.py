"""
The fixed policy of entity resolution (Milestone 29.1).

Everything here is recorded on a stored entity set so a historical
resolution stays explainable, and none of it is a knob to tune per run.
"""

from __future__ import annotations

from app.domain.engineering_evidence.evidence_policy import (
    EXTRACTION_POLICY_VERSION,
)

# The resolution policy's own version. Bumped when the *catalogue*
# changes - a rule added, a rule version raised - so a stored entity set
# always says which body of rules produced it, and a re-resolution is a
# deliberate, visible event rather than a silent regrouping.
RESOLUTION_POLICY_VERSION = "1.0"

# The version of the entity contract itself - the shape of an entity.
# Recorded alongside the rule version because the two change for
# different reasons: the same rules can produce two entity shapes, and
# the same shape can be produced by two rule catalogues.
ENTITY_MODEL_VERSION = "1.0"

# Extraction policies this resolver understands. Evidence built under a
# newer policy is refused rather than resolved on a best-effort basis: it
# may carry evidence types or statuses this code would silently ignore,
# and an entity set missing half its evidence is worse than a visible
# refusal.
SUPPORTED_EXTRACTION_POLICY_VERSIONS: frozenset[str] = frozenset(
    {EXTRACTION_POLICY_VERSION}
)


def is_supported_extraction_policy_version(version: str) -> bool:
    return version in SUPPORTED_EXTRACTION_POLICY_VERSIONS
