"""
Domain tests for ``PromptObjective`` (Milestone 23B.2) - the minimum
addition Prompt Builder needed to support explanation-style responses.

The two guarantees that matter most here:

1. **`DIRECT_ANSWER` is byte-identical to Milestone 15's output.** The
   knowledge-query workflow's prompt did not change.
2. **Truthfulness constraints never vary by objective.** An explanation
   is held to the same "never invent an engineering fact" rule as a
   direct answer.

Pure and fast: no I/O, no database, no AI provider.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.prompt_builder.composition_policy import (
    CONSTRAINTS,
    EXPECTED_OUTPUT_BY_OBJECTIVE,
    EXPLANATION_INSTRUCTIONS,
    INSTRUCTIONS,
    INSTRUCTIONS_BY_OBJECTIVE,
    VERIFICATION_INSTRUCTIONS,
    VERIFICATION_VERDICT_TOKENS,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptObjective,
    PromptSectionType,
)
from app.domain.prompt_builder.prompt_composition import (
    PROMPT_SECTION_ORDER,
)
from app.domain.prompt_builder.prompt_validation import validate_package
from app.services import prompt_builder_service

from tests._governed_context import (
    asset_item,
    context_package,
    designation_result,
)

PROJECT_ID = 7
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _context_package(count: int = 2):
    """A governed context holding ``count`` distinct approved assets."""

    items = tuple(
        asset_item(
            f"node-87t-{index}",
            f"87T-{index}",
            statement_key=f"statement-{index}",
            project_id=PROJECT_ID,
        )
        for index in range(count)
    )

    return context_package(
        project_id=PROJECT_ID,
        results=(
            designation_result("87T", items, project_id=PROJECT_ID),
        ),
        now=NOW,
    )


def _package(objective=None, count: int = 2):
    kwargs = {} if objective is None else {"objective": objective}

    return prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID,
        context_package=_context_package(count),
        now=NOW,
        **kwargs,
    ).package


def _section(package, section_type: PromptSectionType):
    return next(
        section
        for section in package.sections
        if section.section_type is section_type
    )


# --- The default is unchanged ---------------------------------------------


def test_omitting_the_objective_defaults_to_direct_answer() -> None:
    assert _package().objective is PromptObjective.DIRECT_ANSWER


def test_the_default_package_is_identical_to_an_explicit_direct_answer() -> (
    None
):
    assert _package() == _package(PromptObjective.DIRECT_ANSWER)


def test_direct_answer_still_carries_milestone_15s_instruction_set() -> None:
    """The knowledge-query workflow's prompt did not change."""

    package = _package(PromptObjective.DIRECT_ANSWER)

    assert package.instructions == INSTRUCTIONS
    assert _section(
        package, PromptSectionType.FORMATTING_RULES
    ).content == tuple(
        instruction.description for instruction in INSTRUCTIONS
    )


def test_direct_answers_expected_output_is_unchanged() -> None:
    package = _package(PromptObjective.DIRECT_ANSWER)

    assert package.expected_output.content == (
        "Provide a clear, structured answer using only the evidence "
        "supplied above.",
        "Cite each claim by its evidence reference candidate id.",
        "If the supplied evidence does not fully answer the question, "
        "state explicitly what is missing.",
    )


# --- The explanation objective ---------------------------------------------


def test_the_explanation_objective_is_recorded_on_the_package() -> None:
    package = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert package.objective is PromptObjective.ENGINEERING_EXPLANATION


def test_the_explanation_objective_selects_its_own_instruction_set() -> None:
    package = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert package.instructions == EXPLANATION_INSTRUCTIONS
    assert package.instructions != INSTRUCTIONS


def test_the_explanation_asks_for_function_and_role() -> None:
    package = _package(PromptObjective.ENGINEERING_EXPLANATION)
    identifiers = {
        instruction.identifier for instruction in package.instructions
    }

    assert "explain_function_and_role" in identifiers


def test_the_explanation_forbids_completing_gaps_from_general_knowledge() -> (
    None
):
    """The rule this workflow specifically needs: "how does an 87T work"
    has a plausible textbook answer that owes nothing to *this*
    substation."""

    package = _package(PromptObjective.ENGINEERING_EXPLANATION)
    identifiers = {
        instruction.identifier for instruction in package.instructions
    }

    assert "describe_only_what_the_evidence_covers" in identifiers
    assert "state_which_aspects_the_evidence_does_not_cover" in identifiers


def test_the_explanation_has_its_own_expected_output() -> None:
    direct = _package(PromptObjective.DIRECT_ANSWER)
    explanation = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert explanation.expected_output.content != direct.expected_output.content
    assert explanation.expected_output.content == (
        EXPECTED_OUTPUT_BY_OBJECTIVE[PromptObjective.ENGINEERING_EXPLANATION]
    )


# --- What the objective must NOT change ------------------------------------


def test_truthfulness_constraints_never_vary_by_objective() -> None:
    """The central honesty guarantee: a longer answer is a larger
    opportunity to invent a fact, not a licence to."""

    direct = _package(PromptObjective.DIRECT_ANSWER)
    explanation = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert direct.constraints == CONSTRAINTS
    assert explanation.constraints == CONSTRAINTS
    assert _section(direct, PromptSectionType.CONSTRAINTS) == _section(
        explanation, PromptSectionType.CONSTRAINTS
    )


def test_only_the_two_objective_driven_sections_differ() -> None:
    """Every other section is composed identically, from the same
    ContextPackage, by the same functions."""

    direct = _package(PromptObjective.DIRECT_ANSWER)
    explanation = _package(PromptObjective.ENGINEERING_EXPLANATION)

    differing = {
        section.section_type
        for section, other in zip(direct.sections, explanation.sections)
        if section != other
    }

    assert differing == {
        PromptSectionType.FORMATTING_RULES,
        PromptSectionType.EXPECTED_OUTPUT,
    }


def test_the_evidence_offered_is_identical_for_both_objectives() -> None:
    direct = _package(PromptObjective.DIRECT_ANSWER)
    explanation = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert direct.references == explanation.references
    assert direct.retrieved_knowledge == explanation.retrieved_knowledge


def test_the_section_shape_is_identical_for_every_objective() -> None:
    for objective in PromptObjective:
        if objective is PromptObjective.ENGINEERING_COMPARISON:
            # Built from a two-sided context, not a single ContextPackage -
            # covered by the comparison tests.
            continue

        package = _package(objective)

        assert tuple(
            s.section_type for s in package.sections
        ) == PROMPT_SECTION_ORDER


def test_the_composition_policy_version_is_the_same_for_both() -> None:
    """A new objective changes nothing about packages already produced,
    so the policy version is not bumped; ``(objective, version)`` is the
    reproduction key."""

    direct = _package(PromptObjective.DIRECT_ANSWER)
    explanation = _package(PromptObjective.ENGINEERING_EXPLANATION)

    assert (
        direct.version.composition_policy_version
        == explanation.version.composition_policy_version
    )


# --- Validation -------------------------------------------------------------


@pytest.mark.parametrize("objective", list(PromptObjective))
def test_every_objective_produces_a_structurally_valid_package(
    objective: PromptObjective,
) -> None:
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID,
        context_package=_context_package(),
        objective=objective,
        now=NOW,
    )

    assert result.validation.valid is True
    assert result.validation.errors == ()


def test_instructions_that_are_not_the_objectives_declared_set_are_rejected() -> (
    None
):
    """What keeps ``PromptObjective`` an enumerable selector rather than a
    way to smuggle arbitrary instructions into a prompt."""

    package = _package(PromptObjective.ENGINEERING_EXPLANATION)
    tampered = replace(package, instructions=INSTRUCTIONS)

    result = validate_package(tampered)

    assert result.valid is False
    assert any(
        "fixed set this objective declares" in error
        for error in result.errors
    )


def test_an_expected_output_that_does_not_match_the_objective_is_rejected() -> (
    None
):
    package = _package(PromptObjective.ENGINEERING_EXPLANATION)
    tampered = replace(
        package,
        expected_output=replace(
            package.expected_output, content=("Say whatever you like.",)
        ),
    )

    result = validate_package(tampered)

    assert result.valid is False


def test_constraints_that_differ_from_the_shared_set_are_rejected() -> None:
    package = _package(PromptObjective.ENGINEERING_EXPLANATION)
    tampered = replace(package, constraints=CONSTRAINTS[:2])

    result = validate_package(tampered)

    assert result.valid is False
    assert any(
        "never vary by objective" in error for error in result.errors
    )


# --- Determinism ------------------------------------------------------------


@pytest.mark.parametrize("objective", list(PromptObjective))
def test_building_is_deterministic_for_every_objective(
    objective: PromptObjective,
) -> None:
    assert _package(objective) == _package(objective)


def test_every_objective_has_a_declared_instruction_and_output_set() -> None:
    """A new enum member without its policy entries would fail at
    composition; this catches it at the table instead."""

    for objective in PromptObjective:
        assert INSTRUCTIONS_BY_OBJECTIVE[objective]
        assert EXPECTED_OUTPUT_BY_OBJECTIVE[objective]


# --- The verification objective (Milestone 24.1) ----------------------------


def test_the_verification_objective_selects_its_own_instruction_set() -> None:
    package = _package(PromptObjective.ENGINEERING_VERIFICATION)

    assert package.objective is PromptObjective.ENGINEERING_VERIFICATION
    assert package.instructions == VERIFICATION_INSTRUCTIONS
    assert package.instructions != INSTRUCTIONS
    assert package.instructions != EXPLANATION_INSTRUCTIONS


def test_the_verification_prompt_carries_the_four_required_rules() -> None:
    """The milestone names four things the prompt must instruct: evaluate
    only retrieved evidence, distinguish absence of evidence from evidence
    of absence, report uncertainty honestly, cite supporting evidence."""

    identifiers = {
        instruction.identifier
        for instruction in _package(
            PromptObjective.ENGINEERING_VERIFICATION
        ).instructions
    }

    assert "evaluate_only_retrieved_project_evidence" in identifiers
    assert (
        "distinguish_absence_of_evidence_from_evidence_of_absence"
        in identifiers
    )
    assert "report_uncertainty_honestly" in identifiers
    assert "cite_supporting_evidence_by_item_id" in identifiers


def test_the_verification_prompt_forbids_general_knowledge() -> None:
    package = _package(PromptObjective.ENGINEERING_VERIFICATION)
    text = " ".join(
        instruction.description for instruction in package.instructions
    ) + " ".join(package.expected_output.content)

    assert "general" in text.lower()


def test_the_verification_prompt_asks_for_a_declared_verdict_line() -> None:
    """The one machine-readable part of any answer this system asks for."""

    package = _package(PromptObjective.ENGINEERING_VERIFICATION)
    identifiers = {
        instruction.identifier for instruction in package.instructions
    }

    assert "declare_the_verdict_on_the_first_line" in identifiers

    rendered = " ".join(
        instruction.description for instruction in package.instructions
    )
    for token in VERIFICATION_VERDICT_TOKENS:
        assert token in rendered


def test_every_verdict_token_appears_in_the_expected_output() -> None:
    content = " ".join(
        _package(
            PromptObjective.ENGINEERING_VERIFICATION
        ).expected_output.content
    )

    for token in VERIFICATION_VERDICT_TOKENS:
        assert token in content


def test_verification_shares_the_same_truthfulness_constraints() -> None:
    """A verification is held to the same "never invent an engineering
    fact" rule as every other objective - most of all, since its whole
    value is reporting what the evidence says."""

    verification = _package(PromptObjective.ENGINEERING_VERIFICATION)
    direct = _package(PromptObjective.DIRECT_ANSWER)

    assert verification.constraints == CONSTRAINTS
    assert verification.constraints == direct.constraints


def test_verification_differs_from_direct_answer_in_only_two_sections() -> None:
    direct = _package(PromptObjective.DIRECT_ANSWER)
    verification = _package(PromptObjective.ENGINEERING_VERIFICATION)

    differing = {
        section.section_type
        for section, other in zip(direct.sections, verification.sections)
        if section != other
    }

    assert differing == {
        PromptSectionType.FORMATTING_RULES,
        PromptSectionType.EXPECTED_OUTPUT,
    }


def test_the_verification_prompt_offers_the_same_evidence() -> None:
    direct = _package(PromptObjective.DIRECT_ANSWER)
    verification = _package(PromptObjective.ENGINEERING_VERIFICATION)

    assert direct.references == verification.references
    assert direct.retrieved_knowledge == verification.retrieved_knowledge
