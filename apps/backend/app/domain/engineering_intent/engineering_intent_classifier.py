"""
The deterministic Engineering Request Classifier (Milestone 22's
central pipeline stage):

    EngineeringIntentClassificationInput
            |
       input normalization      (engineering_intent_normalization.py)
            |
       rule evaluation          (engineering_intent_rules.py)
            |
       rule matches
            |
       precedence resolution    (engineering_intent_policy.py)
            |
       ambiguity detection      (engineering_intent_policy.py)
            |
       EngineeringIntent        (engineering_intent_builder.py)

Pure and deterministic: no persistence, no network access, no side
effects, no runtime invocation, no LLM, no embeddings. Given the same
input and the same policy version, always produces the same result -
including the same ``EngineeringIntentId``.

This module *decides* the classification; ``engineering_intent_builder.py``
*constructs* the immutable aggregate from the resolved data. The
builder never duplicates classification logic.
"""

from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_builder import (
    build_engineering_intent,
)
from app.domain.engineering_intent.engineering_intent_input_validator import (
    EngineeringIntentInputValidator,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentClassificationResult,
    EngineeringIntentRule,
    EngineeringIntentRuleMatch,
    EngineeringIntentType,
)
from app.domain.engineering_intent.engineering_intent_normalization import (
    normalize_and_tokenize,
)
from app.domain.engineering_intent.engineering_intent_policy import (
    candidate_types_by_precedence,
    is_ambiguous,
)
from app.domain.engineering_intent.engineering_intent_rules import (
    CLASSIFICATION_RULES,
    evaluate_all_rules,
)


def _resolve_intent_type(
    matches: tuple[EngineeringIntentRuleMatch, ...],
) -> tuple[EngineeringIntentType, tuple[EngineeringIntentType, ...]]:
    """
    Resolves the primary intent type and any secondary (explanatory)
    types from the rule matches:

    - No matches at all -> ``UNSUPPORTED_REQUEST``: nothing in the
      request, not even engineering vocabulary, is recognizable.
    - Only domain-vocabulary matches -> ``GENERAL_ENGINEERING_REQUEST``:
      engineering-related, but no workflow signal. (This is why an
      unknown sentence is never classified as engineering-related
      merely because it occurs inside a project - it needs an actual
      domain-vocabulary hit.)
    - Two or more materially distinct operations, each STRONG ->
      ``AMBIGUOUS_REQUEST``, with every candidate reported as secondary.
    - Otherwise -> the highest-precedence candidate, with every other
      candidate reported as secondary.
    """

    candidates = candidate_types_by_precedence(matches)

    if not candidates:
        if matches:
            # Only DOMAIN-strength matches fired.
            return EngineeringIntentType.GENERAL_ENGINEERING_REQUEST, ()
        return EngineeringIntentType.UNSUPPORTED_REQUEST, ()

    if is_ambiguous(matches):
        return EngineeringIntentType.AMBIGUOUS_REQUEST, candidates

    return candidates[0], candidates[1:]


def classify_engineering_request(
    input_: EngineeringIntentClassificationInput,
    *,
    rules: tuple[EngineeringIntentRule, ...] = CLASSIFICATION_RULES,
) -> EngineeringIntentClassificationResult:
    EngineeringIntentInputValidator.validate(input_)

    normalized_text, tokens = normalize_and_tokenize(input_.request_text)
    matches = evaluate_all_rules(tokens, rules)
    intent_type, secondary_intent_types = _resolve_intent_type(matches)

    return build_engineering_intent(
        input_=input_,
        normalized_text=normalized_text,
        matches=matches,
        intent_type=intent_type,
        secondary_intent_types=secondary_intent_types,
        evaluated_rule_count=len(rules),
    )


class EngineeringRequestClassifier:
    """A thin, named façade over ``classify_engineering_request`` - kept
    for the same reason every sibling bounded context's own
    builder/validator class is: the milestone names it explicitly,
    while every sibling exposes its logic as plain functions."""

    @staticmethod
    def classify(
        input_: EngineeringIntentClassificationInput,
        *,
        rules: tuple[EngineeringIntentRule, ...] = CLASSIFICATION_RULES,
    ) -> EngineeringIntentClassificationResult:
        return classify_engineering_request(input_, rules=rules)
