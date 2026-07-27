"""
Prompt Composition (Milestone 15's central pipeline stage). Assembles
every ``PromptSection`` from an already-built ``ContextPackage`` -
never from raw retrieval, never from a database, never from an AI
provider. Each ``PromptSectionType`` has exactly one small, named, pure
builder function below - "no free-form concatenation" (Milestone 15):
every section's ``content`` is a tuple of discrete lines built by a
dedicated, deterministic function, never an ad hoc string join scattered
across the codebase. A section with nothing meaningful to contribute is
still constructed, in its fixed position, with empty content and
``enabled=False`` - ``PromptPackage.sections`` always has the same
nine-section shape regardless of input.

O(n) in the number of selected candidates and warnings on the input
``ContextPackage`` - one pass to build ``SELECTED_KNOWLEDGE``, one pass
to build ``EVIDENCE_REFERENCES``, one pass to build ``WARNINGS``; every
other section is O(1).
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.composition_policy import CONSTRAINTS, INSTRUCTIONS
from app.domain.prompt_builder.prompt_builder_models import (
    PromptAssemblyResult,
    PromptEvidenceReference,
    PromptSection,
    PromptSectionType,
)
from app.domain.prompt_builder.token_estimation import estimate_tokens
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateKind,
)

# The canonical, fixed, deterministic section order - independent of
# input. Every PromptPackage.sections tuple follows exactly this order.
PROMPT_SECTION_ORDER: tuple[PromptSectionType, ...] = (
    PromptSectionType.SYSTEM_CONTEXT,
    PromptSectionType.ENGINEERING_CONTEXT,
    PromptSectionType.SELECTED_KNOWLEDGE,
    PromptSectionType.EVIDENCE_REFERENCES,
    PromptSectionType.CONSTRAINTS,
    PromptSectionType.FORMATTING_RULES,
    PromptSectionType.EXPECTED_OUTPUT,
    PromptSectionType.WARNINGS,
    PromptSectionType.METADATA,
)

_SECTION_PRIORITY: dict[PromptSectionType, int] = {
    section_type: index for index, section_type in enumerate(PROMPT_SECTION_ORDER)
}


def _section(section_type: PromptSectionType, content: tuple[str, ...]) -> PromptSection:
    return PromptSection(
        section_type=section_type,
        priority=_SECTION_PRIORITY[section_type],
        content=content,
        estimated_token_count=estimate_tokens(content),
        enabled=bool(content),
    )


def _build_system_context() -> PromptSection:
    content = (
        "You are an engineering assistant operating over SubstationOS's "
        "governed Project Knowledge Graph.",
        "Every fact supplied below has already been reviewed and "
        "approved before reaching this context.",
        "Do not use any source of knowledge other than what is "
        "explicitly supplied below.",
    )

    return _section(PromptSectionType.SYSTEM_CONTEXT, content)


def _build_engineering_context(context_package: ContextPackage) -> PromptSection:
    summary = context_package.retrieval_summary

    content = (
        f"Project id: {context_package.project_id}",
        f"Knowledge candidates retrieved: {summary.retrieved_candidate_count}",
        "Knowledge candidates selected into this context: "
        f"{len(context_package.selected_candidates)}",
        "Selection completeness: "
        f"{context_package.coverage.overall_completeness:.2f}",
    )

    return _section(PromptSectionType.ENGINEERING_CONTEXT, content)


def _describe_candidate(candidate: KnowledgeCandidate) -> str:
    if candidate.candidate_kind is KnowledgeCandidateKind.ATTRIBUTE:
        reference = candidate.primary_reference
        attribute = candidate.matched_attributes[0]
        subject = (
            f"{reference.entity_type}:{reference.canonical_id}"
            if reference is not None
            else "unknown"
        )
        return (
            f"ATTRIBUTE {subject}.{attribute.name} = {attribute.value} "
            f"(score {candidate.score.total})"
        )

    if candidate.candidate_kind is KnowledgeCandidateKind.RELATIONSHIP:
        relationship = candidate.matched_relationships[0]
        subject = (
            f"{relationship.subject.entity_type}:"
            f"{relationship.subject.canonical_id}"
        )
        obj = f"{relationship.object.entity_type}:{relationship.object.canonical_id}"
        return (
            f"RELATIONSHIP {subject} {relationship.relationship_type.value} "
            f"{obj} (score {candidate.score.total})"
        )

    if candidate.primary_reference is not None:
        reference = candidate.primary_reference
        return (
            f"ENTITY {reference.entity_type}:{reference.canonical_id} "
            f"(score {candidate.score.total})"
        )

    return f"{candidate.candidate_kind.value.upper()} {candidate.candidate_id}"


def _build_selected_knowledge(
    context_package: ContextPackage,
) -> PromptSection:
    content = tuple(
        _describe_candidate(candidate)
        for candidate in context_package.selected_candidates
    )

    return _section(PromptSectionType.SELECTED_KNOWLEDGE, content)


def _build_references(
    context_package: ContextPackage,
) -> tuple[PromptEvidenceReference, ...]:
    return tuple(
        PromptEvidenceReference(
            candidate_id=candidate.candidate_id,
            graph_node_ids=candidate.graph_node_ids,
            graph_relationship_ids=candidate.graph_relationship_ids,
        )
        for candidate in context_package.selected_candidates
    )


def _build_evidence_references(
    references: tuple[PromptEvidenceReference, ...],
) -> PromptSection:
    content = tuple(
        f"{reference.candidate_id}: nodes={list(reference.graph_node_ids)}, "
        f"relationships={list(reference.graph_relationship_ids)}"
        for reference in references
    )

    return _section(PromptSectionType.EVIDENCE_REFERENCES, content)


def _build_constraints_section() -> PromptSection:
    content = tuple(constraint.description for constraint in CONSTRAINTS)

    return _section(PromptSectionType.CONSTRAINTS, content)


def _build_formatting_rules_section() -> PromptSection:
    content = tuple(instruction.description for instruction in INSTRUCTIONS)

    return _section(PromptSectionType.FORMATTING_RULES, content)


def _build_expected_output() -> PromptSection:
    content = (
        "Provide a clear, structured answer using only the evidence "
        "supplied above.",
        "Cite each claim by its evidence reference candidate id.",
        "If the supplied evidence does not fully answer the question, "
        "state explicitly what is missing.",
    )

    return _section(PromptSectionType.EXPECTED_OUTPUT, content)


def _build_warnings_section(context_package: ContextPackage) -> PromptSection:
    content = tuple(
        f"[{warning.category.value}] {warning.message}"
        for warning in context_package.warnings
    )

    return _section(PromptSectionType.WARNINGS, content)


def _build_metadata_section(context_package: ContextPackage) -> PromptSection:
    metadata = context_package.metadata
    content = (
        f"Context assembled at: {metadata.assembled_at.isoformat()}",
        f"Context builder version: {metadata.context_builder_version}",
        "Retrieval policy version: "
        f"{metadata.retrieval_policy_version or 'unknown'}",
    )

    return _section(PromptSectionType.METADATA, content)


def compose_sections(context_package: ContextPackage) -> PromptAssemblyResult:
    system_context = _build_system_context()
    engineering_context = _build_engineering_context(context_package)
    selected_knowledge = _build_selected_knowledge(context_package)
    references = _build_references(context_package)
    evidence_references = _build_evidence_references(references)
    constraints_section = _build_constraints_section()
    formatting_rules_section = _build_formatting_rules_section()
    expected_output = _build_expected_output()
    warnings_section = _build_warnings_section(context_package)
    metadata_section = _build_metadata_section(context_package)

    sections = (
        system_context,
        engineering_context,
        selected_knowledge,
        evidence_references,
        constraints_section,
        formatting_rules_section,
        expected_output,
        warnings_section,
        metadata_section,
    )

    return PromptAssemblyResult(
        sections=sections,
        system_context=system_context,
        engineering_context=engineering_context,
        retrieved_knowledge=selected_knowledge,
        expected_output=expected_output,
        constraints=CONSTRAINTS,
        instructions=INSTRUCTIONS,
        references=references,
    )
