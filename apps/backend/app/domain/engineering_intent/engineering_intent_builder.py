"""
Constructs the immutable ``EngineeringIntent`` aggregate from
already-resolved deterministic classification data (Milestone 22).

**This module never duplicates classification logic** - the classifier
(``engineering_intent_classifier.py``) decides the intent type and
secondary types; this builder only turns rule matches into ordered
evidence, derives confidence from the documented policy, computes
statistics, stamps metadata/version, derives the deterministic
identity, and validates the result.
"""

from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
    EngineeringIntentClassificationInput,
    EngineeringIntentClassificationResult,
    EngineeringIntentEvidence,
    EngineeringIntentEvidenceType,
    EngineeringIntentId,
    EngineeringIntentMetadata,
    EngineeringIntentRuleMatch,
    EngineeringIntentRuleStrength,
    EngineeringIntentStatistics,
    EngineeringIntentType,
    EngineeringIntentVersion,
)
from app.domain.engineering_intent.engineering_intent_policy import (
    CLASSIFICATION_POLICY_VERSION,
    ENGINEERING_INTENT_PACKAGE_VERSION,
    ENGINEERING_INTENT_VERSION,
    derive_confidence,
)
from app.domain.engineering_intent.engineering_intent_validation import (
    validate_engineering_intent,
)

# Stable, machine-readable description codes - never free-text prose,
# so a consumer can present its own localized explanation of why a
# classification was selected.
_DESCRIPTION_CODE_BY_STRENGTH: dict[EngineeringIntentRuleStrength, str] = {
    EngineeringIntentRuleStrength.STRONG: "strong_workflow_signal",
    EngineeringIntentRuleStrength.WEAK: "supporting_signal",
    EngineeringIntentRuleStrength.DOMAIN: "engineering_domain_signal",
}


def derive_engineering_intent_id(
    *, conversation_id: str, turn_id: str, policy_version: str
) -> EngineeringIntentId:
    """Deterministic identity from stable classification provenance -
    never random. Reclassifying identical input under the same policy
    version yields the same id; a changed policy version deliberately
    yields a different one."""

    return EngineeringIntentId(
        value=f"{conversation_id}:{turn_id}:{policy_version}"
    )


def _build_evidence(
    matches: tuple[EngineeringIntentRuleMatch, ...],
) -> tuple[EngineeringIntentEvidence, ...]:
    """One evidence entry per rule match, preserving the matches' own
    deterministic ``(token_index, rule_id)`` ordering and stamping a
    contiguous ``sequence`` for stable presentation."""

    return tuple(
        EngineeringIntentEvidence(
            evidence_type=match.evidence_type,
            matched_rule_id=match.rule_id,
            matched_text=match.matched_text,
            token_index=match.token_index,
            candidate_intent_type=match.candidate_intent_type,
            strength=match.strength,
            description_code=_DESCRIPTION_CODE_BY_STRENGTH[match.strength],
            sequence=sequence,
        )
        for sequence, match in enumerate(matches)
    )


def _build_statistics(
    matches: tuple[EngineeringIntentRuleMatch, ...],
    secondary_intent_types: tuple[EngineeringIntentType, ...],
    evaluated_rule_count: int,
) -> EngineeringIntentStatistics:
    strong_count = sum(
        1
        for match in matches
        if match.strength is EngineeringIntentRuleStrength.STRONG
    )
    weak_count = sum(
        1
        for match in matches
        if match.strength is EngineeringIntentRuleStrength.WEAK
    )
    unique_candidates = {
        match.candidate_intent_type
        for match in matches
        if match.strength is not EngineeringIntentRuleStrength.DOMAIN
    }

    return EngineeringIntentStatistics(
        evaluated_rule_count=evaluated_rule_count,
        matched_rule_count=len(matches),
        strong_match_count=strong_count,
        weak_match_count=weak_count,
        unique_candidate_intent_count=len(unique_candidates),
        secondary_intent_count=len(secondary_intent_types),
    )


def build_engineering_intent(
    *,
    input_: EngineeringIntentClassificationInput,
    normalized_text: str,
    matches: tuple[EngineeringIntentRuleMatch, ...],
    intent_type: EngineeringIntentType,
    secondary_intent_types: tuple[EngineeringIntentType, ...],
    evaluated_rule_count: int,
) -> EngineeringIntentClassificationResult:
    evidence = _build_evidence(matches)
    confidence = derive_confidence(intent_type, matches)
    statistics = _build_statistics(
        matches, secondary_intent_types, evaluated_rule_count
    )

    metadata = EngineeringIntentMetadata(
        engineering_intent_version=ENGINEERING_INTENT_VERSION,
        classification_policy_version=CLASSIFICATION_POLICY_VERSION,
        project_id=input_.project_id,
        engineering_session_id=input_.engineering_session_id,
        conversation_id=input_.conversation_id,
        turn_id=input_.turn_id,
        original_request_text=input_.request_text,
        normalized_request_text=normalized_text,
        classified_at=input_.classified_at,
        package_version=ENGINEERING_INTENT_PACKAGE_VERSION,
    )
    version = EngineeringIntentVersion(
        engineering_intent_version=ENGINEERING_INTENT_VERSION,
        classification_policy_version=CLASSIFICATION_POLICY_VERSION,
        package_version=ENGINEERING_INTENT_PACKAGE_VERSION,
    )

    intent = EngineeringIntent(
        engineering_intent_id=derive_engineering_intent_id(
            conversation_id=input_.conversation_id,
            turn_id=input_.turn_id,
            policy_version=CLASSIFICATION_POLICY_VERSION,
        ),
        project_id=input_.project_id,
        intent_type=intent_type,
        confidence=confidence,
        evidence=evidence,
        secondary_intent_types=secondary_intent_types,
        metadata=metadata,
        statistics=statistics,
        version=version,
    )

    validation = validate_engineering_intent(intent)

    return EngineeringIntentClassificationResult(
        project_id=input_.project_id, intent=intent, validation=validation
    )


class EngineeringIntentBuilder:
    """A thin, named façade over ``build_engineering_intent`` - kept for
    consistency with every sibling bounded context's own builder
    class."""

    @staticmethod
    def build(
        *,
        input_: EngineeringIntentClassificationInput,
        normalized_text: str,
        matches: tuple[EngineeringIntentRuleMatch, ...],
        intent_type: EngineeringIntentType,
        secondary_intent_types: tuple[EngineeringIntentType, ...],
        evaluated_rule_count: int,
    ) -> EngineeringIntentClassificationResult:
        return build_engineering_intent(
            input_=input_,
            normalized_text=normalized_text,
            matches=matches,
            intent_type=intent_type,
            secondary_intent_types=secondary_intent_types,
            evaluated_rule_count=evaluated_rule_count,
        )
