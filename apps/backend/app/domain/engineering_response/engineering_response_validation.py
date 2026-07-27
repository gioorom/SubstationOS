"""
Validation (Milestone 18's pipeline stage of the same name). Proves,
after building, that an ``EngineeringResponse`` satisfies every
structural invariant this milestone requires: required sections exist
in canonical order with no duplicates, metadata is complete, evidence
and version fields are preserved and mutually consistent, and every
statistic is internally consistent with the assembled sections/
warnings/uncertainties/references. Never causes building to raise -
Engineering Response always produces a structurally valid response by
construction; this is an inspectable, testable proof of that fact, not
a gate a caller must pass. O(n) in the number of sections (a small,
fixed-size collection).
"""

from __future__ import annotations

from app.domain.engineering_response.engineering_response_composition import (
    ENGINEERING_RESPONSE_SECTION_ORDER,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
    EngineeringResponseValidationResult,
)
from app.domain.engineering_response.engineering_response_policy import (
    overall_uncertainty_from,
)


def validate_response(
    response: EngineeringResponse,
) -> EngineeringResponseValidationResult:
    errors: list[str] = []

    section_types = tuple(section.section_type for section in response.sections)
    if section_types != ENGINEERING_RESPONSE_SECTION_ORDER:
        errors.append(
            "Required sections are missing or out of canonical order."
        )
    if len(set(section_types)) != len(section_types):
        errors.append("Duplicate section types are present.")

    if (
        not response.metadata.engineering_response_version
        or not response.metadata.response_policy_version
        or not response.metadata.package_version
        or response.metadata.assembled_at is None
        or response.metadata.project_id <= 0
        or not response.metadata.provider_id
        or not response.metadata.request_correlation_id
    ):
        errors.append("Metadata is incomplete.")

    if (
        not response.version.engineering_response_version
        or not response.version.response_policy_version
        or not response.version.package_version
    ):
        errors.append("Version fields are incomplete.")
    elif (
        response.version.engineering_response_version
        != response.metadata.engineering_response_version
        or response.version.response_policy_version
        != response.metadata.response_policy_version
    ):
        errors.append("Version fields are inconsistent with metadata.")

    if response.statistics.reference_count != len(response.references):
        errors.append(
            "Statistics reference_count is inconsistent with the "
            "assembled references."
        )

    if response.statistics.warning_count != len(response.warnings):
        errors.append(
            "Statistics warning_count is inconsistent with the "
            "assembled warnings."
        )

    if not response.uncertainties:
        errors.append("At least one uncertainty declaration is required.")
    else:
        if response.statistics.uncertainty_count != len(response.uncertainties):
            errors.append(
                "Statistics uncertainty_count is inconsistent with the "
                "assembled uncertainty declarations."
            )
        expected_overall = overall_uncertainty_from(response.uncertainties)
        if expected_overall != response.overall_uncertainty:
            errors.append(
                "overall_uncertainty is inconsistent with the assembled "
                "uncertainty declarations."
            )

    if response.statistics.section_count != len(response.sections):
        errors.append(
            "Statistics section_count is inconsistent with the "
            "assembled sections."
        )

    expected_enabled = sum(1 for section in response.sections if section.enabled)
    expected_disabled = len(response.sections) - expected_enabled
    if (
        response.statistics.enabled_section_count != expected_enabled
        or response.statistics.disabled_section_count != expected_disabled
    ):
        errors.append(
            "Statistics enabled/disabled section counts are "
            "inconsistent with the assembled sections."
        )

    expected_characters = sum(
        len(line) for section in response.sections for line in section.body
    )
    if response.statistics.character_count != expected_characters:
        errors.append(
            "Statistics character_count is inconsistent with the "
            "assembled sections."
        )

    return EngineeringResponseValidationResult(
        valid=not errors, errors=tuple(errors)
    )


class EngineeringResponseValidator:
    """A thin, named façade over ``validate_response`` - kept only
    because this milestone explicitly names an ``EngineeringResponseValidator``
    class; every sibling bounded context (Prompt Builder's
    ``prompt_validation.py``, Context Builder's ``context_builder_validator.py``
    output checks) exposes the same logic as a plain function instead."""

    @staticmethod
    def validate(
        response: EngineeringResponse,
    ) -> EngineeringResponseValidationResult:
        return validate_response(response)
