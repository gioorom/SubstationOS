"""
Validation for Engineering Request Classification (Milestone 22).
Proves, after classification, that an ``EngineeringIntent`` satisfies
every structural invariant this milestone requires: identity
consistency, required provenance, valid intent type, confidence
consistency with the documented policy, evidence ordering, evidence-to-
intent consistency, policy version consistency, secondary match
consistency, ambiguity rules, unsupported-request rules, metadata
completeness, and statistics consistency.

**Validation is structural.** It never validates whether the user's
engineering statement is technically correct, and never judges whether
the chosen classification is semantically "right".
"""

from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
    EngineeringIntentConfidence,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
    EngineeringIntentValidationResult,
)
from app.domain.engineering_intent.engineering_intent_policy import (
    MATERIALLY_DISTINCT_OPERATIONS,
    precedence_rank,
)


def validate_engineering_intent(
    intent: EngineeringIntent,
) -> EngineeringIntentValidationResult:
    errors: list[str] = []

    metadata = intent.metadata

    # --- Identity and provenance ---------------------------------------
    expected_id = (
        f"{metadata.conversation_id}:{metadata.turn_id}:"
        f"{metadata.classification_policy_version}"
    )
    if intent.engineering_intent_id.value != expected_id:
        errors.append(
            "engineering_intent_id is not deterministically derived from "
            "its own provenance and policy version."
        )

    if intent.project_id <= 0:
        errors.append("project_id is not positive.")
    if intent.project_id != metadata.project_id:
        errors.append("project_id is inconsistent with metadata.")

    if (
        not metadata.engineering_session_id
        or not metadata.conversation_id
        or not metadata.turn_id
    ):
        errors.append("Required classification provenance is missing.")

    # --- Metadata completeness -----------------------------------------
    if (
        not metadata.engineering_intent_version
        or not metadata.classification_policy_version
        or not metadata.package_version
        or not metadata.original_request_text
        or not metadata.normalized_request_text
        or metadata.classified_at is None
    ):
        errors.append("Metadata is incomplete.")

    # --- Version consistency --------------------------------------------
    version = intent.version
    if (
        not version.engineering_intent_version
        or not version.classification_policy_version
        or not version.package_version
    ):
        errors.append("Version fields are incomplete.")
    elif (
        version.engineering_intent_version != metadata.engineering_intent_version
        or version.classification_policy_version
        != metadata.classification_policy_version
        or version.package_version != metadata.package_version
    ):
        errors.append("Version fields are inconsistent with metadata.")

    # --- Evidence ordering and consistency -------------------------------
    evidence = intent.evidence
    for index, item in enumerate(evidence):
        if item.sequence != index:
            errors.append(
                f"Evidence at position {index} does not have the expected "
                "sequence."
            )
            break

    previous_key: tuple[int, str] | None = None
    for item in evidence:
        key = (item.token_index, item.matched_rule_id)
        if previous_key is not None and key < previous_key:
            errors.append(
                "Evidence is not ordered deterministically by "
                "(token_index, matched_rule_id)."
            )
            break
        previous_key = key

    for item in evidence:
        if not item.matched_rule_id or not item.matched_text:
            errors.append("Evidence is missing a rule id or matched text.")
            break
        if item.token_index < 0:
            errors.append("Evidence carries a negative token index.")
            break

    # --- Evidence-to-intent consistency ----------------------------------
    workflow_candidates = {
        item.candidate_intent_type
        for item in evidence
        if item.strength is not EngineeringIntentRuleStrength.DOMAIN
    }
    strong_candidates = {
        item.candidate_intent_type
        for item in evidence
        if item.strength is EngineeringIntentRuleStrength.STRONG
    }

    terminal_types = (
        EngineeringIntentType.UNSUPPORTED_REQUEST,
        EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
        EngineeringIntentType.AMBIGUOUS_REQUEST,
    )

    if intent.intent_type not in terminal_types:
        if intent.intent_type not in workflow_candidates:
            errors.append(
                "The selected intent type is not supported by any "
                "collected evidence."
            )
        else:
            higher_precedence = [
                candidate
                for candidate in workflow_candidates
                if precedence_rank(candidate) < precedence_rank(intent.intent_type)
            ]
            if higher_precedence:
                errors.append(
                    "A higher-precedence candidate has evidence but was "
                    "not selected."
                )

    # --- Unsupported-request rules ----------------------------------------
    if intent.intent_type is EngineeringIntentType.UNSUPPORTED_REQUEST and evidence:
        errors.append(
            "UNSUPPORTED_REQUEST must carry no evidence - any evidence at "
            "all implies a more specific classification."
        )

    # --- General-engineering fallback rules --------------------------------
    if intent.intent_type is EngineeringIntentType.GENERAL_ENGINEERING_REQUEST:
        has_domain_evidence = any(
            item.strength is EngineeringIntentRuleStrength.DOMAIN
            for item in evidence
        )
        if not has_domain_evidence:
            errors.append(
                "GENERAL_ENGINEERING_REQUEST requires at least one "
                "engineering-domain signal."
            )
        if workflow_candidates:
            errors.append(
                "GENERAL_ENGINEERING_REQUEST must not be selected when a "
                "more specific workflow candidate has evidence."
            )

    # --- Ambiguity rules ---------------------------------------------------
    distinct_strong_operations = strong_candidates & MATERIALLY_DISTINCT_OPERATIONS
    if intent.intent_type is EngineeringIntentType.AMBIGUOUS_REQUEST:
        if len(distinct_strong_operations) < 2:
            errors.append(
                "AMBIGUOUS_REQUEST requires at least two materially "
                "distinct operations with strong evidence."
            )
        if len(intent.secondary_intent_types) < 2:
            errors.append(
                "AMBIGUOUS_REQUEST must report its competing candidates as "
                "secondary intent types."
            )
    elif len(distinct_strong_operations) >= 2:
        errors.append(
            "Two or more materially distinct operations have strong "
            "evidence, but the result is not AMBIGUOUS_REQUEST."
        )

    # --- Secondary match consistency ---------------------------------------
    if intent.intent_type in (
        EngineeringIntentType.UNSUPPORTED_REQUEST,
        EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
    ) and intent.secondary_intent_types:
        errors.append(
            "A terminal fallback classification must not report secondary "
            "intent types."
        )

    if len(set(intent.secondary_intent_types)) != len(
        intent.secondary_intent_types
    ):
        errors.append("Secondary intent types contain duplicates.")

    if (
        intent.intent_type is not EngineeringIntentType.AMBIGUOUS_REQUEST
        and intent.intent_type in intent.secondary_intent_types
    ):
        errors.append(
            "The primary intent type is also reported as a secondary type."
        )

    for secondary in intent.secondary_intent_types:
        if secondary not in workflow_candidates:
            errors.append(
                "A secondary intent type is not supported by any collected "
                "evidence."
            )
            break

    # --- Confidence consistency ---------------------------------------------
    if intent.intent_type in (
        EngineeringIntentType.AMBIGUOUS_REQUEST,
        EngineeringIntentType.UNSUPPORTED_REQUEST,
    ):
        if intent.confidence is not EngineeringIntentConfidence.UNRESOLVED:
            errors.append(
                "Ambiguous and unsupported classifications must carry "
                "UNRESOLVED confidence."
            )
    elif intent.intent_type is EngineeringIntentType.GENERAL_ENGINEERING_REQUEST:
        if intent.confidence is not EngineeringIntentConfidence.LOW:
            errors.append(
                "GENERAL_ENGINEERING_REQUEST must carry LOW confidence."
            )
    else:
        expected_high = (
            intent.intent_type in strong_candidates and len(strong_candidates) == 1
        )
        if expected_high and intent.confidence is not (
            EngineeringIntentConfidence.HIGH
        ):
            errors.append(
                "A single, consistent strong signal must yield HIGH "
                "confidence."
            )
        if not expected_high and intent.confidence is not (
            EngineeringIntentConfidence.MEDIUM
        ):
            errors.append(
                "A weaker or contested signal must yield MEDIUM confidence."
            )

    # --- Statistics consistency ----------------------------------------------
    statistics = intent.statistics
    if statistics.matched_rule_count != len(evidence):
        errors.append(
            "Statistics matched_rule_count is inconsistent with the "
            "collected evidence."
        )
    if statistics.evaluated_rule_count < statistics.matched_rule_count:
        errors.append(
            "Statistics evaluated_rule_count is lower than "
            "matched_rule_count."
        )
    expected_strong = sum(
        1
        for item in evidence
        if item.strength is EngineeringIntentRuleStrength.STRONG
    )
    if statistics.strong_match_count != expected_strong:
        errors.append(
            "Statistics strong_match_count is inconsistent with the "
            "collected evidence."
        )
    expected_weak = sum(
        1 for item in evidence if item.strength is EngineeringIntentRuleStrength.WEAK
    )
    if statistics.weak_match_count != expected_weak:
        errors.append(
            "Statistics weak_match_count is inconsistent with the "
            "collected evidence."
        )
    if statistics.unique_candidate_intent_count != len(workflow_candidates):
        errors.append(
            "Statistics unique_candidate_intent_count is inconsistent with "
            "the collected evidence."
        )
    if statistics.secondary_intent_count != len(intent.secondary_intent_types):
        errors.append(
            "Statistics secondary_intent_count is inconsistent with the "
            "reported secondary intent types."
        )

    return EngineeringIntentValidationResult(
        valid=not errors, errors=tuple(errors)
    )


class EngineeringIntentValidator:
    """A thin, named façade over ``validate_engineering_intent`` - kept
    for consistency with every sibling bounded context's own validator
    class."""

    @staticmethod
    def validate(
        intent: EngineeringIntent,
    ) -> EngineeringIntentValidationResult:
        return validate_engineering_intent(intent)
