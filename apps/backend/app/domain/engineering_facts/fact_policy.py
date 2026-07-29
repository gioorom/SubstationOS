"""
The fixed policy of fact construction (Milestone 29.2).

Everything here is recorded on a stored fact set so a historical
construction stays explainable, and none of it is a knob to tune per run.
"""

from __future__ import annotations

from app.domain.engineering_entities.entity_policy import (
    RESOLUTION_POLICY_VERSION,
)

# The construction policy's own version. Bumped when the *catalogue*
# changes - a rule added, a rule version raised, a predicate declared -
# so a stored fact set always says which body of rules produced it.
FACT_POLICY_VERSION = "1.0"

# The version of the fact contract itself - the shape of a fact.
# Recorded alongside the rule version because the two change for
# different reasons: the same rules can produce two fact shapes, and the
# same shape can be produced by two rule catalogues.
FACT_CONTRACT_VERSION = "1.0"

# Entity resolution policies this constructor understands. An entity set
# built under a newer policy is refused rather than associated on a
# best-effort basis: it may carry entity types this code would silently
# ignore, and a fact set missing half its subjects is worse than a
# visible refusal.
SUPPORTED_RESOLUTION_POLICY_VERSIONS: frozenset[str] = frozenset(
    {RESOLUTION_POLICY_VERSION}
)


def is_supported_resolution_policy_version(version: str) -> bool:
    return version in SUPPORTED_RESOLUTION_POLICY_VERSIONS
