from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_intent.engineering_intent_classifier import (
    EngineeringRequestClassifier,
    classify_engineering_request,
)
from app.domain.engineering_intent.engineering_intent_exceptions import (
    InvalidClassificationProvenanceError,
    InvalidProjectIdError,
    InvalidRequestTextError,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentConfidence,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
)
from app.domain.engineering_intent.engineering_intent_policy import (
    CLASSIFICATION_POLICY_VERSION,
)

NOW = datetime(2026, 1, 1, 6, 0, 0)


def _input(request_text: str, **overrides) -> EngineeringIntentClassificationInput:
    defaults = dict(
        project_id=1,
        engineering_session_id="sess-1",
        conversation_id="conv-1",
        turn_id="turn-1",
        request_text=request_text,
        classified_at=NOW,
    )
    defaults.update(overrides)
    return EngineeringIntentClassificationInput(**defaults)


def _classify(request_text: str, **overrides):
    return classify_engineering_request(_input(request_text, **overrides))


# --- Required representative cases (Italian) ------------------------------


@pytest.mark.parametrize(
    "request_text,expected",
    [
        (
            "Quali documenti parlano del trasformatore T1?",
            EngineeringIntentType.DOCUMENT_LOOKUP,
        ),
        (
            "Quale TA è installato sul montante T2?",
            EngineeringIntentType.KNOWLEDGE_QUERY,
        ),
        (
            "Spiegami lo schema funzionale del montante trasformatore",
            EngineeringIntentType.ENGINEERING_EXPLANATION,
        ),
        (
            "Confronta le revisioni 01 e 02 dello schema",
            EngineeringIntentType.ENGINEERING_COMPARISON,
        ),
        (
            "Disegna uno schema funzionale equivalente",
            EngineeringIntentType.DRAWING_REQUEST,
        ),
        (
            "Verifica se le protezioni del trasformatore sono coerenti",
            EngineeringIntentType.VERIFICATION_REQUEST,
        ),
        (
            "Apri la pagina con lo schema del montante T1",
            EngineeringIntentType.NAVIGATION_REQUEST,
        ),
        (
            "Analizza il montante T1",
            EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
        ),
        (
            "Raccontami una barzelletta",
            EngineeringIntentType.UNSUPPORTED_REQUEST,
        ),
        (
            "Confronta e modifica lo schema",
            EngineeringIntentType.AMBIGUOUS_REQUEST,
        ),
    ],
)
def test_required_italian_cases(
    request_text: str, expected: EngineeringIntentType
) -> None:
    result = _classify(request_text)

    assert result.intent.intent_type is expected
    assert result.validation.valid is True


# --- English coverage -------------------------------------------------------


@pytest.mark.parametrize(
    "request_text,expected",
    [
        ("Find document about the transformer", EngineeringIntentType.DOCUMENT_LOOKUP),
        (
            "Which breaker is installed on bay T2?",
            EngineeringIntentType.KNOWLEDGE_QUERY,
        ),
        (
            "Explain the functional schematic",
            EngineeringIntentType.ENGINEERING_EXPLANATION,
        ),
        ("Compare revision 01 and 02", EngineeringIntentType.ENGINEERING_COMPARISON),
        ("Generate drawing of the bay", EngineeringIntentType.DRAWING_REQUEST),
        ("Verify the transformer protections", EngineeringIntentType.VERIFICATION_REQUEST),
        ("Open the page with the schematic", EngineeringIntentType.NAVIGATION_REQUEST),
    ],
)
def test_required_english_cases(
    request_text: str, expected: EngineeringIntentType
) -> None:
    result = _classify(request_text)

    assert result.intent.intent_type is expected
    assert result.validation.valid is True


# --- Precedence -------------------------------------------------------------


def test_comparison_outranks_document_lookup() -> None:
    result = _classify("Confronta i due documenti")

    assert result.intent.intent_type is (
        EngineeringIntentType.ENGINEERING_COMPARISON
    )
    assert EngineeringIntentType.DOCUMENT_LOOKUP in (
        result.intent.secondary_intent_types
    )


def test_verification_outranks_document_lookup() -> None:
    result = _classify("Verifica lo schema del montante")

    assert result.intent.intent_type is EngineeringIntentType.VERIFICATION_REQUEST


def test_navigation_outranks_document_lookup() -> None:
    result = _classify("Apri il documento")

    assert result.intent.intent_type is EngineeringIntentType.NAVIGATION_REQUEST
    assert EngineeringIntentType.DOCUMENT_LOOKUP in (
        result.intent.secondary_intent_types
    )


def test_explanation_outranks_knowledge_query() -> None:
    result = _classify("Spiegami quale TA è installato")

    assert result.intent.intent_type is (
        EngineeringIntentType.ENGINEERING_EXPLANATION
    )
    assert EngineeringIntentType.KNOWLEDGE_QUERY in (
        result.intent.secondary_intent_types
    )


# --- Ambiguity ----------------------------------------------------------------


def test_two_materially_distinct_operations_yield_ambiguity() -> None:
    result = _classify("Disegna uno schema e poi verificalo")
    intent = result.intent

    assert intent.intent_type is EngineeringIntentType.AMBIGUOUS_REQUEST
    assert EngineeringIntentType.DRAWING_REQUEST in intent.secondary_intent_types
    assert EngineeringIntentType.VERIFICATION_REQUEST in (
        intent.secondary_intent_types
    )
    assert intent.confidence is EngineeringIntentConfidence.UNRESOLVED
    assert result.validation.valid is True


def test_a_multi_action_request_never_silently_discards_a_secondary_operation() -> (
    None
):
    result = _classify("Confronta e modifica lo schema")
    matched_rule_ids = {item.matched_rule_id for item in result.intent.evidence}

    assert "comparison.verb" in matched_rule_ids
    assert "drawing.verb" in matched_rule_ids


def test_reading_oriented_overlap_does_not_force_ambiguity() -> None:
    """DOCUMENT_LOOKUP/EXPLANATION/KNOWLEDGE_QUERY overlap constantly in
    natural phrasing - only materially distinct *operations* trigger
    ambiguity, so this stays a decisive classification."""

    result = _classify("Trova e spiegami il documento")

    assert result.intent.intent_type is not (
        EngineeringIntentType.AMBIGUOUS_REQUEST
    )


# --- Unsupported and general fallback -------------------------------------------


def test_a_clearly_non_engineering_request_is_unsupported() -> None:
    result = _classify("Raccontami una barzelletta")
    intent = result.intent

    assert intent.intent_type is EngineeringIntentType.UNSUPPORTED_REQUEST
    assert intent.evidence == ()
    assert intent.confidence is EngineeringIntentConfidence.UNRESOLVED


def test_an_unknown_sentence_is_not_engineering_merely_by_occurring_in_a_project() -> (
    None
):
    result = _classify("Ci vediamo domani mattina")

    assert result.intent.intent_type is EngineeringIntentType.UNSUPPORTED_REQUEST


def test_engineering_vocabulary_without_a_workflow_signal_is_general() -> None:
    result = _classify("Analizza il montante T1")
    intent = result.intent

    assert intent.intent_type is (
        EngineeringIntentType.GENERAL_ENGINEERING_REQUEST
    )
    assert intent.confidence is EngineeringIntentConfidence.LOW
    assert any(
        item.strength is EngineeringIntentRuleStrength.DOMAIN
        for item in intent.evidence
    )


# --- Confidence policy -----------------------------------------------------------


def test_a_single_consistent_strong_signal_yields_high_confidence() -> None:
    result = _classify("Confronta le revisioni 01 e 02")

    assert result.intent.confidence is EngineeringIntentConfidence.HIGH


def test_only_weak_signals_yield_medium_confidence() -> None:
    result = _classify("Quale valore è installato?")

    assert result.intent.intent_type is EngineeringIntentType.KNOWLEDGE_QUERY
    assert result.intent.confidence is EngineeringIntentConfidence.MEDIUM


def test_general_engineering_requests_always_carry_low_confidence() -> None:
    result = _classify("Il trasformatore")

    assert result.intent.confidence is EngineeringIntentConfidence.LOW


# --- Evidence -----------------------------------------------------------------------


def test_evidence_is_sequenced_contiguously_and_ordered() -> None:
    result = _classify("Confronta i documenti del trasformatore")
    evidence = result.intent.evidence

    assert [item.sequence for item in evidence] == list(range(len(evidence)))
    keys = [(item.token_index, item.matched_rule_id) for item in evidence]
    assert keys == sorted(keys)


def test_evidence_is_stable_and_reproducible() -> None:
    first = _classify("Verifica lo schema del montante").intent.evidence
    second = _classify("Verifica lo schema del montante").intent.evidence

    assert first == second


def test_evidence_records_the_matched_rule_and_text() -> None:
    result = _classify("Disegna uno schema")
    drawing_evidence = next(
        item
        for item in result.intent.evidence
        if item.matched_rule_id == "drawing.verb"
    )

    assert drawing_evidence.matched_text == "disegna"
    assert drawing_evidence.description_code == "strong_workflow_signal"
    assert drawing_evidence.candidate_intent_type is (
        EngineeringIntentType.DRAWING_REQUEST
    )


# --- Identity determinism ------------------------------------------------------------


def test_identity_is_derived_from_provenance_and_policy_version() -> None:
    result = _classify("Confronta le revisioni")

    assert result.intent.engineering_intent_id.value == (
        f"conv-1:turn-1:{CLASSIFICATION_POLICY_VERSION}"
    )


def test_identical_input_produces_an_identical_result() -> None:
    first = _classify("Apri la pagina con lo schema")
    second = _classify("Apri la pagina con lo schema")

    assert first.intent == second.intent
    assert first.validation == second.validation


def test_a_different_turn_produces_a_different_identity() -> None:
    first = _classify("Confronta le revisioni", turn_id="turn-1")
    second = _classify("Confronta le revisioni", turn_id="turn-2")

    assert (
        first.intent.engineering_intent_id != second.intent.engineering_intent_id
    )


# --- Metadata and statistics ------------------------------------------------------------


def test_metadata_preserves_the_original_and_normalized_request_text() -> None:
    result = _classify("  Confronta le REVISIONI!  ")
    metadata = result.intent.metadata

    assert metadata.original_request_text == "  Confronta le REVISIONI!  "
    assert metadata.normalized_request_text == "confronta le revisioni"
    assert metadata.classified_at == NOW


def test_statistics_are_derivable_from_the_evidence() -> None:
    result = _classify("Confronta i documenti del trasformatore")
    intent = result.intent
    statistics = intent.statistics

    assert statistics.matched_rule_count == len(intent.evidence)
    assert statistics.evaluated_rule_count >= statistics.matched_rule_count
    assert statistics.strong_match_count == sum(
        1
        for item in intent.evidence
        if item.strength is EngineeringIntentRuleStrength.STRONG
    )
    assert statistics.secondary_intent_count == len(intent.secondary_intent_types)


# --- Input validation ------------------------------------------------------------------


def test_a_non_positive_project_id_is_rejected() -> None:
    with pytest.raises(InvalidProjectIdError):
        _classify("Confronta", project_id=0)


def test_blank_provenance_is_rejected() -> None:
    with pytest.raises(InvalidClassificationProvenanceError):
        _classify("Confronta", conversation_id="   ")


def test_request_text_with_no_classifiable_content_is_rejected() -> None:
    with pytest.raises(InvalidRequestTextError):
        _classify("???")


def test_the_classifier_class_delegates_to_the_same_function() -> None:
    via_class = EngineeringRequestClassifier.classify(_input("Confronta"))
    via_function = classify_engineering_request(_input("Confronta"))

    assert via_class.intent == via_function.intent
