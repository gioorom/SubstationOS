"""
Value objects for Engineering Request Classification (EPIC 5, Milestone
22). The package is named ``engineering_intent`` for roadmap
continuity, but its documented responsibility is **classifying an
explicit engineering request into a structured domain result a future
orchestration component can use to select a workflow** - never
detecting a user's psychological intent, never "understanding" or
"reasoning about" the request.

Classification is deterministic, explainable, and provider-independent:
a fixed, versioned table of explicit rules
(``engineering_intent_rules.py``) is evaluated against deterministically
normalized request text (``engineering_intent_normalization.py``), and
the winning classification is resolved by an explicit, documented
precedence policy (``engineering_intent_policy.py``). No LLM, no
embeddings, no vector similarity, no semantic model, no external NLP
service is involved at any point - see
``docs/architecture/adr/0019-engineering-request-classification.md``.

An ``EngineeringIntent`` is a **classification result, not a command**:
it executes no workflow, retrieves no documents, queries no graph,
invokes no LLM, and never modifies ``Conversation`` or
``WorkingMemory``. The future Engineering Assistant (Milestone 23) will
consume it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EngineeringIntentType(str, Enum):
    """A deliberately small, operational taxonomy - see
    ``docs/architecture/engineering_intent.md`` for each type's full
    definition. Deliberately not dozens of types: every type here must
    map to a workflow a future orchestrator could actually select."""

    DOCUMENT_LOOKUP = "document_lookup"
    KNOWLEDGE_QUERY = "knowledge_query"
    ENGINEERING_EXPLANATION = "engineering_explanation"
    ENGINEERING_COMPARISON = "engineering_comparison"
    DRAWING_REQUEST = "drawing_request"
    VERIFICATION_REQUEST = "verification_request"
    NAVIGATION_REQUEST = "navigation_request"
    GENERAL_ENGINEERING_REQUEST = "general_engineering_request"
    UNSUPPORTED_REQUEST = "unsupported_request"
    AMBIGUOUS_REQUEST = "ambiguous_request"


class EngineeringIntentConfidence(str, Enum):
    """Deterministic and categorical - never a fabricated
    floating-point probability (no model produces one here, and
    inventing one would imply a statistical basis this classifier does
    not have). See ``engineering_intent_policy.py``'s
    ``derive_confidence`` for the exact, documented policy."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"


class EngineeringIntentRuleStrength(str, Enum):
    """How decisive one rule's match is. ``STRONG`` rules identify a
    specific workflow verb or phrase (e.g. "confronta", "verifica");
    ``WEAK`` rules identify a supporting signal that alone is not
    decisive (e.g. a bare interrogative like "quale"); ``DOMAIN`` rules
    only establish that the request is engineering-related at all."""

    STRONG = "strong"
    WEAK = "weak"
    DOMAIN = "domain"


class EngineeringIntentEvidenceType(str, Enum):
    """Which kind of deterministic signal produced one piece of
    evidence - recorded so every classification is explainable and
    reproducible without storing hidden reasoning."""

    TOKEN_MATCH = "token_match"
    PHRASE_MATCH = "phrase_match"
    DOMAIN_VOCABULARY_MATCH = "domain_vocabulary_match"
    STRUCTURAL_CONTEXT = "structural_context"


@dataclass(frozen=True, slots=True)
class EngineeringIntentId:
    """
    Deterministically derived from stable classification provenance -
    ``f"{conversation_id}:{turn_id}:{policy_version}"`` - **never a
    random UUID**. Reclassifying identical input under the same policy
    version must produce the same identity and the same result; a
    changed policy version deliberately produces a different identity,
    so two classifications made under different policies are never
    mistaken for the same result.
    """

    value: str


@dataclass(frozen=True, slots=True)
class EngineeringIntentRule:
    """
    One explicit, immutable rule definition. ``tokens`` match whole
    normalized tokens (never substrings inside unrelated words);
    ``phrases`` match a contiguous run of normalized tokens. A rule
    matches when any of its tokens or phrases is present.

    Rules are data, not code: the full table lives in
    ``engineering_intent_rules.py`` and is independently testable one
    rule at a time (``evaluate_rule``), never buried inside one large
    if/elif function.
    """

    rule_id: str
    candidate_intent_type: EngineeringIntentType
    strength: EngineeringIntentRuleStrength
    tokens: tuple[str, ...] = ()
    phrases: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class EngineeringIntentRuleMatch:
    """One rule firing against one specific position in the normalized
    token sequence. ``token_index`` is the deterministic ordering key -
    the position of the first matched token - so evidence ordering is
    reproducible without depending on rule-table iteration order
    alone."""

    rule_id: str
    candidate_intent_type: EngineeringIntentType
    strength: EngineeringIntentRuleStrength
    matched_text: str
    token_index: int
    evidence_type: EngineeringIntentEvidenceType


@dataclass(frozen=True, slots=True)
class EngineeringIntentEvidence:
    """
    A structured, reproducible explanation of one signal that
    contributed to the classification. Contains **no hidden reasoning,
    no chain-of-thought, and no AI-generated prose** - only which rule
    fired, what text matched, where, how strongly, and toward which
    candidate type. ``description_code`` is a stable, machine-readable
    code (never a free-text sentence), so a consumer can present its
    own localized explanation.
    """

    evidence_type: EngineeringIntentEvidenceType
    matched_rule_id: str
    matched_text: str
    token_index: int
    candidate_intent_type: EngineeringIntentType
    strength: EngineeringIntentRuleStrength
    description_code: str
    sequence: int


@dataclass(frozen=True, slots=True)
class EngineeringIntentPolicy:
    """The versioned, documented classification policy in force - which
    rules exist, their precedence order, the confidence derivation, and
    the ambiguity rule. Never a per-request, ad hoc choice."""

    version: str


@dataclass(frozen=True, slots=True)
class EngineeringIntentVersion:
    engineering_intent_version: str
    classification_policy_version: str
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringIntentMetadata:
    engineering_intent_version: str
    classification_policy_version: str
    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    original_request_text: str
    normalized_request_text: str
    classified_at: datetime
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringIntentStatistics:
    evaluated_rule_count: int
    matched_rule_count: int
    strong_match_count: int
    weak_match_count: int
    unique_candidate_intent_count: int
    secondary_intent_count: int


@dataclass(frozen=True, slots=True)
class EngineeringIntentClassificationInput:
    """
    Every input this classifier accepts - all deterministic. The
    classifier classifies **the current explicit request**
    (``request_text``), never the whole conversation concatenated into
    an opaque blob.

    ``working_memory_has_open_question``/
    ``working_memory_active_response_count`` are the *only* Working
    Memory signals consumed, and both are purely structural facts
    already computed by Working Memory itself (Milestone 21) - never a
    route into hidden semantic inference over memory contents. They are
    passed as plain, already-extracted values rather than a whole
    ``WorkingMemory`` object so this bounded context needs no
    dependency on the Working Memory context at all (see ADR-0019).

    ``classified_at`` is always supplied by the caller, never read from
    the wall clock inside the domain layer.
    """

    project_id: int
    engineering_session_id: str
    conversation_id: str
    turn_id: str
    request_text: str
    classified_at: datetime
    working_memory_has_open_question: bool = False
    working_memory_active_response_count: int = 0


@dataclass(frozen=True, slots=True)
class EngineeringIntent:
    """
    The immutable classification result. **Not a command**: it executes
    no workflow, retrieves nothing, queries nothing, invokes no LLM,
    and modifies neither ``Conversation`` nor ``WorkingMemory``.

    ``secondary_intent_types`` are *explanatory metadata* recording
    other materially distinct workflows the request also signalled -
    never executable sub-tasks. Real multi-step planning and request
    decomposition belong to a future orchestration milestone.
    """

    engineering_intent_id: EngineeringIntentId
    project_id: int
    intent_type: EngineeringIntentType
    confidence: EngineeringIntentConfidence
    evidence: tuple[EngineeringIntentEvidence, ...]
    secondary_intent_types: tuple[EngineeringIntentType, ...]
    metadata: EngineeringIntentMetadata
    statistics: EngineeringIntentStatistics
    version: EngineeringIntentVersion


@dataclass(frozen=True, slots=True)
class EngineeringIntentValidationResult:
    """
    Whether the just-built ``EngineeringIntent`` satisfies every
    structural invariant this milestone requires. **Structural only** -
    never whether the user's engineering statement is technically
    correct, and never whether the chosen classification is the
    "right" one in any semantic sense.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringIntentClassificationResult:
    project_id: int
    intent: EngineeringIntent
    validation: EngineeringIntentValidationResult
