"""
Value objects for the Classification-to-Retrieval Bridge (EPIC 5,
Milestone 23B.3) - the deterministic step that turns a **classified**
engineering request into the **retrieval configuration** the Engineering
Engine already accepts.

Until this milestone the pipeline had a gap an engineer could not cross
on their own: the classifier decided *which workflow* a request wanted,
and the engine required retrieval criteria (a canonical entity id, an
entity type, lexical terms) that only a caller who already knew the
graph's contents could supply. This bounded context closes that gap, and
nothing more.

**What it is not**, deliberately:

- It is **not** a query planner: it never decides how to execute
  retrieval, never touches Graph Query, and never runs anything.
- It is **not** an extractor of engineering facts: it reports
  designations a request literally contains, never entities it believes
  the request is "about".
- It performs **no** semantic inference, no embeddings, no LLM call, no
  provider call, and no fuzzy matching. A designation it cannot resolve
  against the existing canonical vocabulary becomes a lexical term - it
  is never guessed into a canonical identifier.
- It has **no fallback**. Insufficient or conflicting evidence yields a
  typed unresolved result, never a broadened retrieval that would answer
  a question the engineer did not ask.

Determinism: the same ``EngineeringIntent`` and the same policy version
always produce the same ``RetrievalBridgeResult``, including designation
order and every derived field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)


class DesignationResolution(str, Enum):
    """How far a designation found in the request text could be resolved
    against **existing** vocabularies - never a confidence, never a
    guess.

    ``CANONICAL_REFERENCE`` means Canonicalization's own
    ``normalize_entity_reference`` recognized it and returned a real
    ``entity_type``/``canonical_id`` (e.g. "C-295" -> ``CABLE:C-295``).
    ``LEXICAL_TERM`` means it did not - the designation is real and is
    carried forward verbatim as a search term, but this system does not
    claim to know which graph entity it names.
    """

    CANONICAL_REFERENCE = "canonical_reference"
    LEXICAL_TERM = "lexical_term"


class RetrievalBridgeFailureCode(str, Enum):
    """A closed, provider-neutral failure taxonomy. Every value describes
    something about the *request or the mapping*; none describes a
    provider, a network, or an execution outcome, because this context
    executes nothing."""

    INVALID_BRIDGE_INPUT = "invalid_bridge_input"
    UNSUPPORTED_INTENT_MAPPING = "unsupported_intent_mapping"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INVALID_RETRIEVAL_CONFIGURATION = "invalid_retrieval_configuration"


@dataclass(frozen=True, slots=True)
class RetrievalBridgeFailure:
    """``detail`` is a safe, already-composed explanation naming what was
    found and what was expected - never a stack trace, never a raw
    exception from another bounded context."""

    code: RetrievalBridgeFailureCode
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class RequestDesignation:
    """
    One equipment designation the request literally contains ("T2",
    "87T", "C-295"), with how far it could be resolved.

    ``text`` is preserved **exactly as the engineer wrote it** - not
    case-folded and not normalized - because a designation is an
    identifier in the field, and the downstream consumers that need it
    folded (Canonicalization, the Engineering Index's case-insensitive
    search, lexical matching) each fold it themselves.

    ``token_index`` is the position in the request's own whitespace
    tokenization, so ordering is reproducible and a reader can point at
    where a designation came from.
    """

    text: str
    token_index: int
    resolution: DesignationResolution
    entity_type: str | None = None
    canonical_id: str | None = None
    canonical_reference: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalConfiguration:
    """
    The typed, immutable retrieval criteria this bridge produces - a
    field-for-field mirror of the ``retrieval_*`` configuration
    ``EngineeringEngineExecutionRequest`` already accepts, so the engine
    consumes it without a new model, a new adapter, or a change of any
    kind.

    ``canonical_entity_id`` carries the **full** canonical reference
    ("CABLE:C-295"), which is the shape Structured Retrieval's own
    criterion parser expects.

    ``entity_type`` is populated **only** alongside a canonical
    reference, never on its own. That is a real invariant, not a
    convention: the engine's retrieval step handler derives its
    ``RetrievalMode`` from which of these fields are set, so emitting a
    bare entity type would silently turn a lexical search into an
    entity-type search. Enforced by ``retrieval_bridge_validation.py``
    and covered by a test that the mode declared here always equals the
    mode the engine will derive.

    ``attribute_name`` is always ``None`` today: nothing in the
    classifier's evidence identifies an attribute, and inventing one
    would be exactly the inference this milestone forbids. The field
    exists because the engine accepts it, so a future capability that can
    honestly populate it needs no model change.
    """

    mode: RetrievalMode
    limit: int
    include_neighborhood: bool
    neighborhood_depth: int
    lexical_terms: tuple[str, ...] = ()
    canonical_entity_id: str | None = None
    entity_type: str | None = None
    attribute_name: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalBridgeMetadata:
    """Provenance for one derivation - which request, which classified
    intent, and which versioned policy produced the configuration."""

    retrieval_bridge_version: str
    bridge_policy_version: str
    project_id: int
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    derived_at: datetime


@dataclass(frozen=True, slots=True)
class RetrievalBridgeStatistics:
    designation_count: int
    canonical_reference_count: int
    lexical_term_count: int


@dataclass(frozen=True, slots=True)
class RetrievalBridgeResult:
    """
    Either a ``configuration`` (``resolved=True``) or a ``failure``
    (``resolved=False``) - never both, never neither.

    ``designations`` is populated in **both** cases on purpose: when the
    bridge refuses, an engineer needs to see what it did and did not find
    in order to understand why. A refusal that reported nothing would be
    indistinguishable from a bug.
    """

    resolved: bool
    metadata: RetrievalBridgeMetadata
    statistics: RetrievalBridgeStatistics
    designations: tuple[RequestDesignation, ...] = ()
    configuration: RetrievalConfiguration | None = None
    failure: RetrievalBridgeFailure | None = None


@dataclass(frozen=True, slots=True)
class RetrievalBridgeValidationResult:
    """Structural validation of a produced ``RetrievalConfiguration``.
    Never validates engineering correctness, and never judges whether the
    derived criteria were the "right" ones."""

    valid: bool
    errors: tuple[str, ...]
