from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
    EngineeringIntentConfidence,
    EngineeringIntentEvidence,
    EngineeringIntentEvidenceType,
    EngineeringIntentId,
    EngineeringIntentMetadata,
    EngineeringIntentRuleStrength,
    EngineeringIntentStatistics,
    EngineeringIntentType,
    EngineeringIntentVersion,
)
from app.domain.engineering_intent.engineering_intent_validation import (
    EngineeringIntentValidator,
    validate_engineering_intent,
)

NOW = datetime(2026, 1, 1, 6, 0, 0)


def _evidence(
    *,
    rule_id: str = "comparison.verb",
    matched_text: str = "confronta",
    token_index: int = 0,
    candidate: EngineeringIntentType = (
        EngineeringIntentType.ENGINEERING_COMPARISON
    ),
    strength: EngineeringIntentRuleStrength = EngineeringIntentRuleStrength.STRONG,
    sequence: int = 0,
) -> EngineeringIntentEvidence:
    description_codes = {
        EngineeringIntentRuleStrength.STRONG: "strong_workflow_signal",
        EngineeringIntentRuleStrength.WEAK: "supporting_signal",
        EngineeringIntentRuleStrength.DOMAIN: "engineering_domain_signal",
    }
    evidence_types = {
        EngineeringIntentRuleStrength.DOMAIN: (
            EngineeringIntentEvidenceType.DOMAIN_VOCABULARY_MATCH
        ),
    }
    return EngineeringIntentEvidence(
        evidence_type=evidence_types.get(
            strength, EngineeringIntentEvidenceType.TOKEN_MATCH
        ),
        matched_rule_id=rule_id,
        matched_text=matched_text,
        token_index=token_index,
        candidate_intent_type=candidate,
        strength=strength,
        description_code=description_codes[strength],
        sequence=sequence,
    )


def _intent(**overrides) -> EngineeringIntent:
    evidence = overrides.pop("evidence", (_evidence(),))
    secondary = overrides.pop("secondary_intent_types", ())
    intent_type = overrides.pop(
        "intent_type", EngineeringIntentType.ENGINEERING_COMPARISON
    )
    confidence = overrides.pop("confidence", EngineeringIntentConfidence.HIGH)

    workflow_candidates = {
        item.candidate_intent_type
        for item in evidence
        if item.strength is not EngineeringIntentRuleStrength.DOMAIN
    }

    defaults = dict(
        engineering_intent_id=EngineeringIntentId(value="conv-1:turn-1:1.0"),
        project_id=1,
        intent_type=intent_type,
        confidence=confidence,
        evidence=evidence,
        secondary_intent_types=secondary,
        metadata=EngineeringIntentMetadata(
            engineering_intent_version="1.0",
            classification_policy_version="1.0",
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            original_request_text="Confronta le revisioni",
            normalized_request_text="confronta le revisioni",
            classified_at=NOW,
            package_version="1.0",
        ),
        statistics=EngineeringIntentStatistics(
            evaluated_rule_count=12,
            matched_rule_count=len(evidence),
            strong_match_count=sum(
                1
                for item in evidence
                if item.strength is EngineeringIntentRuleStrength.STRONG
            ),
            weak_match_count=sum(
                1
                for item in evidence
                if item.strength is EngineeringIntentRuleStrength.WEAK
            ),
            unique_candidate_intent_count=len(workflow_candidates),
            secondary_intent_count=len(secondary),
        ),
        version=EngineeringIntentVersion(
            engineering_intent_version="1.0",
            classification_policy_version="1.0",
            package_version="1.0",
        ),
    )
    defaults.update(overrides)
    return EngineeringIntent(**defaults)


def test_a_well_formed_intent_is_valid() -> None:
    result = validate_engineering_intent(_intent())

    assert result.valid is True
    assert result.errors == ()


def test_the_validator_class_delegates_to_the_same_function() -> None:
    intent = _intent()

    assert EngineeringIntentValidator.validate(intent) == (
        validate_engineering_intent(intent)
    )


def test_a_non_derived_identity_is_rejected() -> None:
    broken = replace(
        _intent(), engineering_intent_id=EngineeringIntentId(value="random-uuid")
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("deterministically derived" in e for e in result.errors)


def test_missing_provenance_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, metadata=replace(intent.metadata, turn_id="")
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("provenance" in e for e in result.errors)


def test_incomplete_metadata_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, metadata=replace(intent.metadata, normalized_request_text="")
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("Metadata is incomplete" in e for e in result.errors)


def test_version_inconsistent_with_metadata_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, version=replace(intent.version, engineering_intent_version="9.9")
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("inconsistent with metadata" in e for e in result.errors)


def test_out_of_sequence_evidence_is_rejected() -> None:
    broken = _intent(evidence=(_evidence(sequence=7),))

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("expected sequence" in e for e in result.errors)


def test_evidence_out_of_deterministic_order_is_rejected() -> None:
    evidence = (
        _evidence(rule_id="comparison.verb", token_index=5, sequence=0),
        _evidence(
            rule_id="document.noun",
            matched_text="documenti",
            token_index=1,
            candidate=EngineeringIntentType.DOCUMENT_LOOKUP,
            strength=EngineeringIntentRuleStrength.WEAK,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        secondary_intent_types=(EngineeringIntentType.DOCUMENT_LOOKUP,),
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("ordered deterministically" in e for e in result.errors)


def test_an_intent_type_with_no_supporting_evidence_is_rejected() -> None:
    broken = _intent(intent_type=EngineeringIntentType.DRAWING_REQUEST)

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("not supported by any" in e for e in result.errors)


def test_ignoring_a_higher_precedence_candidate_is_rejected() -> None:
    evidence = (
        _evidence(
            rule_id="verification.verb",
            matched_text="verifica",
            token_index=0,
            candidate=EngineeringIntentType.VERIFICATION_REQUEST,
            sequence=0,
        ),
        _evidence(
            rule_id="document.noun",
            matched_text="documento",
            token_index=1,
            candidate=EngineeringIntentType.DOCUMENT_LOOKUP,
            strength=EngineeringIntentRuleStrength.WEAK,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
        confidence=EngineeringIntentConfidence.MEDIUM,
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("higher-precedence candidate" in e for e in result.errors)


def test_unsupported_request_carrying_evidence_is_rejected() -> None:
    broken = _intent(
        intent_type=EngineeringIntentType.UNSUPPORTED_REQUEST,
        confidence=EngineeringIntentConfidence.UNRESOLVED,
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("must carry no evidence" in e for e in result.errors)


def test_general_engineering_without_a_domain_signal_is_rejected() -> None:
    broken = _intent(
        intent_type=EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
        confidence=EngineeringIntentConfidence.LOW,
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("engineering-domain signal" in e for e in result.errors)


def test_general_engineering_alongside_a_workflow_candidate_is_rejected() -> None:
    evidence = (
        _evidence(sequence=0),
        _evidence(
            rule_id="domain.vocabulary",
            matched_text="montante",
            token_index=1,
            candidate=EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
            strength=EngineeringIntentRuleStrength.DOMAIN,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        intent_type=EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
        confidence=EngineeringIntentConfidence.LOW,
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any(
        "must not be selected when a more specific" in e for e in result.errors
    )


def test_undetected_ambiguity_is_rejected() -> None:
    evidence = (
        _evidence(sequence=0),
        _evidence(
            rule_id="drawing.verb",
            matched_text="disegna",
            token_index=1,
            candidate=EngineeringIntentType.DRAWING_REQUEST,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        intent_type=EngineeringIntentType.ENGINEERING_COMPARISON,
        confidence=EngineeringIntentConfidence.MEDIUM,
        secondary_intent_types=(EngineeringIntentType.DRAWING_REQUEST,),
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("not AMBIGUOUS_REQUEST" in e for e in result.errors)


def test_ambiguity_without_competing_secondary_types_is_rejected() -> None:
    evidence = (
        _evidence(sequence=0),
        _evidence(
            rule_id="drawing.verb",
            matched_text="disegna",
            token_index=1,
            candidate=EngineeringIntentType.DRAWING_REQUEST,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        intent_type=EngineeringIntentType.AMBIGUOUS_REQUEST,
        confidence=EngineeringIntentConfidence.UNRESOLVED,
        secondary_intent_types=(),
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("competing candidates" in e for e in result.errors)


def test_duplicate_secondary_intent_types_are_rejected() -> None:
    evidence = (
        _evidence(sequence=0),
        _evidence(
            rule_id="document.noun",
            matched_text="documenti",
            token_index=1,
            candidate=EngineeringIntentType.DOCUMENT_LOOKUP,
            strength=EngineeringIntentRuleStrength.WEAK,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        secondary_intent_types=(
            EngineeringIntentType.DOCUMENT_LOOKUP,
            EngineeringIntentType.DOCUMENT_LOOKUP,
        ),
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("duplicates" in e for e in result.errors)


def test_a_secondary_type_without_evidence_is_rejected() -> None:
    broken = _intent(
        secondary_intent_types=(EngineeringIntentType.DRAWING_REQUEST,)
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any(
        "secondary intent type is not supported" in e for e in result.errors
    )


def test_wrong_confidence_for_a_strong_signal_is_rejected() -> None:
    broken = _intent(confidence=EngineeringIntentConfidence.MEDIUM)

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("HIGH confidence" in e for e in result.errors)


def test_wrong_confidence_for_ambiguity_is_rejected() -> None:
    evidence = (
        _evidence(sequence=0),
        _evidence(
            rule_id="drawing.verb",
            matched_text="disegna",
            token_index=1,
            candidate=EngineeringIntentType.DRAWING_REQUEST,
            sequence=1,
        ),
    )
    broken = _intent(
        evidence=evidence,
        intent_type=EngineeringIntentType.AMBIGUOUS_REQUEST,
        confidence=EngineeringIntentConfidence.HIGH,
        secondary_intent_types=(
            EngineeringIntentType.DRAWING_REQUEST,
            EngineeringIntentType.ENGINEERING_COMPARISON,
        ),
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("UNRESOLVED confidence" in e for e in result.errors)


def test_matched_rule_count_inconsistency_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, statistics=replace(intent.statistics, matched_rule_count=99)
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("matched_rule_count" in e for e in result.errors)


def test_strong_match_count_inconsistency_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, statistics=replace(intent.statistics, strong_match_count=99)
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("strong_match_count" in e for e in result.errors)


def test_evaluated_rule_count_below_matched_rule_count_is_rejected() -> None:
    intent = _intent()
    broken = replace(
        intent, statistics=replace(intent.statistics, evaluated_rule_count=0)
    )

    result = validate_engineering_intent(broken)

    assert result.valid is False
    assert any("evaluated_rule_count" in e for e in result.errors)
