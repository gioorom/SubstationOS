"""
Engineering Response Composition (Milestone 18's central pipeline
stage). Builds every ``EngineeringResponseSection``, structured
``EngineeringWarning``, and ``EngineeringUncertainty`` declaration from
an already-built ``ContextPackage``/``PromptPackage``/
``EngineeringResponseSourceEnvelope`` - never from raw retrieval, never
from a database, never from an AI provider call of its own.

This module performs **no AI usage and no semantic parsing of the
provider's own returned text**. Every section, warning, and uncertainty
declaration below is derived from *structural* signals already present
on the source envelope and its upstream packages (content-block types,
finish reason, coverage ratios, retrieved-candidate counts) - never by
reading the model's prose and guessing which sentences are "the
summary" versus "an assumption." This is why ``SUMMARY``/
``TECHNICAL_EXPLANATION``/``ASSUMPTIONS``/``NEXT_ACTIONS`` are always
constructed disabled and empty: inventing a split of free text into
those categories would itself be inventing engineering structure that
was never actually there (Milestone 18's own "never invent engineering
facts" rule applies to structure, not only to content).

**The one narrow exception**, added in Milestone 24.1: for a response
built from a *verification* prompt, the answer's first line is matched
against the four verdict tokens Prompt Builder explicitly asked for
(``engineering_response_verification.py``). That is reading a declared
protocol - the same kind of operation as reading ``finish_reason`` off
the envelope - not interpreting prose: nothing beyond the first line is
examined, no keyword is searched for, and a non-matching line yields no
verdict rather than a guessed one. The rule above is otherwise unchanged,
and it still holds for every other objective.

O(n) in the number of content blocks, references, and warnings on the
input - a small, constant number of linear passes over already
materialized data.
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
)
from app.domain.engineering_response.engineering_response_models import (
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
    VerificationAssessment,
)
from app.domain.engineering_response.engineering_response_policy import (
    overall_uncertainty_from,
)
from app.domain.engineering_response.engineering_response_verification import (
    assess_verification,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptObjective,
    PromptPackage,
)

# The canonical, fixed, deterministic section order - independent of
# input. Every EngineeringResponse.sections tuple follows exactly this
# order.
ENGINEERING_RESPONSE_SECTION_ORDER: tuple[EngineeringSectionType, ...] = (
    EngineeringSectionType.SUMMARY,
    EngineeringSectionType.DIRECT_ANSWER,
    EngineeringSectionType.TECHNICAL_EXPLANATION,
    EngineeringSectionType.ASSUMPTIONS,
    EngineeringSectionType.WARNINGS,
    EngineeringSectionType.LIMITATIONS,
    EngineeringSectionType.NEXT_ACTIONS,
    EngineeringSectionType.REFERENCES,
    EngineeringSectionType.UNKNOWN,
)

_SECTION_SEQUENCE: dict[EngineeringSectionType, int] = {
    section_type: index
    for index, section_type in enumerate(ENGINEERING_RESPONSE_SECTION_ORDER)
}

_TRUNCATING_FINISH_REASONS = (
    EngineeringSourceFinishReason.MAXIMUM_OUTPUT_REACHED,
    EngineeringSourceFinishReason.STOP_SEQUENCE,
)


def build_section(
    section_type: EngineeringSectionType, title: str, body: tuple[str, ...]
) -> EngineeringResponseSection:
    """Constructs one section in its fixed canonical position, enabled
    exactly when it has something to say. Public because every
    composition stage - this one and
    ``engineering_response_document_composition.py`` - must place
    sections identically; two copies of this rule could drift apart and
    break the "always the same nine-section shape" invariant."""

    return EngineeringResponseSection(
        section_type=section_type,
        title=title,
        body=body,
        sequence=_SECTION_SEQUENCE[section_type],
        enabled=bool(body),
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
    if not source.content:
        return EngineeringResponseStatus.EMPTY

    text_blocks = _text_blocks(source.content)
    if not text_blocks:
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

    return build_section(EngineeringSectionType.DIRECT_ANSWER, "Direct Answer", body)


def _build_references(
    prompt_package: PromptPackage,
) -> tuple[EngineeringEvidenceReference, ...]:
    return tuple(
        EngineeringEvidenceReference(
            item_id=reference.item_id,
            node_ids=reference.node_ids,
            edge_ids=reference.edge_ids,
            statement_key=reference.statement_key,
            review_id=reference.review_id,
            document_id=reference.document_id,
        )
        for reference in prompt_package.references
    )


def _build_references_section(
    references: tuple[EngineeringEvidenceReference, ...],
) -> EngineeringResponseSection:
    body = tuple(
        f"{reference.item_id}: nodes={list(reference.node_ids)}, "
        f"edges={list(reference.edge_ids)}, "
        f"statement={reference.statement_key}, "
        f"review={reference.review_id}, "
        f"document={reference.document_id}"
        for reference in references
    )

    return build_section(EngineeringSectionType.REFERENCES, "Evidence References", body)


def _build_unknown_section(
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseSection:
    body = tuple(
        f"Unsupported provider content block (type="
        f"{block.provider_block_type or 'unknown'}) at position "
        f"{block.sequence_index} was omitted."
        for block in _unsupported_blocks(source.content)
    )

    return build_section(EngineeringSectionType.UNKNOWN, "Unrecognized Content", body)


def _ambiguous_queries(context_package: ContextPackage):
    """
    The governed queries that had more than one governed answer.

    Read from the context rather than recomputed: retrieval decided what
    was ambiguous, Context Assembly carried that decision through, and a
    second definition here would eventually disagree with the first.
    """

    return tuple(
        query
        for query in context_package.retrieval_summary.queries
        if query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
    )


def _build_warnings(
    context_package: ContextPackage,
    source: EngineeringResponseSourceEnvelope,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringWarning, ...]:
    warnings: list[EngineeringWarning] = []

    retrieved_count = context_package.retrieval_summary.retrieved_item_count
    completeness = context_package.coverage.overall_completeness

    if retrieved_count == 0:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.INSUFFICIENT_EVIDENCE,
                message="No supporting evidence was available in the "
                "knowledge context.",
            )
        )
    elif completeness < 1.0:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.PARTIAL_CONTEXT,
                message="Knowledge context selection completeness was "
                f"{completeness:.2f}; some retrieved knowledge was not "
                "included.",
            )
        )

    for ambiguous in _ambiguous_queries(context_package):
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.AMBIGUOUS_KNOWLEDGE,
                message=(
                    f"'{ambiguous.normalized_query}' matched "
                    f"{ambiguous.matched_before_limit} distinct governed "
                    "objects, which were not merged. This answer may "
                    "describe more than one piece of equipment."
                    if ambiguous.normalized_query
                    else (
                        f"A governed {ambiguous.query_type.value} query "
                        f"matched {ambiguous.matched_before_limit} distinct "
                        "governed objects, which were not merged."
                    )
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
                "not interpret; it was omitted from the direct answer.",
            )
        )

    if source.finish_reason in _TRUNCATING_FINISH_REASONS:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.LIMITED_RESPONSE,
                message="The response was not completed in full "
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
    body = tuple(f"[{warning.category.value}] {warning.message}" for warning in warnings)

    return build_section(EngineeringSectionType.WARNINGS, "Warnings", body)


def _build_limitations_section(
    context_package: ContextPackage,
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseSection:
    lines: list[str] = []

    if source.finish_reason is EngineeringSourceFinishReason.MAXIMUM_OUTPUT_REACHED:
        lines.append(
            "Response was truncated: maximum output length reached."
        )

    if source.finish_reason is EngineeringSourceFinishReason.STOP_SEQUENCE:
        lines.append(
            "Response stopped at a configured stop sequence before "
            "completion."
        )

    unsupported = _unsupported_blocks(source.content)
    if unsupported:
        lines.append(
            f"{len(unsupported)} provider content block(s) were of an "
            "unsupported type and were omitted from the direct answer."
        )

    retrieved_count = context_package.retrieval_summary.retrieved_item_count
    completeness = context_package.coverage.overall_completeness
    if retrieved_count > 0 and completeness < 1.0:
        lines.append(
            "The underlying knowledge context was incomplete (selection "
            f"completeness: {completeness:.2f})."
        )

    return build_section(EngineeringSectionType.LIMITATIONS, "Limitations", tuple(lines))


def _build_uncertainties(
    context_package: ContextPackage,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringUncertainty, ...]:
    uncertainties: list[EngineeringUncertainty] = []

    if status is EngineeringResponseStatus.EMPTY:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.UNKNOWN,
                reasons=("No response content was available to assess.",),
            )
        )

    ambiguous = _ambiguous_queries(context_package)
    if ambiguous:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=tuple(
                    (
                        f"'{query.normalized_query}' names more than one "
                        "governed object; this answer may not be about a "
                        "single piece of equipment."
                    )
                    if query.normalized_query
                    else (
                        f"A governed {query.query_type.value} query matched "
                        "more than one governed object."
                    )
                    for query in ambiguous
                ),
            )
        )

    retrieved_count = context_package.retrieval_summary.retrieved_item_count
    completeness = context_package.coverage.overall_completeness

    if retrieved_count == 0:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=(
                    "No governed knowledge was retrieved for this "
                    "project.",
                ),
            )
        )
    elif completeness < 0.5:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=(
                    "Knowledge context selection completeness was only "
                    f"{completeness:.2f}.",
                ),
            )
        )
    elif completeness < 1.0:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.MEDIUM,
                reasons=(
                    "Knowledge context selection completeness was "
                    f"{completeness:.2f}; some retrieved knowledge was "
                    "not included.",
                ),
            )
        )

    if status is EngineeringResponseStatus.UNSUPPORTED:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=(
                    "The provider did not return usable text content.",
                ),
            )
        )
    elif status is EngineeringResponseStatus.PARTIAL:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.MEDIUM,
                reasons=("The response was not returned in full.",),
            )
        )

    if not uncertainties:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.LOW,
                reasons=(
                    "Full knowledge coverage and a complete provider "
                    "response were available.",
                ),
            )
        )

    return tuple(uncertainties)


def _verification_assessment(
    context_package: ContextPackage,
    prompt_package: PromptPackage,
    source: EngineeringResponseSourceEnvelope,
) -> VerificationAssessment | None:
    """
    Assessed only when the prompt that produced this response actually
    asked for a verification.

    The objective is read off the ``PromptPackage`` rather than passed in
    separately, because the package is already the record of what was
    asked - a response cannot carry a verdict for a question nobody put.
    This is a branch on the *prompt objective*, not on a workflow or an
    intent: Engineering Response has always shaped its output from the
    structure of its inputs, and the engine knows nothing about it.
    """

    if prompt_package.objective is not PromptObjective.ENGINEERING_VERIFICATION:
        return None

    return assess_verification(context_package, source)


def compose_engineering_response(
    context_package: ContextPackage,
    prompt_package: PromptPackage,
    source: EngineeringResponseSourceEnvelope,
) -> EngineeringResponseCompositionResult:
    status = _determine_status(source)
    references = _build_references(prompt_package)
    warnings = _build_warnings(context_package, source, status)
    uncertainties = _build_uncertainties(context_package, status)
    overall_uncertainty = overall_uncertainty_from(uncertainties)

    summary_section = build_section(EngineeringSectionType.SUMMARY, "Summary", ())
    direct_answer_section = _build_direct_answer_section(source)
    technical_explanation_section = build_section(
        EngineeringSectionType.TECHNICAL_EXPLANATION, "Technical Explanation", ()
    )
    assumptions_section = build_section(
        EngineeringSectionType.ASSUMPTIONS, "Assumptions", ()
    )
    warnings_section = _build_warnings_section(warnings)
    limitations_section = _build_limitations_section(context_package, source)
    next_actions_section = build_section(
        EngineeringSectionType.NEXT_ACTIONS, "Next Actions", ()
    )
    references_section = _build_references_section(references)
    unknown_section = _build_unknown_section(source)

    sections = (
        summary_section,
        direct_answer_section,
        technical_explanation_section,
        assumptions_section,
        warnings_section,
        limitations_section,
        next_actions_section,
        references_section,
        unknown_section,
    )

    return EngineeringResponseCompositionResult(
        sections=sections,
        summary=summary_section,
        direct_answer=direct_answer_section,
        references=references,
        warnings=warnings,
        uncertainties=uncertainties,
        overall_uncertainty=overall_uncertainty,
        status=status,
        verification=_verification_assessment(
            context_package, prompt_package, source
        ),
    )
