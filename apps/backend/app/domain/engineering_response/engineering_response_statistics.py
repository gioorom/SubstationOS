"""
Statistics (Milestone 18's pipeline stage of the same name). Summarizes
the already-composed sections into one ``EngineeringResponseStatistics``
value object - never a recomputation of anything an earlier stage
already decided. O(n) in the number of sections, warnings, uncertainty
declarations, and references (all small, fixed or bounded collections).
Deliberately does not compute a token count - that remains Prompt
Builder's own approximate, provider-independent responsibility one
layer upstream; duplicating it here would drift out of sync with it.
"""

from __future__ import annotations

from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseCompositionResult,
    EngineeringResponseStatistics,
)


def build_statistics(
    composition: EngineeringResponseCompositionResult,
) -> EngineeringResponseStatistics:
    enabled_count = sum(1 for section in composition.sections if section.enabled)
    disabled_count = len(composition.sections) - enabled_count
    character_count = sum(
        len(line) for section in composition.sections for line in section.body
    )

    return EngineeringResponseStatistics(
        section_count=len(composition.sections),
        enabled_section_count=enabled_count,
        disabled_section_count=disabled_count,
        warning_count=len(composition.warnings),
        uncertainty_count=len(composition.uncertainties),
        reference_count=len(composition.references),
        character_count=character_count,
    )
