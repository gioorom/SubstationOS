"""
Validation (Milestone 18's pipeline stage of the same name). Proves,
after building, that an ``EngineeringResponse`` satisfies every
structural invariant this milestone requires: required sections exist
in canonical order with no duplicates, metadata is complete, evidence
and version fields are preserved and mutually consistent, and every
statistic is internally consistent with the assembled sections/
warnings/uncertainties/references.

Shared by **both** production paths since Milestone 23B.1: an
``EngineeringResponse`` composed from deterministic retrieval is held to
exactly the same structural invariants as one composed from an LLM
invocation, plus the origin/provider correspondence ``_origin_errors``
enforces. Never causes building to raise -
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
    EngineeringResponseOrigin,
    EngineeringResponseValidationResult,
    ComparisonOutcome,
    VerificationOutcome,
)
from app.domain.engineering_response.engineering_response_policy import (
    overall_uncertainty_from,
)


def _origin_errors(response: EngineeringResponse) -> list[str]:
    """
    Provider metadata must correspond to the origin **in both
    directions**: an ``LLM_INVOCATION`` response names the provider and
    model that produced it, and a ``DETERMINISTIC_RETRIEVAL`` response
    names neither. Checking only the first direction would let a
    deterministic response quietly claim a provider it never called,
    which is exactly the fabrication this project refuses.
    """

    metadata = response.metadata

    if response.origin is EngineeringResponseOrigin.LLM_INVOCATION:
        if not metadata.provider_id or not (
            metadata.configured_model_identifier
        ):
            return [
                "Metadata is incomplete: an LLM_INVOCATION response must "
                "name the provider and model that produced it."
            ]

        return []

    errors: list[str] = []

    if (
        metadata.provider_id is not None
        or metadata.configured_model_identifier is not None
        or metadata.returned_model_identifier is not None
    ):
        errors.append(
            "A DETERMINISTIC_RETRIEVAL response must name no provider and "
            "no model - none was involved."
        )

    if response.version.runtime_version is not None:
        errors.append(
            "A DETERMINISTIC_RETRIEVAL response must record no LLM runtime "
            "version - the runtime was never invoked."
        )

    return errors


def _verification_errors(response: EngineeringResponse) -> list[str]:
    """
    Structural consistency of a verification assessment. Never judges
    whether the verdict was *correct* - that is an engineering judgement
    this validator has no basis to make, and claiming otherwise would be
    the invention the whole context forbids.
    """

    assessment = response.verification

    if assessment is None:
        return []

    errors: list[str] = []

    if assessment.evidence_reference_count < 0:
        errors.append("A verification assessment reports negative evidence.")

    if assessment.evidence_bounded:
        # The structural override: an empty evidence set forces
        # INSUFFICIENT_EVIDENCE, so nothing else may be reported.
        if assessment.evidence_reference_count != 0:
            errors.append(
                "A verification bounded by empty evidence must report no "
                "evidence references."
            )
        if assessment.outcome is not (
            VerificationOutcome.INSUFFICIENT_EVIDENCE
        ):
            errors.append(
                "A verification with no retrieved evidence must report "
                "INSUFFICIENT_EVIDENCE - nothing existed to support or "
                "contradict the statement."
            )
    elif assessment.outcome is None and assessment.stated_by_model:
        errors.append(
            "A verification reporting no outcome must not claim the model "
            "stated one."
        )

    return errors


def _comparison_errors(response: EngineeringResponse) -> list[str]:
    """
    Structural consistency of a comparison assessment. Never judges
    whether the comparison was *correct*.

    The rule that carries the weight is the evidence bound: a comparison
    with a side that retrieved nothing must report
    ``INSUFFICIENT_EVIDENCE``, because the absent side's silence is a gap
    in the project's reviewed knowledge and can never honestly become a
    difference.
    """

    assessment = response.comparison

    if assessment is None:
        return []

    errors: list[str] = []

    if (
        assessment.left_evidence_count < 0
        or assessment.right_evidence_count < 0
    ):
        errors.append("A comparison assessment reports negative evidence.")

    both_sides = assessment.has_both_sides

    if assessment.evidence_bounded:
        if both_sides:
            errors.append(
                "A comparison bounded by missing evidence must report at "
                "least one side with no evidence."
            )
        if assessment.outcome is not ComparisonOutcome.INSUFFICIENT_EVIDENCE:
            errors.append(
                "A comparison with a side carrying no evidence must report "
                "INSUFFICIENT_EVIDENCE - a missing side is never a "
                "difference."
            )
    else:
        if not both_sides:
            errors.append(
                "A comparison with a side carrying no evidence must be "
                "reported as evidence-bounded."
            )
        if assessment.outcome is None and assessment.stated_by_model:
            errors.append(
                "A comparison reporting no outcome must not claim the model "
                "stated one."
            )

    return errors


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
        or not response.metadata.request_correlation_id
    ):
        errors.append("Metadata is incomplete.")

    errors.extend(_origin_errors(response))
    errors.extend(_verification_errors(response))
    errors.extend(_comparison_errors(response))

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

    if response.statistics.document_reference_count != len(
        response.document_references
    ):
        errors.append(
            "Statistics document_reference_count is inconsistent with the "
            "assembled document references."
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
