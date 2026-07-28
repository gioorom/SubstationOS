"""
Comparison prompt composition (Milestone 24.2) - the only composition
that assembles a prompt from **two** labelled evidence groups.

It reuses ``prompt_composition``'s own section builder and candidate
renderer rather than restating them, so a comparison prompt places its
sections in the same canonical order and describes a candidate the same
way every other prompt does. What it adds is the one thing a comparison
genuinely needs: ``LEFT_KNOWLEDGE`` and ``RIGHT_KNOWLEDGE`` as separate,
typed sections.

**The two sides are never merged.** Rendering them as labelled lines
inside one section would technically preserve the labels, but it would
also mean a formatting change could silently transpose them - and a
comparison answered backwards is worse than one not answered. Separate
sections make the direction structural.

``EVIDENCE_REFERENCES`` carries both sides' references, in left-then-right
order, because a citation must be resolvable whichever side it came from.
Which side a candidate belongs to remains recoverable from the
``ComparisonContextPackage`` itself, which keeps the two packages whole.

Pure and deterministic, and performs no AI usage: every line is built from
already-materialized context, exactly as Milestone 15 requires.
"""

from __future__ import annotations

from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
    ComparisonOperandContext,
)
from app.domain.prompt_builder.composition_policy import (
    CONSTRAINTS,
    EXPECTED_OUTPUT_BY_OBJECTIVE,
    INSTRUCTIONS_BY_OBJECTIVE,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptAssemblyResult,
    PromptEvidenceReference,
    PromptObjective,
    PromptSection,
    PromptSectionType,
)
from app.domain.prompt_builder.prompt_composition import (
    describe_candidate,
    section,
)

_OBJECTIVE = PromptObjective.ENGINEERING_COMPARISON


def _build_system_context() -> PromptSection:
    content = (
        "You are an engineering assistant operating over SubstationOS's "
        "governed Project Knowledge Graph.",
        "Every fact supplied below has already been reviewed and "
        "approved before reaching this context.",
        "You are comparing two subjects. Their evidence is supplied as "
        "two separate, labelled groups: LEFT and RIGHT.",
        "Do not use any source of knowledge other than what is "
        "explicitly supplied below.",
    )

    return section(PromptSectionType.SYSTEM_CONTEXT, content)


def _build_engineering_context(
    comparison: ComparisonContextPackage,
) -> PromptSection:
    """States both sides' evidence counts explicitly, so the model can see
    that one side is thin *before* it starts reporting differences."""

    left = comparison.left
    right = comparison.right

    content = (
        f"Project id: {comparison.project_id}",
        f"LEFT subject: {left.designation}",
        f"LEFT evidence items: {left.evidence_count}",
        f"RIGHT subject: {right.designation}",
        f"RIGHT evidence items: {right.evidence_count}",
        "Direction: report findings as changes from LEFT to RIGHT.",
    )

    return section(PromptSectionType.ENGINEERING_CONTEXT, content)


def _build_side(
    section_type: PromptSectionType,
    label: str,
    operand: ComparisonOperandContext,
) -> PromptSection:
    """A side with no evidence is rendered as an explicit statement that
    the project holds none, not as an empty section: an empty section
    would leave the model to infer *why* it is empty, and the likeliest
    wrong inference - that the equipment does not exist - is exactly the
    one this workflow must prevent."""

    if not operand.has_evidence:
        return section(
            section_type,
            (
                f"{label} subject: {operand.designation}",
                f"No project evidence was retrieved for the {label} "
                "subject. This means the project's reviewed knowledge "
                "does not cover it - not that it does not exist.",
            ),
        )

    content = (f"{label} subject: {operand.designation}",) + tuple(
        f"{label}: {describe_candidate(candidate)}"
        for candidate in operand.package.selected_candidates
    )

    return section(section_type, content)


def _build_references(
    comparison: ComparisonContextPackage,
) -> tuple[PromptEvidenceReference, ...]:
    return tuple(
        PromptEvidenceReference(
            candidate_id=candidate.candidate_id,
            graph_node_ids=candidate.graph_node_ids,
            graph_relationship_ids=candidate.graph_relationship_ids,
        )
        for operand in (comparison.left, comparison.right)
        for candidate in operand.package.selected_candidates
    )


def _build_evidence_references_section(
    comparison: ComparisonContextPackage,
) -> PromptSection:
    content = tuple(
        f"{label}: {candidate.candidate_id}: "
        f"nodes={list(candidate.graph_node_ids)}, "
        f"relationships={list(candidate.graph_relationship_ids)}"
        for label, operand in (
            ("LEFT", comparison.left),
            ("RIGHT", comparison.right),
        )
        for candidate in operand.package.selected_candidates
    )

    return section(PromptSectionType.EVIDENCE_REFERENCES, content)


def _build_warnings_section(
    comparison: ComparisonContextPackage,
) -> PromptSection:
    """Both sides' own context warnings, each attributed to its side, plus
    an explicit warning whenever a side carries no evidence at all."""

    lines: list[str] = []

    for label, operand in (
        ("LEFT", comparison.left),
        ("RIGHT", comparison.right),
    ):
        if not operand.has_evidence:
            lines.append(
                f"[insufficient_evidence] No evidence was retrieved for "
                f"the {label} subject; the comparison cannot be completed "
                "from this context."
            )
        for warning in operand.package.warnings:
            lines.append(
                f"[{label}] [{warning.category.value}] {warning.message}"
            )

    return section(PromptSectionType.WARNINGS, tuple(lines))


def _build_metadata_section(
    comparison: ComparisonContextPackage,
) -> PromptSection:
    left_metadata = comparison.left.package.metadata

    content = (
        f"Context assembled at: {comparison.assembled_at.isoformat()}",
        f"Context builder version: {left_metadata.context_builder_version}",
        "Retrieval policy version: "
        f"{left_metadata.retrieval_policy_version or 'unknown'}",
    )

    return section(PromptSectionType.METADATA, content)


def compose_comparison_sections(
    comparison: ComparisonContextPackage,
) -> PromptAssemblyResult:
    instructions = INSTRUCTIONS_BY_OBJECTIVE[_OBJECTIVE]

    system_context = _build_system_context()
    engineering_context = _build_engineering_context(comparison)
    # SELECTED_KNOWLEDGE stays empty for a comparison: there is no single
    # body of selected knowledge, and putting either side there would
    # imply one is the default.
    selected_knowledge = section(PromptSectionType.SELECTED_KNOWLEDGE, ())
    left_knowledge = _build_side(
        PromptSectionType.LEFT_KNOWLEDGE, "LEFT", comparison.left
    )
    right_knowledge = _build_side(
        PromptSectionType.RIGHT_KNOWLEDGE, "RIGHT", comparison.right
    )
    references = _build_references(comparison)
    evidence_references = _build_evidence_references_section(comparison)
    constraints_section = section(
        PromptSectionType.CONSTRAINTS,
        tuple(constraint.description for constraint in CONSTRAINTS),
    )
    formatting_rules_section = section(
        PromptSectionType.FORMATTING_RULES,
        tuple(instruction.description for instruction in instructions),
    )
    expected_output = section(
        PromptSectionType.EXPECTED_OUTPUT,
        EXPECTED_OUTPUT_BY_OBJECTIVE[_OBJECTIVE],
    )
    warnings_section = _build_warnings_section(comparison)
    metadata_section = _build_metadata_section(comparison)

    return PromptAssemblyResult(
        sections=(
            system_context,
            engineering_context,
            selected_knowledge,
            left_knowledge,
            right_knowledge,
            evidence_references,
            constraints_section,
            formatting_rules_section,
            expected_output,
            warnings_section,
            metadata_section,
        ),
        system_context=system_context,
        engineering_context=engineering_context,
        retrieved_knowledge=selected_knowledge,
        expected_output=expected_output,
        constraints=CONSTRAINTS,
        instructions=instructions,
        references=references,
    )
