"""
Domain tests for comparison request preparation (Milestone 24.2).

Every test starts from a **real classified request**, so what is proved
is the genuine mapping an engineer's sentence undergoes.

The rules that carry the weight: exactly two operands, order preserved,
nothing inferred and nothing truncated.

Pure and fast: no I/O, no database, no provider.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.engineering_intent.engineering_intent_classifier import (
    classify_engineering_request,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.comparison_bridge import (
    derive_comparison_configuration,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RetrievalBridgeFailureCode,
)
from app.domain.retrieval_bridge.retrieval_bridge_policy import (
    COMPARISON_OPERAND_POLICY,
    REQUIRED_COMPARISON_OPERAND_COUNT,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


def _classify(text: str, *, project_id: int = 1):
    return classify_engineering_request(
        EngineeringIntentClassificationInput(
            project_id=project_id,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text=text,
            classified_at=NOW,
        )
    ).intent


def _derive(text: str, **overrides):
    return derive_comparison_configuration(
        _classify(text, **overrides), derived_at=NOW
    )


# --- Exactly two operands ---------------------------------------------------


def test_two_named_subjects_produce_two_operands() -> None:
    result = _derive("Confronta il trasformatore T1 con T2")

    assert result.resolved is True
    assert result.configuration.left.text == "T1"
    assert result.configuration.right.text == "T2"
    assert result.statistics.designation_count == 2
    assert result.statistics.required_operand_count == 2


def test_one_named_subject_is_insufficient_never_inferred() -> None:
    """The second operand is never inferred - not from the project, not
    from what usually gets compared with a T1."""

    result = _derive("Confronta il trasformatore T1")

    assert result.resolved is False
    assert result.configuration is None
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE
    )
    assert "never inferred" in result.failure.detail


def test_no_named_subject_is_insufficient() -> None:
    result = _derive("Confronta i trasformatori")

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE
    )


def test_three_named_subjects_are_conflicting_never_truncated() -> None:
    """Choosing two of three would compare a pair the request did not ask
    for."""

    result = _derive("Confronta T1 con T2 e T3")

    assert result.resolved is False
    assert result.configuration is None
    assert result.failure.code is (
        RetrievalBridgeFailureCode.CONFLICTING_EVIDENCE
    )
    assert result.statistics.designation_count == 3
    assert "never truncated" in result.failure.detail


def test_a_refusal_still_reports_every_designation_found() -> None:
    result = _derive("Confronta T1 con T2 e T3")

    assert [d.text for d in result.designations] == ["T1", "T2", "T3"]


# --- Order is preserved ------------------------------------------------------


def test_operand_order_follows_the_request() -> None:
    result = _derive("Confronta il trasformatore T1 con T2")

    assert result.configuration.left.text == "T1"
    assert result.configuration.right.text == "T2"


def test_reversing_the_request_reverses_the_operands() -> None:
    """"Compare A with B" and "compare B with A" must not become
    indistinguishable - additions, removals and every directional finding
    invert."""

    forward = _derive("Confronta il trasformatore T1 con T2")
    reverse = _derive("Confronta il trasformatore T2 con T1")

    assert forward.configuration.left.text == "T1"
    assert forward.configuration.right.text == "T2"
    assert reverse.configuration.left.text == "T2"
    assert reverse.configuration.right.text == "T1"
    assert forward.configuration != reverse.configuration


# --- Per-operand retrieval configuration -------------------------------------


def test_each_operand_gets_its_own_retrieval_configuration() -> None:
    result = _derive("Confronta il trasformatore T1 con T2")
    configuration = result.configuration

    assert configuration.left.configuration.lexical_terms == ("T1",)
    assert configuration.right.configuration.lexical_terms == ("T2",)
    assert (
        configuration.left.configuration
        != configuration.right.configuration
    )


def test_two_canonical_subjects_are_the_normal_case_not_a_conflict() -> None:
    """Unlike the single-operand path, where two canonical references are
    a conflict: here each side has its own configuration to carry one."""

    result = _derive("Confronta il cavo C-295 con il cavo C-300")

    assert result.resolved is True
    left = result.configuration.left
    right = result.configuration.right
    assert left.configuration.mode is RetrievalMode.ENTITY_LOOKUP
    assert left.configuration.canonical_entity_id == "CABLE:C-295"
    assert right.configuration.canonical_entity_id == "CABLE:C-300"
    assert result.statistics.canonical_reference_count == 2


def test_an_unresolvable_designation_becomes_that_sides_lexical_term() -> None:
    result = _derive("Confronta il montante M1 con M2")

    left = result.configuration.left
    assert left.designation.resolution is DesignationResolution.LEXICAL_TERM
    assert left.configuration.mode is RetrievalMode.LEXICAL_SEARCH
    assert left.configuration.canonical_entity_id is None


def test_both_operands_expand_the_neighborhood_by_policy() -> None:
    """What usually differs between two montanti is what each is connected
    to and protected by."""

    result = _derive("Confronta il montante M1 con M2")

    for operand in (result.configuration.left, result.configuration.right):
        assert operand.configuration.include_neighborhood is True
        assert operand.configuration.neighborhood_depth == 1


def test_operand_provenance_travels_with_the_operand() -> None:
    result = _derive("Confronta il cavo C-295 con il cavo C-300")
    designation = result.configuration.left.designation

    assert designation.text == "C-295"
    assert designation.entity_type == "CABLE"
    assert designation.token_index >= 0


def test_the_scope_records_whether_both_sides_resolved_canonically() -> None:
    canonical = _derive("Confronta il cavo C-295 con il cavo C-300")
    lexical = _derive("Confronta il montante M1 con M2")

    assert canonical.configuration.scope.both_operands_resolved_canonically
    assert not lexical.configuration.scope.both_operands_resolved_canonically
    assert canonical.configuration.scope.project_id == 1


# --- Guards ------------------------------------------------------------------


def test_a_non_comparison_intent_is_refused() -> None:
    result = _derive("Quale TA è installato sul cavo C-295?")

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING
    )


def test_an_invalid_intent_is_rejected() -> None:
    intent = _classify("Confronta il trasformatore T1 con T2")
    broken = replace(
        intent, project_id=0, metadata=replace(intent.metadata, project_id=0)
    )

    result = derive_comparison_configuration(broken, derived_at=NOW)

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INVALID_BRIDGE_INPUT
    )


# --- Determinism and policy --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Confronta il trasformatore T1 con T2",
        "Confronta il cavo C-295 con il cavo C-300",
        "Confronta T1 con T2 e T3",
        "Confronta il trasformatore T1",
    ],
)
def test_the_same_request_always_produces_the_same_result(text: str) -> None:
    assert _derive(text) == _derive(text)


def test_the_policy_requires_exactly_two_operands() -> None:
    assert REQUIRED_COMPARISON_OPERAND_COUNT == 2


def test_the_operand_policy_is_explicit_and_reviewable() -> None:
    """The mapping is table data, not a branch chain."""

    assert (
        COMPARISON_OPERAND_POLICY.intent_type
        is EngineeringIntentType.ENGINEERING_COMPARISON
    )
    assert COMPARISON_OPERAND_POLICY.allows_canonical_entity_lookup is True
    assert COMPARISON_OPERAND_POLICY.neighborhood_depth == 1


def test_the_result_records_which_policy_produced_it() -> None:
    result = _derive("Confronta il trasformatore T1 con T2")

    assert result.metadata.retrieval_bridge_version
    assert result.metadata.bridge_policy_version
    assert result.metadata.derived_at == NOW
