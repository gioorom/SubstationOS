from __future__ import annotations

import pytest

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentEvidenceType,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
)
from app.domain.engineering_intent.engineering_intent_normalization import (
    normalize_and_tokenize,
)
from app.domain.engineering_intent.engineering_intent_rules import (
    CLASSIFICATION_RULES,
    evaluate_all_rules,
    evaluate_rule,
)


def _rule(rule_id: str):
    return next(
        rule for rule in CLASSIFICATION_RULES if rule.rule_id == rule_id
    )


def _tokens(text: str):
    _normalized, tokens = normalize_and_tokenize(text)
    return tokens


# --- Individual rule evaluation ------------------------------------------


def test_every_rule_id_is_unique() -> None:
    rule_ids = [rule.rule_id for rule in CLASSIFICATION_RULES]

    assert len(rule_ids) == len(set(rule_ids))


def test_a_rule_matches_a_whole_token() -> None:
    match = evaluate_rule(_rule("comparison.verb"), _tokens("confronta i due"))

    assert match is not None
    assert match.matched_text == "confronta"
    assert match.token_index == 0
    assert match.candidate_intent_type is (
        EngineeringIntentType.ENGINEERING_COMPARISON
    )
    assert match.strength is EngineeringIntentRuleStrength.STRONG
    assert match.evidence_type is EngineeringIntentEvidenceType.TOKEN_MATCH


def test_a_rule_does_not_match_inside_an_unrelated_word() -> None:
    """The whole-token guarantee: 'aprile' must never fire the 'apri'
    navigation rule, which a naive substring search would."""

    assert evaluate_rule(_rule("navigation.verb"), _tokens("ad aprile")) is None


def test_the_vs_token_does_not_match_inside_another_word() -> None:
    assert evaluate_rule(_rule("comparison.marker"), _tokens("vsat link")) is None


def test_a_rule_matches_a_multi_token_phrase() -> None:
    match = evaluate_rule(_rule("navigation.verb"), _tokens("vai a pagina 3"))

    assert match is not None
    assert match.matched_text == "vai a"
    assert match.evidence_type is EngineeringIntentEvidenceType.PHRASE_MATCH


def test_a_rule_returns_none_when_nothing_matches() -> None:
    assert evaluate_rule(_rule("drawing.verb"), _tokens("buongiorno")) is None


def test_a_phrase_match_is_preferred_over_a_bare_token_match() -> None:
    """'find document' (phrase) is more specific than 'find' (token) -
    the phrase is reported when both are present."""

    match = evaluate_rule(_rule("document.find"), _tokens("find document x"))

    assert match is not None
    assert match.matched_text == "find document"
    assert match.evidence_type is EngineeringIntentEvidenceType.PHRASE_MATCH


def test_domain_vocabulary_matches_report_a_domain_evidence_type() -> None:
    match = evaluate_rule(_rule("domain.vocabulary"), _tokens("il montante T1"))

    assert match is not None
    assert match.strength is EngineeringIntentRuleStrength.DOMAIN
    assert match.evidence_type is (
        EngineeringIntentEvidenceType.DOMAIN_VOCABULARY_MATCH
    )


def test_the_earliest_matching_token_is_reported() -> None:
    match = evaluate_rule(
        _rule("document.noun"), _tokens("il pdf e il documento")
    )

    assert match is not None
    assert match.matched_text == "pdf"


# --- Representative per-intent rule coverage -------------------------------


@pytest.mark.parametrize(
    "rule_id,text",
    [
        ("drawing.verb", "disegna uno schema"),
        ("drawing.verb", "genera schema funzionale"),
        ("drawing.verb", "create schematic"),
        ("verification.verb", "verifica le protezioni"),
        ("verification.verb", "validate the design"),
        ("verification.condition", "sono coerenti"),
        ("comparison.verb", "confronta le revisioni"),
        ("comparison.verb", "compare revisions"),
        ("comparison.marker", "differenze tra i due"),
        ("navigation.verb", "apri la pagina"),
        ("navigation.verb", "portami alla tavola"),
        ("navigation.verb", "navigate to the page"),
        ("document.find", "trova il documento"),
        ("document.find", "where is the file"),
        ("document.noun", "quali tavole"),
        ("explanation.verb", "spiegami lo schema"),
        ("explanation.verb", "summarize the document"),
        ("knowledge.interrogative", "quale TA"),
        ("knowledge.state", "e installato"),
        ("domain.vocabulary", "il trasformatore T1"),
        ("domain.vocabulary", "the switchgear"),
    ],
)
def test_representative_signals_fire_their_own_rule(
    rule_id: str, text: str
) -> None:
    assert evaluate_rule(_rule(rule_id), _tokens(text)) is not None


# --- Aggregate evaluation ---------------------------------------------------


def test_evaluate_all_rules_orders_matches_deterministically() -> None:
    matches = evaluate_all_rules(
        _tokens("Confronta i documenti e verifica lo schema")
    )

    keys = [(match.token_index, match.rule_id) for match in matches]
    assert keys == sorted(keys)


def test_evaluate_all_rules_is_reproducible() -> None:
    tokens = _tokens("Apri la pagina con lo schema del montante T1")

    assert evaluate_all_rules(tokens) == evaluate_all_rules(tokens)


def test_evaluate_all_rules_returns_nothing_for_an_unrelated_request() -> None:
    assert evaluate_all_rules(_tokens("Raccontami una barzelletta")) == ()
