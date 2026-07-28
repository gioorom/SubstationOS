"""
The fixed, documented policy table mapping a classified intent to
retrieval behaviour - explicit immutable data, never a large if/elif
chain. The same "policy table, not code" convention Engineering Request
Classification's ``engineering_intent_rules.py``, Structured Retrieval's
``scoring_policy.py`` and Prompt Builder's ``composition_policy.py`` all
established.

Every value here is a deliberate, reviewable decision. Bump
``BRIDGE_POLICY_VERSION`` whenever an entry changes, so
``RetrievalBridgeMetadata`` can record which policy produced a given
configuration.

**Only intents this system actually implements a workflow for appear
below** - four since Milestone 24.1 added verification. An intent absent
from this table is reported as ``UNSUPPORTED_INTENT_MAPPING`` - never
mapped to a default policy, which would silently answer a question with a
retrieval shape nobody chose for it.

That coupling is deliberate: a policy entry without a workflow would
prepare a request the engine then refuses, and a workflow without a
policy entry would be reachable only by a caller writing retrieval
criteria by hand. The two sets are kept equal, and a test asserts it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)

RETRIEVAL_BRIDGE_VERSION = "1.0"
BRIDGE_POLICY_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class IntentRetrievalPolicy:
    """
    How one classified intent becomes retrieval criteria.

    ``allows_canonical_entity_lookup`` decides whether a designation that
    Canonicalization *can* resolve is used as an entity lookup. It is
    ``False`` for DOCUMENT_LOOKUP because that workflow reads the
    Engineering Index by identifier, not the knowledge graph by canonical
    id - handing it a canonical reference would send it looking for a
    document mentioning the string "CABLE:C-295", which no document does.

    ``include_neighborhood``/``neighborhood_depth`` are the only
    expansion this bridge ever applies, and only where the workflow's own
    question requires it (see ENGINEERING_EXPLANATION below).
    """

    intent_type: EngineeringIntentType
    allows_canonical_entity_lookup: bool
    lexical_mode: RetrievalMode
    include_neighborhood: bool
    neighborhood_depth: int
    result_limit: int


# The default result limit. Deliberately the same value the engine's own
# execution request already defaults to, so the bridge introduces no new
# tuning surface and a derived request is indistinguishable in shape from
# a hand-written one.
_DEFAULT_RESULT_LIMIT = 20

RETRIEVAL_POLICY_BY_INTENT: dict[
    EngineeringIntentType, IntentRetrievalPolicy
] = {
    # A knowledge query asks for a specific fact. When the engineer named
    # a designation this system can resolve, look that entity up
    # directly; otherwise search lexically for what they wrote. No
    # neighborhood expansion: "quale TA è installato sul cavo C-295?" is
    # answered by the cable's own facts, and pulling in its neighbours
    # would widen the evidence beyond the question.
    EngineeringIntentType.KNOWLEDGE_QUERY: IntentRetrievalPolicy(
        intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        allows_canonical_entity_lookup=True,
        lexical_mode=RetrievalMode.LEXICAL_SEARCH,
        include_neighborhood=False,
        neighborhood_depth=0,
        result_limit=_DEFAULT_RESULT_LIMIT,
    ),
    # A document lookup searches the Engineering Index for recorded
    # mentions of a designation, so it always wants the designation
    # *as written* - never a canonical reference (see the field note
    # above).
    EngineeringIntentType.DOCUMENT_LOOKUP: IntentRetrievalPolicy(
        intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
        allows_canonical_entity_lookup=False,
        lexical_mode=RetrievalMode.LEXICAL_SEARCH,
        include_neighborhood=False,
        neighborhood_depth=0,
        result_limit=_DEFAULT_RESULT_LIMIT,
    ),
    # An explanation asks what something *does* and how its parts relate,
    # so the relationships around the named equipment are part of the
    # answer, not context beyond it. This is the one place the bridge
    # expands scope, it does so by fixed policy rather than per request,
    # and depth is 1 - the only depth Structured Retrieval supports.
    EngineeringIntentType.ENGINEERING_EXPLANATION: IntentRetrievalPolicy(
        intent_type=EngineeringIntentType.ENGINEERING_EXPLANATION,
        allows_canonical_entity_lookup=True,
        lexical_mode=RetrievalMode.LEXICAL_SEARCH,
        include_neighborhood=True,
        neighborhood_depth=1,
        result_limit=_DEFAULT_RESULT_LIMIT,
    ),
    # Verification (Milestone 24.1). Two deliberate differences from the
    # entries above:
    #
    # `allows_canonical_entity_lookup=False` - a verification statement is
    # usually *about a relationship between things it names* ("check
    # whether cable C-295 is connected to TA-12"). An entity lookup
    # resolves one canonical entity and carries no lexical terms, so the
    # second designation would be dropped, and a request naming two
    # canonicalizable entities would be refused as conflicting. Searching
    # lexically for every designation retrieves evidence about all of them,
    # which is what deciding the statement actually needs.
    #
    # `include_neighborhood=True` - a relational claim is settled by
    # relationships, so the one hop around the named equipment is part of
    # the evidence rather than context beyond it. Same fixed-policy
    # expansion as an explanation, for the same kind of reason.
    EngineeringIntentType.VERIFICATION_REQUEST: IntentRetrievalPolicy(
        intent_type=EngineeringIntentType.VERIFICATION_REQUEST,
        allows_canonical_entity_lookup=False,
        lexical_mode=RetrievalMode.LEXICAL_SEARCH,
        include_neighborhood=True,
        neighborhood_depth=1,
        result_limit=_DEFAULT_RESULT_LIMIT,
    ),
}

# --- Comparison (Milestone 24.2) --------------------------------------------
#
# A comparison names exactly two subjects. The count is a hard rule rather
# than a bound: one operand is not a comparison, and three would leave the
# system choosing which two the engineer meant.
REQUIRED_COMPARISON_OPERAND_COUNT = 2

# The policy applied to **each** operand independently. It sits outside
# RETRIEVAL_POLICY_BY_INTENT because a comparison does not produce one
# retrieval configuration - it produces two, and the table above maps an
# intent to exactly one.
#
# `allows_canonical_entity_lookup=True`, unlike verification: each side
# has its own configuration to carry a canonical reference, so two
# canonicalizable subjects are the normal case here rather than the
# conflict they are on the single-operand path.
#
# `include_neighborhood=True`: what usually differs between two montanti
# is what each is connected to and protected by, so the one hop around
# each subject is part of what is being compared, not context beyond it.
COMPARISON_OPERAND_POLICY = IntentRetrievalPolicy(
    intent_type=EngineeringIntentType.ENGINEERING_COMPARISON,
    allows_canonical_entity_lookup=True,
    lexical_mode=RetrievalMode.LEXICAL_SEARCH,
    include_neighborhood=True,
    neighborhood_depth=1,
    result_limit=_DEFAULT_RESULT_LIMIT,
)

SUPPORTED_INTENT_TYPES: tuple[EngineeringIntentType, ...] = tuple(
    sorted(RETRIEVAL_POLICY_BY_INTENT, key=lambda intent: intent.value)
)

# Every intent this bridge can prepare, single-operand or comparison -
# the set that must stay equal to the engine's registered workflows.
PREPARABLE_INTENT_TYPES: tuple[EngineeringIntentType, ...] = tuple(
    sorted(
        set(SUPPORTED_INTENT_TYPES)
        | {EngineeringIntentType.ENGINEERING_COMPARISON},
        key=lambda intent: intent.value,
    )
)


def policy_for(
    intent_type: EngineeringIntentType,
) -> IntentRetrievalPolicy | None:
    """The one lookup into the table. Returns ``None`` for an intent this
    bridge deliberately does not map - the caller reports it as a typed
    unsupported result rather than substituting a default."""

    return RETRIEVAL_POLICY_BY_INTENT.get(intent_type)
