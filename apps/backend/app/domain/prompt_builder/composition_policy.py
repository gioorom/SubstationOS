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
"""

from __future__ import annotations

from app.domain.prompt_builder.prompt_builder_models import (
    PromptConstraint,
    PromptInstruction,
)

PROMPT_BUILDER_VERSION = "1.0"
COMPOSITION_POLICY_VERSION = "1.0"
PROMPT_PACKAGE_VERSION = "1.0"

# Fixed, always-present behavioral guardrails - never derived from
# ContextPackage content, never conditional on it. Governs truthfulness,
# never formatting (see INSTRUCTIONS below for formatting).
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

# Fixed, always-present formatting/structural instructions for how the
# expected output should be produced - distinct from CONSTRAINTS, which
# governs truthfulness, not formatting.
INSTRUCTIONS: tuple[PromptInstruction, ...] = (
    PromptInstruction(
        identifier="structure_the_answer_with_clear_sections",
        description="Structure the answer with clear, labeled sections.",
    ),
    PromptInstruction(
        identifier="reference_evidence_by_candidate_id",
        description=(
            "When citing evidence, reference it by its candidate "
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

# A documented, deliberately approximate, provider-independent token
# estimate - never a real tokenizer (every real tokenizer is
# provider-specific, e.g. tiktoken for OpenAI, which Prompt Builder must
# not depend on). Characters-per-token is a widely used rough English
# text approximation; treated as part of the composition policy - a
# change to this formula bumps COMPOSITION_POLICY_VERSION above, the
# same as a changed constraint or instruction would.
CHARACTERS_PER_ESTIMATED_TOKEN = 4
