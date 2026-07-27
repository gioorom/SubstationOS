"""
Statistics (Milestone 15's pipeline stage of the same name). Summarizes
the already-composed sections and the input ``ContextPackage`` into one
``PromptStatistics`` value object - never a recomputation of anything
an earlier stage already decided. O(n) in the number of sections and
warnings (both small, fixed-size collections).
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.prompt_builder_models import (
    PromptAssemblyResult,
    PromptStatistics,
)


def build_statistics(
    assembly: PromptAssemblyResult, context_package: ContextPackage
) -> PromptStatistics:
    enabled_count = sum(1 for section in assembly.sections if section.enabled)
    disabled_count = len(assembly.sections) - enabled_count
    total_tokens = sum(
        section.estimated_token_count for section in assembly.sections
    )
    warnings = tuple(
        f"{warning.category.value}: {warning.message}"
        for warning in context_package.warnings
    )

    return PromptStatistics(
        section_count=len(assembly.sections),
        estimated_total_tokens=total_tokens,
        enabled_section_count=enabled_count,
        disabled_section_count=disabled_count,
        knowledge_item_count=len(context_package.selected_candidates),
        reference_count=len(assembly.references),
        warnings=warnings,
    )
