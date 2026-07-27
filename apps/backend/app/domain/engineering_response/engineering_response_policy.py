"""
The fixed, documented composition policy for Engineering Response
(Milestone 18): version stamps, and the uncertainty-ranking table the
Composition and Validation stages both share. The same "fixed,
documented policy table" convention Structured Retrieval's
``scoring_policy.py``, Context Builder's ``budget_policy.py``, and
Prompt Builder's ``composition_policy.py`` all established. Bump the
relevant ``*_VERSION`` constant whenever a warning/uncertainty rule
changes, so ``EngineeringResponseMetadata``/``EngineeringResponseVersion``
can record which policy produced a given ``EngineeringResponse``.
"""

from __future__ import annotations

from app.domain.engineering_response.engineering_response_models import (
    EngineeringUncertainty,
    EngineeringUncertaintyLevel,
)

ENGINEERING_RESPONSE_VERSION = "1.0"
RESPONSE_POLICY_VERSION = "1.0"
RESPONSE_PACKAGE_VERSION = "1.0"

# Worst-wins ranking: HIGH is the most severe, LOW the least. UNKNOWN
# ranks above MEDIUM but below HIGH - "we have no basis to judge" is
# more concerning than "we judged it partially uncertain," but a
# concretely identified HIGH-severity gap is still worse than an
# unassessed one being reported alongside it.
UNCERTAINTY_RANK: dict[EngineeringUncertaintyLevel, int] = {
    EngineeringUncertaintyLevel.LOW: 0,
    EngineeringUncertaintyLevel.MEDIUM: 1,
    EngineeringUncertaintyLevel.UNKNOWN: 2,
    EngineeringUncertaintyLevel.HIGH: 3,
}


def overall_uncertainty_from(
    uncertainties: tuple[EngineeringUncertainty, ...],
) -> EngineeringUncertaintyLevel:
    """The worst (highest-ranked) level among every uncertainty
    declaration. Callers must supply at least one declaration - the
    Composition stage always produces at least one (see
    ``engineering_response_composition.py``'s ``_build_uncertainties``),
    so an empty tuple here would itself indicate a builder defect, not
    a legitimate "no uncertainty" state."""

    return max(
        (uncertainty.level for uncertainty in uncertainties),
        key=lambda level: UNCERTAINTY_RANK[level],
    )
