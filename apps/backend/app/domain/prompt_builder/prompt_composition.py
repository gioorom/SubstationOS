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
eleven-section shape regardless of input.

``LEFT_KNOWLEDGE``/``RIGHT_KNOWLEDGE`` are populated only by the
comparison composition (``comparison_prompt_composition.py``); this
module always constructs them empty and disabled, which is why every
prompt keeps the same shape whether or not it compares anything.

O(n) in the number of selected candidates and warnings on the input
``ContextPackage`` - one pass to build ``SELECTED_KNOWLEDGE``, one pass
to build ``EVIDENCE_REFERENCES``, one pass to build ``WARNINGS``; every
other section is O(1).
"""

from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_reasoning.reasoning_models import (
    ReasoningResult,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
    StructuralReasoningOutcome,
)
from app.domain.prompt_builder.composition_policy import (
    CONSTRAINTS,
    EXPECTED_OUTPUT_BY_OBJECTIVE,
    INSTRUCTIONS_BY_OBJECTIVE,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptAssemblyResult,
    PromptEvidenceReference,
    PromptInstruction,
    PromptObjective,
    PromptSection,
    PromptSectionType,
)
from app.domain.prompt_builder.token_estimation import estimate_tokens
from app.domain.context_builder.context_builder_models import ContextItem
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedResultKind,
)

# The canonical, fixed, deterministic section order - independent of
# input. Every PromptPackage.sections tuple follows exactly this order.
PROMPT_SECTION_ORDER: tuple[PromptSectionType, ...] = (
    PromptSectionType.SYSTEM_CONTEXT,
    PromptSectionType.ENGINEERING_CONTEXT,
    PromptSectionType.SELECTED_KNOWLEDGE,
    PromptSectionType.DERIVED_REASONING,
    PromptSectionType.LEFT_KNOWLEDGE,
    PromptSectionType.RIGHT_KNOWLEDGE,
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


def section(
    section_type: PromptSectionType, content: tuple[str, ...]
) -> PromptSection:
    """Constructs one section in its fixed canonical position, enabled
    exactly when it has content. Public because the comparison
    composition (``comparison_prompt_composition.py``) must place
    sections identically - two copies of this rule could drift and break
    the "always the same shape" invariant."""

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
        "Governed Knowledge Graph.",
        "Every statement supplied below was interpreted deterministically "
        "from a document and approved by a named engineer, and each one "
        "cites the review that authorised it.",
        "Approved means an engineer accepted that statement. It does not "
        "mean the knowledge below is complete, and it does not mean a "
        "question has exactly one answer.",
        "Do not use any source of knowledge other than what is "
        "explicitly supplied below.",
    )

    return section(PromptSectionType.SYSTEM_CONTEXT, content)


def _build_engineering_context(context_package: ContextPackage) -> PromptSection:
    summary = context_package.retrieval_summary

    content = (
        f"Project id: {context_package.project_id}",
        "Governed results retrieved: "
        f"{summary.retrieved_item_count} of {summary.total_before_limit} "
        "matched",
        "Governed results included in this context: "
        f"{len(context_package.selected_items)}",
        "Selection completeness: "
        f"{context_package.coverage.overall_completeness:.2f}",
    ) + _ambiguity_lines(context_package)

    return section(PromptSectionType.ENGINEERING_CONTEXT, content)


def evidence_reference(item: ContextItem) -> PromptEvidenceReference:
    """
    One governed citation for one context item.

    Built here rather than in Context Assembly because a citation is a
    *prompt* concept: the context carries the whole governed item, and
    this is the subset a consumer needs in order to follow a claim back
    to the review that authorised it.
    """

    result = item.result
    node_ids = () if result.node is None else (result.node.node_id,)
    edge_ids = (
        ()
        if result.relationship is None
        else (result.relationship.edge_id,)
    )

    return PromptEvidenceReference(
        item_id=result.result_id,
        node_ids=node_ids,
        edge_ids=edge_ids,
        statement_key=result.provenance.statement_key,
        review_id=result.provenance.review_id,
        document_id=result.provenance.document_id,
    )


def describe_reference(reference: PromptEvidenceReference) -> str:
    """One citation, as one prompt line. Identities only - never the
    statement, the facts, the evidence or their text, all of which stay
    in the pipeline that produced them."""

    return (
        f"{reference.item_id}: nodes={list(reference.node_ids)}, "
        f"edges={list(reference.edge_ids)}, "
        f"statement={reference.statement_key}, "
        f"review={reference.review_id}, "
        f"document={reference.document_id}"
    )


def _ambiguity_lines(context_package: ContextPackage) -> tuple[str, ...]:
    """
    What the model must be told when a governed question had more than
    one governed answer.

    Stated in the prompt rather than left to the ordering: an ordered
    list reads as a ranked one, and the first line of a ranked list
    reads as the answer. Ambiguity that survives retrieval and Context
    Assembly must survive the prompt too, or the whole chain hid it at
    the last step.
    """

    ambiguous = tuple(
        query
        for query in context_package.retrieval_summary.queries
        if query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
    )

    if not ambiguous:
        return ()

    lines = [
        "AMBIGUOUS: the following subjects matched more than one "
        "governed object. They are distinct governed identities and were "
        "not merged. Do not present one of them as the answer.",
    ]
    lines.extend(
        f"  - '{query.normalized_query}' matched "
        f"{query.matched_before_limit} governed objects"
        if query.normalized_query
        else (
            f"  - a {query.query_type.value} query matched "
            f"{query.matched_before_limit} governed objects"
        )
        for query in ambiguous
    )

    return tuple(lines)


def describe_item(item: ContextItem) -> str:
    """
    One governed context item, as one prompt line.

    **No score.** The legacy description ended in ``(score 100.0)``, a
    number the model could only read as confidence. What replaces it is
    the governed match strategy - a statement about *how* the item was
    found, in a closed vocabulary - and the statement key that
    authorises it, so a line in a prompt can be traced to a review
    without leaving the prompt.

    Nothing is formatted, converted or rounded: a governed label and its
    unit are reproduced exactly as the pipeline recorded them, because
    an engineering value that the prompt reshaped would be a value
    nobody reviewed.
    """

    result = item.result
    strategy = result.match.strategy.value
    statement = result.provenance.statement_key

    if item.kind is GovernedResultKind.RELATIONSHIP:
        relationship = result.relationship
        return (
            f"RELATIONSHIP {relationship.subject.label} "
            f"{relationship.kind.value} {relationship.object.label} "
            f"[edge {relationship.edge_id}] "
            f"(matched by {strategy}; statement {statement})"
        )

    node = result.node

    if item.kind is GovernedResultKind.QUANTITY and (
        result.relationship is not None
    ):
        relationship = result.relationship
        return (
            f"QUANTITY {relationship.subject.label} "
            f"{relationship.kind.value} {node.label} "
            f"[node {node.node_id}] "
            f"(matched by {strategy}; statement {statement})"
        )

    kind = item.kind.value.upper()

    return (
        f"{kind} {node.label} [node {node.node_id}] "
        f"(matched by {strategy}; statement {statement})"
    )


#: What each deterministic outcome means, stated for the model in words
#: it cannot misread as a judgement somebody made.
#:
#: `INCONSISTENT` deliberately does **not** say a document is wrong or
#: that anything was rejected. The platform knows only that two approved
#: statements cannot both describe the same thing; which one is right is
#: an engineering question nobody has answered yet.
_OUTCOME_MEANING: dict[ReasoningOutcome, str] = {
    ReasoningOutcome.CONSISTENT: (
        "The governed values examined agree with each other."
    ),
    ReasoningOutcome.INCONSISTENT: (
        "The governed values examined CONFLICT. Two or more approved "
        "statements cannot both be describing the same thing. This does "
        "not say which is correct, and it does not say any document is "
        "wrong - nobody has reviewed the conflict."
    ),
    ReasoningOutcome.INSUFFICIENT_KNOWLEDGE: (
        "There was not enough governed knowledge to reach a conclusion. "
        "This is NOT the same as agreement: nothing was found to compare."
    ),
    ReasoningOutcome.AMBIGUOUS: (
        "The subject named more than one governed asset, so the question "
        "was never about a single piece of equipment. It was not "
        "answered, and no candidate was chosen."
    ),
}


#: What each structural outcome means, in words the model may repeat.
#:
#: The `INSUFFICIENT_KNOWLEDGE` wording is the load-bearing one. A model
#: told only "insufficient" will write "they are not in the same place",
#: because that is what the word suggests in ordinary English. It is told
#: explicitly that the finding is *not* a finding of separation, because
#: the governed graph cannot establish separation at all.
_STRUCTURAL_OUTCOME_MEANING: dict[StructuralReasoningOutcome, str] = {
    StructuralReasoningOutcome.ESTABLISHED: (
        "Governed knowledge places both assets in the SAME governed "
        "structural location. This says they share a location context "
        "and NOTHING else: it does not say they are connected, that "
        "current can flow between them, that one feeds or protects the "
        "other, that they are adjacent, or what kind of place the "
        "location is."
    ),
    StructuralReasoningOutcome.INSUFFICIENT_KNOWLEDGE: (
        "Governed knowledge does not establish that the two assets share "
        "a structural location. This is NOT a finding that they are in "
        "different places: the governed graph records only what "
        "documents state and engineers have approved, and a shared "
        "location may simply never have been recorded. Do not report "
        "them as separate."
    ),
    StructuralReasoningOutcome.AMBIGUOUS: (
        "The question resolved to more than one possibility and was "
        "therefore never a single question. No candidate was chosen."
    ),
}


def build_derived_reasoning(
    reasoning: ReasoningResult | None,
) -> PromptSection:
    """
    The deterministic conclusion, presented as **derived**.

    Every line here says so: the heading, the rule identity, and the
    explicit statement that this is not a reviewed engineering
    statement. A conclusion the model mistook for governed knowledge
    would be an inference laundered into a fact, which is the failure
    AF-REASON-001 exists to prevent.

    Empty and disabled when no rule ran or none examined any governed
    knowledge - a reasoning block reporting that it found nothing would
    add noise to every prompt and information to none.
    """

    if reasoning is None:
        return section(PromptSectionType.DERIVED_REASONING, ())

    if isinstance(reasoning.outcome, StructuralReasoningOutcome):
        return _build_structural_reasoning(reasoning)

    if (
        reasoning.outcome is ReasoningOutcome.INSUFFICIENT_KNOWLEDGE
        and reasoning.diagnostics.code
        in (
            ReasoningDiagnosticCode.NO_SUBJECT,
            ReasoningDiagnosticCode.NO_REQUIRED_QUANTITY,
        )
    ):
        return section(PromptSectionType.DERIVED_REASONING, ())

    content = [
        "The following is a DERIVED CONCLUSION produced by a "
        "deterministic engineering rule. It is NOT a reviewed "
        "engineering statement and NOT part of the governed knowledge "
        "above.",
        f"Question: {reasoning.query.question}",
        f"Rule: {reasoning.rule.identity}",
        f"Outcome: {reasoning.outcome.value.upper()}",
        f"Meaning: {_OUTCOME_MEANING[reasoning.outcome]}",
        f"Basis: {reasoning.diagnostics.code.value}",
    ]

    content.extend(
        f"Contributing governed value: {contributor.label} "
        f"[node {contributor.node_id}] "
        f"(statement {contributor.statement_key}, "
        f"review {contributor.review_id})"
        for contributor in reasoning.contributors
    )

    return section(PromptSectionType.DERIVED_REASONING, tuple(content))


def _build_structural_reasoning(
    reasoning: ReasoningResult,
) -> PromptSection:
    """
    A structural conclusion, presented as **derived**.

    The model is never asked whether the two assets share a location.
    That question was answered exactly, upstream, by a versioned rule;
    this section reports the answer and the governed path it rests on, so
    the model's job is to communicate a conclusion rather than to reach
    one.

    The derived relationship is named in full - ``shares structural
    location with`` - and never shortened to anything a reader could take
    for connectivity.
    """

    assessment = reasoning.structural

    content = [
        "The following is a DERIVED CONCLUSION produced by a "
        "deterministic engineering rule. It is NOT a reviewed "
        "engineering statement and NOT part of the governed knowledge "
        "above.",
        f"Question: {reasoning.query.question}",
        f"Rule: {reasoning.rule.identity}",
        f"Outcome: {reasoning.outcome.value.upper()}",
        f"Meaning: {_STRUCTURAL_OUTCOME_MEANING[reasoning.outcome]}",
        f"Basis: {assessment.diagnostics.code.value}",
    ]

    if assessment.is_established:
        content.append(
            "Derived relationship: "
            f"{assessment.derived_relationship.value} "
            f"(shared governed structural location "
            f"'{assessment.shared_location_label}' "
            f"[node {assessment.shared_location_node_id}])"
        )

    content.extend(
        "Contributing governed relationship: "
        f"{contributor.label} "
        f"[edge {contributor.edge_id}] "
        f"(statement {contributor.statement_key}, "
        f"review {contributor.review_id})"
        for contributor in reasoning.contributors
    )

    return section(PromptSectionType.DERIVED_REASONING, tuple(content))


def _build_selected_knowledge(
    context_package: ContextPackage,
) -> PromptSection:
    content = tuple(
        describe_item(item) for item in context_package.selected_items
    )

    return section(PromptSectionType.SELECTED_KNOWLEDGE, content)


def _build_references(
    context_package: ContextPackage,
) -> tuple[PromptEvidenceReference, ...]:
    return tuple(evidence_reference(item) for item in context_package.selected_items)


def _build_evidence_references(
    references: tuple[PromptEvidenceReference, ...],
) -> PromptSection:
    content = tuple(describe_reference(reference) for reference in references)

    return section(PromptSectionType.EVIDENCE_REFERENCES, content)


def _build_constraints_section() -> PromptSection:
    content = tuple(constraint.description for constraint in CONSTRAINTS)

    return section(PromptSectionType.CONSTRAINTS, content)


def _build_formatting_rules_section(
    instructions: tuple[PromptInstruction, ...],
) -> PromptSection:
    content = tuple(instruction.description for instruction in instructions)

    return section(PromptSectionType.FORMATTING_RULES, content)


def _build_expected_output(objective: PromptObjective) -> PromptSection:
    return section(
        PromptSectionType.EXPECTED_OUTPUT,
        EXPECTED_OUTPUT_BY_OBJECTIVE[objective],
    )


def _build_warnings_section(context_package: ContextPackage) -> PromptSection:
    content = tuple(
        f"[{warning.category.value}] {warning.message}"
        for warning in context_package.warnings
    )

    return section(PromptSectionType.WARNINGS, content)


def _build_metadata_section(context_package: ContextPackage) -> PromptSection:
    metadata = context_package.metadata
    content = (
        f"Context assembled at: {metadata.assembled_at.isoformat()}",
        f"Context assembly version: {metadata.context_assembly_version}",
        "Retrieval matching policy version: "
        f"{metadata.retrieval_matching_policy_version or 'unknown'}",
        "Governed graph generation: "
        f"{metadata.graph_generation_number or 'unknown'}",
    )

    return section(PromptSectionType.METADATA, content)


def compose_sections(
    context_package: ContextPackage,
    *,
    objective: PromptObjective = PromptObjective.DIRECT_ANSWER,
    reasoning: ReasoningResult | None = None,
) -> PromptAssemblyResult:
    """
    ``objective`` selects the fixed instruction and expected-output sets
    (``composition_policy.py``) and nothing else: every other section is
    composed identically for every objective, from the same
    ``ContextPackage``, by the same functions. The default reproduces
    Milestone 15's output exactly.
    """

    instructions = INSTRUCTIONS_BY_OBJECTIVE[objective]

    system_context = _build_system_context()
    engineering_context = _build_engineering_context(context_package)
    selected_knowledge = _build_selected_knowledge(context_package)
    derived_reasoning = build_derived_reasoning(reasoning)
    references = _build_references(context_package)
    evidence_references = _build_evidence_references(references)
    constraints_section = _build_constraints_section()
    formatting_rules_section = _build_formatting_rules_section(instructions)
    expected_output = _build_expected_output(objective)
    warnings_section = _build_warnings_section(context_package)
    metadata_section = _build_metadata_section(context_package)

    # Always constructed, empty and disabled: only a comparison prompt
    # populates them, and every PromptPackage keeps the same shape.
    left_knowledge = section(PromptSectionType.LEFT_KNOWLEDGE, ())
    right_knowledge = section(PromptSectionType.RIGHT_KNOWLEDGE, ())

    sections = (
        system_context,
        engineering_context,
        selected_knowledge,
        derived_reasoning,
        left_knowledge,
        right_knowledge,
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
        instructions=instructions,
        references=references,
    )
