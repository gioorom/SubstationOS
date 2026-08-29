"""
The fixed, documented composition policy for Prompt Builder (Milestone
15): the versioned constraint and instruction sets every
``PromptPackage`` carries, and the token-estimation convention. Every
value here is fixed and version-stamped - the same "fixed, documented
policy table" convention Structured Retrieval's ``scoring_policy.py``
and Context Builder's ``budget_policy.py`` both established. Bump the
relevant ``*_VERSION`` constant whenever a constraint, instruction, or
the token-estimation formula changes, so ``PromptMetadata``/
``PromptVersion`` can record which policy produced a given
``PromptPackage``.

Since Milestone 23B.2 the instruction and expected-output sets are
selected by ``PromptObjective``. ``COMPOSITION_POLICY_VERSION`` stays
``"1.0"`` deliberately: the ``DIRECT_ANSWER`` sets are byte-identical to
what this policy always produced, so a package stamped ``1.0`` is still
exactly reproducible. The full reproduction key is
``(objective, composition_policy_version)``, and ``PromptPackage``
records both. Bump the version when an existing objective's own
constraints, instructions, expected output, or the token-estimation
formula change - **not** when a new objective is added, which changes
nothing about the packages already produced.
"""

from __future__ import annotations

from app.domain.prompt_builder.prompt_builder_models import (
    PromptConstraint,
    PromptInstruction,
    PromptObjective,
)

PROMPT_BUILDER_VERSION = "1.0"
COMPOSITION_POLICY_VERSION = "1.0"
PROMPT_PACKAGE_VERSION = "1.0"

# Fixed, always-present behavioral guardrails - never derived from
# ContextPackage content, never conditional on it, and deliberately
# **identical for every PromptObjective**: an explanation is held to the
# same "never invent an engineering fact" rule as a direct answer,
# because a longer answer is a larger opportunity to invent one, not a
# licence to. Governs truthfulness, never formatting (see the
# per-objective instruction sets below for formatting).
CONSTRAINTS: tuple[PromptConstraint, ...] = (
    PromptConstraint(
        identifier="use_only_supplied_evidence",
        description=(
            "Use only the evidence explicitly supplied in this context. "
            "Do not use any other source of knowledge."
        ),
    ),
    PromptConstraint(
        identifier="do_not_invent_facts",
        description=(
            "Never invent, assume, or infer an engineering fact that is "
            "not present in the supplied evidence."
        ),
    ),
    PromptConstraint(
        identifier="report_uncertainty",
        description=(
            "When the supplied evidence is incomplete or partial, state "
            "that explicitly rather than filling the gap with a guess."
        ),
    ),
    PromptConstraint(
        identifier="preserve_engineering_terminology",
        description=(
            "Preserve the exact engineering terminology, identifiers, "
            "and units used in the supplied evidence."
        ),
    ),
    PromptConstraint(
        identifier="cite_supporting_evidence",
        description=(
            "Every claim must be traceable to one or more of the "
            "supplied evidence references."
        ),
    ),
)

# Fixed formatting/structural instructions for how the expected output
# should be produced - distinct from CONSTRAINTS, which governs
# truthfulness, not formatting. This is the DIRECT_ANSWER set, unchanged
# since Milestone 15; `INSTRUCTIONS` is kept as its name so a package
# built without naming an objective is byte-identical to one built
# before Milestone 23B.2.
INSTRUCTIONS: tuple[PromptInstruction, ...] = (
    PromptInstruction(
        identifier="structure_the_answer_with_clear_sections",
        description="Structure the answer with clear, labeled sections.",
    ),
    PromptInstruction(
        identifier="reference_evidence_by_item_id",
        description=(
            "When citing evidence, reference it by its governed item "
            "identifier, exactly as supplied."
        ),
    ),
    PromptInstruction(
        identifier="state_explicitly_when_no_supporting_evidence_exists",
        description=(
            "If no supplied evidence supports a requested answer, state "
            "that explicitly instead of answering anyway."
        ),
    ),
)

# The ENGINEERING_EXPLANATION set (Milestone 23B.2). It asks for the
# *function and role* of the retrieved equipment to be set out for an
# engineer, and adds the two rules an explanation specifically needs:
# say what the evidence does not cover, and do not fill a gap in a
# functional description with general electrical-engineering knowledge.
# That second rule matters more here than anywhere else in the system:
# "how does an 87T work" has a plausible textbook answer that owes
# nothing to *this* substation, and a plausible answer about the wrong
# installation is worse than an admitted gap.
EXPLANATION_INSTRUCTIONS: tuple[PromptInstruction, ...] = (
    PromptInstruction(
        identifier="explain_function_and_role",
        description=(
            "Explain the function and role of the equipment described by "
            "the supplied evidence, and how the supplied elements relate "
            "to one another."
        ),
    ),
    PromptInstruction(
        identifier="structure_the_answer_with_clear_sections",
        description="Structure the answer with clear, labeled sections.",
    ),
    PromptInstruction(
        identifier="reference_evidence_by_item_id",
        description=(
            "When citing evidence, reference it by its governed item "
            "identifier, exactly as supplied."
        ),
    ),
    PromptInstruction(
        identifier="describe_only_what_the_evidence_covers",
        description=(
            "Describe only the behaviour the supplied evidence covers. "
            "Do not complete a functional description with general "
            "electrical engineering knowledge about equipment of this "
            "type - a plausible answer about a different installation is "
            "worse than an admitted gap."
        ),
    ),
    PromptInstruction(
        identifier="state_which_aspects_the_evidence_does_not_cover",
        description=(
            "State explicitly which aspects of the requested explanation "
            "the supplied evidence does not cover."
        ),
    ),
)

# The closed verdict vocabulary a verification answer must open with, and
# the **only** part of any answer this system reads as a machine-readable
# token rather than as prose.
#
# It exists because a verification whose result a system cannot read is a
# verification nobody can act on - but it is deliberately a *declared
# protocol*, not prose interpretation: Engineering Response matches the
# first line against these four literals exactly, and reports no verdict
# at all when it matches none. Nothing is ever inferred from the
# surrounding text.
#
# Prompt Builder owns this vocabulary because Prompt Builder is what asks
# for it; Engineering Response imports it rather than restating it, so the
# question asked and the answer read can never drift apart.
VERIFICATION_VERDICT_TOKENS: tuple[str, ...] = (
    "SUPPORTED",
    "NOT_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
)

_VERDICT_LIST = ", ".join(VERIFICATION_VERDICT_TOKENS)

# The ENGINEERING_VERIFICATION set (Milestone 24.1) - the first objective
# that asks the model to *evaluate* rather than present.
#
# The four rules the milestone requires are all here, and the second is
# the one that makes verification meaningfully different from every other
# objective: **absence of evidence is not evidence of absence.** "The
# project's evidence does not show a differential protection on T1" and
# "T1 has no differential protection" are different statements, and in
# this domain confusing them is how a real installation gets signed off
# on a gap nobody looked for. The instruction set forces that distinction
# rather than hoping for it.
VERIFICATION_INSTRUCTIONS: tuple[PromptInstruction, ...] = (
    PromptInstruction(
        identifier="declare_the_verdict_on_the_first_line",
        description=(
            "Begin the answer with exactly one of these words on its own "
            f"first line, and nothing else on that line: {_VERDICT_LIST}."
        ),
    ),
    PromptInstruction(
        identifier="evaluate_only_retrieved_project_evidence",
        description=(
            "Evaluate the statement only against the project evidence "
            "supplied above. Never judge it using general electrical "
            "engineering knowledge about equipment of this type."
        ),
    ),
    PromptInstruction(
        identifier="distinguish_absence_of_evidence_from_evidence_of_absence",
        description=(
            "Distinguish absence of evidence from evidence of absence. "
            "Answer NOT_SUPPORTED only when the supplied evidence "
            "positively contradicts the statement; answer "
            "INSUFFICIENT_EVIDENCE when the evidence simply does not "
            "cover it."
        ),
    ),
    PromptInstruction(
        identifier="report_conflicting_evidence_rather_than_choosing",
        description=(
            "Answer CONFLICTING_EVIDENCE when the supplied evidence both "
            "supports and contradicts the statement, and say which "
            "evidence does which - never silently pick a side."
        ),
    ),
    PromptInstruction(
        identifier="report_uncertainty_honestly",
        description=(
            "State plainly how far the supplied evidence settles the "
            "question, including what would be needed to settle it fully."
        ),
    ),
    PromptInstruction(
        identifier="cite_supporting_evidence_by_item_id",
        description=(
            "Cite the evidence behind the verdict by its governed item "
            "identifier, exactly as supplied."
        ),
    ),
)

# The closed outcome vocabulary a comparison answer must open with -
# the same declared-protocol device the verdict vocabulary above uses,
# and read the same way (exact match on the first line, no verdict at all
# when it matches none).
#
# Deliberately **not** "same" versus "different": a real comparison of
# two montanti almost always contains both changed and unchanged aspects,
# so a top-level same/different verdict would force a false choice. The
# three values answer a different and answerable question - *could* the
# two sides be compared on this evidence at all?
COMPARISON_OUTCOME_TOKENS: tuple[str, ...] = (
    "COMPARABLE",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
)

_COMPARISON_OUTCOME_LIST = ", ".join(COMPARISON_OUTCOME_TOKENS)

# The ENGINEERING_COMPARISON set (Milestone 24.2). Two rules here carry
# most of the weight:
#
# `preserve_left_and_right_direction` - "T1 has a differential protection
# that T2 lacks" and "T2 has one that T1 lacks" are opposite engineering
# findings. A comparison answered backwards is worse than one not
# answered, so direction is instructed explicitly rather than assumed
# from the order evidence happens to appear in.
#
# `never_report_missing_evidence_as_a_difference` - if the right side's
# evidence simply does not mention a protection, that is not a removal.
# Absence of evidence is not evidence of absence, and a "removed
# protection" that was only ever un-indexed is exactly the kind of
# confident wrong answer this domain cannot afford.
COMPARISON_INSTRUCTIONS: tuple[PromptInstruction, ...] = (
    PromptInstruction(
        identifier="declare_the_comparison_outcome_on_the_first_line",
        description=(
            "Begin the answer with exactly one of these words on its own "
            "first line, and nothing else on that line: "
            f"{_COMPARISON_OUTCOME_LIST}."
        ),
    ),
    PromptInstruction(
        identifier="compare_only_the_two_supplied_evidence_groups",
        description=(
            "Compare only the LEFT and RIGHT evidence groups supplied "
            "above. Never compare either side against general knowledge "
            "of how equipment of this type is usually configured."
        ),
    ),
    PromptInstruction(
        identifier="preserve_left_and_right_direction",
        description=(
            "Preserve direction. State every finding as a change from "
            "LEFT to RIGHT, and never report it the other way round: "
            "'present on LEFT, absent from RIGHT' and its reverse are "
            "opposite engineering findings."
        ),
    ),
    PromptInstruction(
        identifier="separate_added_removed_modified_and_unchanged",
        description=(
            "Organize the findings under the headings ADDED (present on "
            "RIGHT only), REMOVED (present on LEFT only), MODIFIED "
            "(present on both with differing detail) and UNCHANGED "
            "(present on both and equivalent). A comparison may "
            "legitimately contain all four."
        ),
    ),
    PromptInstruction(
        identifier="never_report_missing_evidence_as_a_difference",
        description=(
            "Never report an absence of evidence as a difference. If one "
            "side's evidence does not mention something, say the evidence "
            "does not cover it - do not record it as ADDED or REMOVED."
        ),
    ),
    PromptInstruction(
        identifier="state_when_the_evidence_cannot_settle_the_comparison",
        description=(
            "Answer INSUFFICIENT_EVIDENCE when one or both sides carry too "
            "little evidence to compare, and say which side is lacking."
        ),
    ),
    PromptInstruction(
        identifier="cite_supporting_evidence_for_each_finding",
        description=(
            "Cite the evidence behind each material finding by its "
            "candidate identifier, exactly as supplied, and say which "
            "side it came from."
        ),
    ),
)

INSTRUCTIONS_BY_OBJECTIVE: dict[
    PromptObjective, tuple[PromptInstruction, ...]
] = {
    PromptObjective.DIRECT_ANSWER: INSTRUCTIONS,
    PromptObjective.ENGINEERING_EXPLANATION: EXPLANATION_INSTRUCTIONS,
    PromptObjective.ENGINEERING_VERIFICATION: VERIFICATION_INSTRUCTIONS,
    PromptObjective.ENGINEERING_COMPARISON: COMPARISON_INSTRUCTIONS,
}

# The EXPECTED_OUTPUT section's lines, per objective. Same shape, same
# fixed-position section - only what is asked for differs.
EXPECTED_OUTPUT_BY_OBJECTIVE: dict[PromptObjective, tuple[str, ...]] = {
    PromptObjective.DIRECT_ANSWER: (
        "Provide a clear, structured answer using only the evidence "
        "supplied above.",
        "Cite each claim by its evidence reference candidate id.",
        "If the supplied evidence does not fully answer the question, "
        "state explicitly what is missing.",
    ),
    PromptObjective.ENGINEERING_EXPLANATION: (
        "Explain, for a substation engineer, what the equipment described "
        "by the evidence above does and how its parts relate.",
        "Ground every statement in the supplied evidence and cite it by "
        "its evidence reference candidate id.",
        "Do not describe behaviour the supplied evidence does not cover, "
        "even where the equipment type makes it predictable.",
        "State explicitly which aspects of the requested explanation the "
        "supplied evidence does not cover.",
    ),
    PromptObjective.ENGINEERING_VERIFICATION: (
        "Decide whether the project evidence above supports the statement "
        "in the request. Do not explain the equipment; evaluate the "
        "statement.",
        f"First line: exactly one of {_VERDICT_LIST}, and nothing else.",
        "Then state, in a few lines, which supplied evidence led to that "
        "verdict, citing each by its evidence reference candidate id.",
        "Answer NOT_SUPPORTED only where the evidence positively "
        "contradicts the statement. Where the evidence simply does not "
        "cover it, answer INSUFFICIENT_EVIDENCE - absence of evidence is "
        "not evidence of absence.",
        "Never decide the verdict from general knowledge about this type "
        "of equipment. If the supplied evidence does not settle the "
        "question, say so and say what would settle it.",
    ),
    PromptObjective.ENGINEERING_COMPARISON: (
        "Compare the LEFT and RIGHT evidence groups above. Do not describe "
        "either side on its own; report how RIGHT differs from LEFT.",
        f"First line: exactly one of {_COMPARISON_OUTCOME_LIST}, and "
        "nothing else.",
        "Then group the findings under ADDED, REMOVED, MODIFIED and "
        "UNCHANGED, citing the evidence for each by its candidate "
        "identifier and naming the side it came from.",
        "State every finding as a change from LEFT to RIGHT. Reporting a "
        "difference in the wrong direction is an error, not a wording "
        "choice.",
        "Where one side's evidence does not cover something, say so - "
        "never record it as ADDED or REMOVED. Absence of evidence is not "
        "evidence of absence.",
        "Never compare either side against general knowledge of how this "
        "type of equipment is usually configured.",
    ),
}

# A documented, deliberately approximate, provider-independent token
# estimate - never a real tokenizer (every real tokenizer is
# provider-specific, e.g. tiktoken for OpenAI, which Prompt Builder must
# not depend on). Characters-per-token is a widely used rough English
# text approximation; treated as part of the composition policy - a
# change to this formula bumps COMPOSITION_POLICY_VERSION above, the
# same as a changed constraint or instruction would.
CHARACTERS_PER_ESTIMATED_TOKEN = 4
