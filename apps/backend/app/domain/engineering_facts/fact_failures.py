"""
The failure taxonomy for fact construction (Milestone 29.2).

A separate enum from the extraction, evaluation and resolution
vocabularies, for the reason those are separate from each other: these
are different questions. Resolution asks "which observations are one
thing?"; construction asks "which of those things are associated?" and
has failures - missing support, an unknown rule - that would be
meaningless upstream.

**Ambiguous pairing is deliberately not in this list.** A line whose
designations cannot be matched to its quantities is not a system failure;
it is the rules working. It produces a diagnostic and no fact, and the
construction still succeeds.

Ten named causes. Nothing is collapsed into a generic "construction
failed", because they send an engineer to different places: there are no
entities, the entities cite evidence that is gone, the two disagree about
their source, the entities were built under rules this code does not
know, a rule is malformed, a rule raised, the support is unusable, the
result violates an invariant, storage failed, or two stages disagree
about reality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FactConstructionFailureCode(str, Enum):
    """Why a fact set could not be produced."""

    # There is no entity set for this document. Not an error about the
    # document - construction is the step after resolution.
    ENTITY_SET_MISSING = "entity_set_missing"
    # The entities cite evidence, and the evidence set is not there. The
    # associations would rest on support nobody could check.
    ENTITY_EVIDENCE_MISSING = "entity_evidence_missing"
    # The entity set and the evidence set describe different document
    # versions. Continuing would associate entities from one revision
    # using observations from another.
    INCONSISTENT_SOURCE_IDENTITY = "inconsistent_source_identity"
    # The entities were resolved under a policy this constructor does not
    # know. Refusing is the only safe answer: a newer policy may carry
    # entity types this code would silently ignore.
    UNSUPPORTED_ENTITY_SET_VERSION = "unsupported_entity_set_version"
    # A fact cites a rule or version the catalogue does not declare.
    INVALID_CONSTRUCTION_RULE = "invalid_construction_rule"
    # A rule raised while constructing. The one genuinely unknown cause.
    RULE_EXECUTION_FAILURE = "rule_execution_failure"
    # A fact's support does not hold up - it cites evidence the entities
    # do not, or names a location its support does not share.
    INVALID_FACT_SUPPORT = "invalid_fact_support"
    # The assembled set violates an invariant - a fact whose subject and
    # object are the same entity, or one with no support at all.
    FACT_VALIDATION_FAILURE = "fact_validation_failure"
    # Built, and could not be stored.
    FACT_PERSISTENCE_FAILURE = "fact_persistence_failure"
    # Two stages reported success and disagree about what exists.
    # Nothing should be able to reach this; if it does, continuing would
    # build on a contradiction.
    INCONSISTENT_PIPELINE_STATE = "inconsistent_pipeline_state"


@dataclass(frozen=True, slots=True)
class FactConstructionFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: FactConstructionFailureCode
    message: str
    detail: str | None = None
