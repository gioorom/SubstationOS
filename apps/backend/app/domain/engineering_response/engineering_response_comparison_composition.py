"""
Comparison response composition (Milestone 24.2) - the ``Composition``
stage for a two-sided answer.

Its own module for the same reason the document-lookup composition has
one: its input is a ``ComparisonContextPackage``, not a single
``ContextPackage``, so every coverage and warning judgement has to be made
per side. Averaging the two sides' coverage would describe neither.

It performs **no semantic parsing of the provider's prose**. The direct
answer is the returned text verbatim; the only thing read out of it is the
declared outcome token on the first line
(``engineering_response_comparison.py``), exactly as a verification
verdict is read. The ADDED/REMOVED/MODIFIED/UNCHANGED grouping the prompt
asks for stays as prose in the answer - extracting it into typed findings
would mean manufacturing engineering structure out of free text.

The section shape is the same fixed nine-section shape as every other
``EngineeringResponse``.
"""

from __future__ import annotations

from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
    ComparisonOperandContext,
)
from app.domain.engineering_response.engineering_response_comparison import (
    assess_comparison,
)
from app.domain.engineering_response.engineering_response_composition import (
    build_section,
)
from app.domain.engineering_response.engineering_response_models import (
    ComparisonAssessment,
    EngineeringEvidenceReference,
    EngineeringResponseCompositionResult,
    EngineeringResponseSection,
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    EngineeringResponseStatus,
    EngineeringSectionType,
    EngineeringSourceFinishReason,
    EngineeringUncertainty,
    EngineeringUncertaintyLevel,
    EngineeringWarning,
    EngineeringWarningCategory,
)
from app.domain.engineering_response.engineering_response_policy import (
    overall_uncertainty_from,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage

_TRUNCATING_FINISH_REASONS = (
    EngineeringSourceFinishReason.MAXIMUM_OUTPUT_REACHED,
    EngineeringSourceFinishReason.STOP_SEQUENCE,
)


def _text_blocks(
    content: tuple[EngineeringResponseSourceContent, ...],
) -> tuple[EngineeringResponseSourceContent, ...]:
    return tuple(
        block for block in content if block.is_supported_text and block.text
    )


def _unsupported_blocks(
    content: tuple[EngineeringResponseSourceContent, ...],
) -> tuple[EngineeringResponseSourceContent, ...]:
    return tuple(block for block in content if not block.is_supported_text)


def _determine_status(
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseStatus:
    """Identical to the single-sided rule: this describes how complete the
    *response* is, never how complete the comparison is. Whether the two
    sides could be compared at all is the ``ComparisonAssessment``'s job,
    and conflating the two would make a truncated answer and an
    uncomparable pair look the same."""

    if not source.content:
        return EngineeringResponseStatus.EMPTY

    if not _text_blocks(source.content):
        return EngineeringResponseStatus.UNSUPPORTED

    if _unsupported_blocks(source.content):
        return EngineeringResponseStatus.PARTIAL

    if source.finish_reason in _TRUNCATING_FINISH_REASONS:
        return EngineeringResponseStatus.PARTIAL

    return EngineeringResponseStatus.COMPLETE


def _build_direct_answer_section(
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseSection:
    body = tuple(block.text for block in _text_blocks(source.content))

    return build_section(
        EngineeringSectionType.DIRECT_ANSWER, "Comparison", body
    )


def _build_references(
    prompt_package: PromptPackage,
) -> tuple[EngineeringEvidenceReference, ...]:
    return tuple(
        EngineeringEvidenceReference(
            candidate_id=reference.candidate_id,
            graph_node_ids=reference.graph_node_ids,
            graph_relationship_ids=reference.graph_relationship_ids,
        )
        for reference in prompt_package.references
    )


def _build_references_section(
    references: tuple[EngineeringEvidenceReference, ...],
) -> EngineeringResponseSection:
    body = tuple(
        f"{reference.candidate_id}: nodes={list(reference.graph_node_ids)}, "
        f"relationships={list(reference.graph_relationship_ids)}"
        for reference in references
    )

    return build_section(
        EngineeringSectionType.REFERENCES, "Evidence References", body
    )


def _missing_sides(
    comparison: ComparisonContextPackage,
) -> tuple[tuple[str, ComparisonOperandContext], ...]:
    return tuple(
        (label, operand)
        for label, operand in (
            ("LEFT", comparison.left),
            ("RIGHT", comparison.right),
        )
        if not operand.has_evidence
    )


def _build_warnings(
    comparison: ComparisonContextPackage,
    source: EngineeringResponseSourceEnvelope,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringWarning, ...]:
    warnings: list[EngineeringWarning] = []

    for label, operand in _missing_sides(comparison):
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.INSUFFICIENT_EVIDENCE,
                message=(
                    f"No project evidence was retrieved for the {label} "
                    f"subject ('{operand.designation}'). The project's "
                    "reviewed knowledge does not cover it; this is not a "
                    "finding that it is absent from the installation."
                ),
            )
        )

    for label, operand in (
        ("LEFT", comparison.left),
        ("RIGHT", comparison.right),
    ):
        if not operand.has_evidence:
            continue
        completeness = operand.package.coverage.overall_completeness
        if completeness < 1.0:
            warnings.append(
                EngineeringWarning(
                    category=EngineeringWarningCategory.PARTIAL_CONTEXT,
                    message=(
                        f"{label} context selection completeness was "
                        f"{completeness:.2f}; some retrieved knowledge for "
                        f"'{operand.designation}' was not included."
                    ),
                )
            )

    for provider_warning in source.warnings:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.PROVIDER_WARNING,
                message=provider_warning,
            )
        )

    if _unsupported_blocks(source.content):
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.UNKNOWN_CONTENT,
                message="The provider returned content SubstationOS does "
                "not interpret; it was omitted from the comparison.",
            )
        )

    if source.finish_reason in _TRUNCATING_FINISH_REASONS:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.LIMITED_RESPONSE,
                message="The comparison was not completed in full "
                f"(finish_reason={source.finish_reason.value}).",
            )
        )

    if status is EngineeringResponseStatus.UNSUPPORTED:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.UNSUPPORTED_RESPONSE,
                message="No usable text content was returned by the "
                "provider.",
            )
        )

    return tuple(warnings)


def _build_warnings_section(
    warnings: tuple[EngineeringWarning, ...],
) -> EngineeringResponseSection:
    body = tuple(
        f"[{warning.category.value}] {warning.message}" for warning in warnings
    )

    return build_section(EngineeringSectionType.WARNINGS, "Warnings", body)


def _build_limitations_section(
    comparison: ComparisonContextPackage,
    assessment: ComparisonAssessment,
) -> EngineeringResponseSection:
    lines: list[str] = [
        "This comparison evaluates only the project evidence retrieved for "
        "each subject. It is not a comparison against typical practice for "
        "this equipment type.",
    ]

    for label, operand in _missing_sides(comparison):
        lines.append(
            f"No evidence was retrieved for the {label} subject "
            f"('{operand.designation}'), so no difference involving it can "
            "be asserted."
        )

    if assessment.evidence_bounded:
        lines.append(
            "The comparison outcome was set to INSUFFICIENT_EVIDENCE "
            "because at least one side carried no evidence, regardless of "
            "what the response text states."
        )

    return build_section(
        EngineeringSectionType.LIMITATIONS, "Limitations", tuple(lines)
    )


def _build_uncertainties(
    comparison: ComparisonContextPackage,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringUncertainty, ...]:
    uncertainties: list[EngineeringUncertainty] = []

    missing = _missing_sides(comparison)
    if missing:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=tuple(
                    f"No evidence was retrieved for the {label} subject "
                    f"('{operand.designation}')."
                    for label, operand in missing
                ),
            )
        )
    else:
        worst_completeness = min(
            comparison.left.package.coverage.overall_completeness,
            comparison.right.package.coverage.overall_completeness,
        )
        if worst_completeness < 0.5:
            uncertainties.append(
                EngineeringUncertainty(
                    level=EngineeringUncertaintyLevel.HIGH,
                    reasons=(
                        "Context selection completeness on at least one "
                        f"side was only {worst_completeness:.2f}.",
                    ),
                )
            )
        elif worst_completeness < 1.0:
            uncertainties.append(
                EngineeringUncertainty(
                    level=EngineeringUncertaintyLevel.MEDIUM,
                    reasons=(
                        "Context selection completeness on at least one "
                        f"side was {worst_completeness:.2f}; some retrieved "
                        "knowledge was not included.",
                    ),
                )
            )

    if status is EngineeringResponseStatus.EMPTY:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.UNKNOWN,
                reasons=("No response content was available to assess.",),
            )
        )
    elif status is EngineeringResponseStatus.UNSUPPORTED:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=("The provider did not return usable text content.",),
            )
        )
    elif status is EngineeringResponseStatus.PARTIAL:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.MEDIUM,
                reasons=("The comparison was not returned in full.",),
            )
        )

    if not uncertainties:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.LOW,
                reasons=(
                    "Both subjects had full evidence coverage and a "
                    "complete response was returned.",
                ),
            )
        )

    return tuple(uncertainties)


def compose_comparison_response(
    comparison: ComparisonContextPackage,
    prompt_package: PromptPackage,
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseCompositionResult:
    status = _determine_status(source)
    assessment = assess_comparison(comparison, source)
    references = _build_references(prompt_package)
    warnings = _build_warnings(comparison, source, status)
    uncertainties = _build_uncertainties(comparison, status)

    summary_section = build_section(
        EngineeringSectionType.SUMMARY, "Summary", ()
    )
    direct_answer_section = _build_direct_answer_section(source)
    technical_explanation_section = build_section(
        EngineeringSectionType.TECHNICAL_EXPLANATION,
        "Technical Explanation",
        (),
    )
    assumptions_section = build_section(
        EngineeringSectionType.ASSUMPTIONS, "Assumptions", ()
    )
    warnings_section = _build_warnings_section(warnings)
    limitations_section = _build_limitations_section(comparison, assessment)
    next_actions_section = build_section(
        EngineeringSectionType.NEXT_ACTIONS, "Next Actions", ()
    )
    references_section = _build_references_section(references)
    unknown_section = build_section(
        EngineeringSectionType.UNKNOWN,
        "Unrecognized Content",
        tuple(
            f"Unsupported provider content block (type="
            f"{block.provider_block_type or 'unknown'}) at position "
            f"{block.sequence_index} was omitted."
            for block in _unsupported_blocks(source.content)
        ),
    )

    return EngineeringResponseCompositionResult(
        sections=(
            summary_section,
            direct_answer_section,
            technical_explanation_section,
            assumptions_section,
            warnings_section,
            limitations_section,
            next_actions_section,
            references_section,
            unknown_section,
        ),
        summary=summary_section,
        direct_answer=direct_answer_section,
        references=references,
        warnings=warnings,
        uncertainties=uncertainties,
        overall_uncertainty=overall_uncertainty_from(uncertainties),
        status=status,
        comparison=assessment,
    )
