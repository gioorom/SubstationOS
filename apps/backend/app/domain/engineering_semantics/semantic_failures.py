"""
The failure taxonomy for semantic interpretation (Milestone 30.1).

A separate enum from the fact, entity and evidence vocabularies, for the
reason those are separate from each other: these are different questions.
Construction asks "which entities are associated?"; interpretation asks
"what does that association mean?" and has failures - an unknown rule, an
unusable support chain - that would be meaningless below it.

**Ambiguous mapping within a subject is deliberately not a failure of the
run.** A designation associated with two power quantities receives no
statement and one diagnostic, and the interpretation still succeeds - the
rules working is not a system failure. The
``AMBIGUOUS_SEMANTIC_MAPPING`` code below is for the *validation* case: a
set that somehow contains two statements of one type for one subject,
which would be a defect rather than a data condition.

Seven named causes. Nothing is collapsed into a generic "interpretation
failed", because they send an engineer to different places.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SemanticInterpretationFailureCode(str, Enum):
    """Why a semantic set could not be produced."""

    # There is no fact set for this document. Not an error about the
    # document - interpretation is the step after construction.
    FACT_SET_MISSING = "fact_set_missing"
    # A statement cites a rule or version the catalogue does not declare.
    UNSUPPORTED_SEMANTIC_RULE = "unsupported_semantic_rule"
    # The facts were constructed under a policy this interpreter does not
    # know. Refusing is the only safe answer: a newer policy may carry
    # predicates this code would silently ignore, and a semantic set
    # missing half its meaning is worse than a visible refusal.
    UNSUPPORTED_FACT_VERSION = "unsupported_fact_version"
    # A statement cites facts that are not in the source set, or cites
    # none at all. The meaning would rest on support nobody could follow.
    INVALID_SUPPORT = "invalid_support"
    # A set contains two statements of one type for one subject - a
    # defect in the interpreter, caught before it can be stored.
    AMBIGUOUS_SEMANTIC_MAPPING = "ambiguous_semantic_mapping"
    # The assembled set violates an invariant.
    SEMANTIC_VALIDATION_FAILURE = "semantic_validation_failure"
    # Interpreted, and could not be stored.
    SEMANTIC_PERSISTENCE_FAILURE = "semantic_persistence_failure"
    # The facts describe a different document or version than the one
    # asked about.
    INCONSISTENT_SOURCE_IDENTITY = "inconsistent_source_identity"


@dataclass(frozen=True, slots=True)
class SemanticInterpretationFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: SemanticInterpretationFailureCode
    message: str
    detail: str | None = None
