"""
Validation (Milestone 15's pipeline stage of the same name). Proves,
after assembly, that a ``PromptPackage`` satisfies every structural
invariant this milestone requires: required sections exist, section
ordering is canonical, constraints are present, metadata is complete,
and statistics are internally consistent with the assembled sections.
Never causes assembly to raise - Prompt Builder always produces a
structurally valid package by construction; this is an inspectable,
testable proof of that fact, not a gate a caller must pass. O(n) in the
number of sections (a small, fixed-size collection).
"""

from __future__ import annotations

from app.domain.prompt_builder.prompt_builder_models import (
    PromptPackage,
    PromptValidationResult,
)
from app.domain.prompt_builder.prompt_composition import PROMPT_SECTION_ORDER


def validate_package(package: PromptPackage) -> PromptValidationResult:
    errors: list[str] = []

    section_types = tuple(section.section_type for section in package.sections)
    if section_types != PROMPT_SECTION_ORDER:
        errors.append(
            "Required sections are missing or out of canonical order."
        )

    if not package.constraints:
        errors.append("No constraints are present.")

    if not package.instructions:
        errors.append("No instructions are present.")

    if (
        not package.metadata.prompt_builder_version
        or not package.metadata.composition_policy_version
        or not package.metadata.package_version
        or package.metadata.assembled_at is None
    ):
        errors.append("Metadata is incomplete.")

    if package.statistics.section_count != len(package.sections):
        errors.append(
            "Statistics section_count is inconsistent with the "
            "assembled sections."
        )

    expected_enabled = sum(1 for section in package.sections if section.enabled)
    expected_disabled = len(package.sections) - expected_enabled
    if (
        package.statistics.enabled_section_count != expected_enabled
        or package.statistics.disabled_section_count != expected_disabled
    ):
        errors.append(
            "Statistics enabled/disabled section counts are "
            "inconsistent with the assembled sections."
        )

    if package.statistics.reference_count != len(package.references):
        errors.append(
            "Statistics reference_count is inconsistent with the "
            "assembled references."
        )

    return PromptValidationResult(valid=not errors, errors=tuple(errors))
