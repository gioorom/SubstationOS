"""
The fixed, documented classification policy for Engineering Request
Classification (Milestone 22): version stamps, the precedence order,
the ambiguity rule, and the confidence derivation - the same "fixed,
documented policy table" convention every upstream bounded context in
this pipeline establishes. Bump ``CLASSIFICATION_POLICY_VERSION``
whenever any of them changes, so
``EngineeringIntentMetadata``/``EngineeringIntentVersion`` (and the
deterministically derived ``EngineeringIntentId``) record which policy
produced a given result.
"""

from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentConfidence,
    EngineeringIntentRuleMatch,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
)

ENGINEERING_INTENT_VERSION = "1.0"
CLASSIFICATION_POLICY_VERSION = "1.0"
ENGINEERING_INTENT_PACKAGE_VERSION = "1.0"

# The explicit precedence order, applied when more than one workflow
# type has evidence. Adopted as the milestone's own recommended
# starting policy, unchanged - reviewing this repository's domain
# language surfaced no reason to reorder it:
#
# - DRAWING_REQUEST and VERIFICATION_REQUEST rank highest because they
#   request an *action on* engineering content, which is materially
#   more consequential than reading it.
# - ENGINEERING_COMPARISON outranks DOCUMENT_LOOKUP so
#   "confronta i due documenti" classifies by the comparison verb, not
#   the incidental noun "documenti".
# - NAVIGATION_REQUEST outranks DOCUMENT_LOOKUP so "apri la pagina con
#   lo schema" classifies as navigation to a known location rather than
#   a search for one.
# - ENGINEERING_EXPLANATION outranks KNOWLEDGE_QUERY so "spiegami quale
#   TA e installato" is an explanation request, not a bare fact lookup.
#
# GENERAL_ENGINEERING_REQUEST / UNSUPPORTED_REQUEST are terminal
# fallbacks, never competing candidates, so they are ranked last.
# AMBIGUOUS_REQUEST is never a candidate at all - it is an outcome the
# ambiguity rule produces instead of resolving precedence.
INTENT_PRECEDENCE: tuple[EngineeringIntentType, ...] = (
    EngineeringIntentType.DRAWING_REQUEST,
    EngineeringIntentType.VERIFICATION_REQUEST,
    EngineeringIntentType.ENGINEERING_COMPARISON,
    EngineeringIntentType.NAVIGATION_REQUEST,
    EngineeringIntentType.DOCUMENT_LOOKUP,
    EngineeringIntentType.ENGINEERING_EXPLANATION,
    EngineeringIntentType.KNOWLEDGE_QUERY,
    EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
    EngineeringIntentType.UNSUPPORTED_REQUEST,
)

_PRECEDENCE_RANK: dict[EngineeringIntentType, int] = {
    intent_type: index for index, intent_type in enumerate(INTENT_PRECEDENCE)
}

# Workflow types that request a materially distinct *operation* rather
# than a different way of reading the same content. When two or more of
# these are each supported by a STRONG match, precedence alone would
# silently discard a real requested operation - so the classifier
# reports AMBIGUOUS_REQUEST instead (the milestone's own
# "Confronta e modifica lo schema" case). Reading-oriented types
# (DOCUMENT_LOOKUP / ENGINEERING_EXPLANATION / KNOWLEDGE_QUERY) are
# deliberately excluded: they overlap constantly in natural phrasing,
# and forcing ambiguity on every "spiegami quale..." would make the
# classifier useless.
MATERIALLY_DISTINCT_OPERATIONS: frozenset[EngineeringIntentType] = frozenset(
    {
        EngineeringIntentType.DRAWING_REQUEST,
        EngineeringIntentType.VERIFICATION_REQUEST,
        EngineeringIntentType.ENGINEERING_COMPARISON,
        EngineeringIntentType.NAVIGATION_REQUEST,
    }
)


def precedence_rank(intent_type: EngineeringIntentType) -> int:
    """Lower is higher-precedence. Types absent from the table (only
    ``AMBIGUOUS_REQUEST``) rank last."""

    return _PRECEDENCE_RANK.get(intent_type, len(INTENT_PRECEDENCE))


def candidate_types_by_precedence(
    matches: tuple[EngineeringIntentRuleMatch, ...],
) -> tuple[EngineeringIntentType, ...]:
    """Every distinct candidate type present in ``matches``, ordered by
    precedence. Domain-vocabulary matches are excluded - they establish
    only that the request is engineering-related, never a specific
    workflow."""

    candidates = {
        match.candidate_intent_type
        for match in matches
        if match.strength is not EngineeringIntentRuleStrength.DOMAIN
    }

    return tuple(sorted(candidates, key=precedence_rank))


def strong_candidate_types(
    matches: tuple[EngineeringIntentRuleMatch, ...],
) -> frozenset[EngineeringIntentType]:
    return frozenset(
        match.candidate_intent_type
        for match in matches
        if match.strength is EngineeringIntentRuleStrength.STRONG
    )


def is_ambiguous(matches: tuple[EngineeringIntentRuleMatch, ...]) -> bool:
    """``True`` when two or more *materially distinct operations* each
    have a STRONG match - precedence alone would hide a genuinely
    requested operation, so the classifier prefers explicit uncertainty
    over false certainty."""

    distinct_operations = strong_candidate_types(matches) & (
        MATERIALLY_DISTINCT_OPERATIONS
    )

    return len(distinct_operations) >= 2


def derive_confidence(
    intent_type: EngineeringIntentType,
    matches: tuple[EngineeringIntentRuleMatch, ...],
) -> EngineeringIntentConfidence:
    """
    The exact, documented confidence policy - deterministic and
    categorical, never a fabricated probability:

    - ``UNRESOLVED`` - the result is ``AMBIGUOUS_REQUEST`` or
      ``UNSUPPORTED_REQUEST``: no workflow was confidently selected.
    - ``LOW``        - the result is ``GENERAL_ENGINEERING_REQUEST``:
      only broad engineering-domain signals exist, no workflow signal.
    - ``HIGH``       - at least one STRONG match supports the selected
      type, **and** no other type has a STRONG match (one strong rule,
      or several consistent rules, all pointing the same way).
    - ``MEDIUM``     - everything else: the selected type is supported
      only by WEAK matches, or a STRONG match exists but another type
      also has one (a genuine but not decisive signal).
    """

    if intent_type in (
        EngineeringIntentType.AMBIGUOUS_REQUEST,
        EngineeringIntentType.UNSUPPORTED_REQUEST,
    ):
        return EngineeringIntentConfidence.UNRESOLVED

    if intent_type is EngineeringIntentType.GENERAL_ENGINEERING_REQUEST:
        return EngineeringIntentConfidence.LOW

    strong_types = strong_candidate_types(matches)
    if intent_type in strong_types and len(strong_types) == 1:
        return EngineeringIntentConfidence.HIGH

    return EngineeringIntentConfidence.MEDIUM
