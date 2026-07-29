"""
The failure taxonomy for entity resolution (Milestone 29.1).

A separate enum from the extraction and evaluation vocabularies, for the
reason those are separate from each other: these are different questions.
Extraction asks "what does this document contain?"; resolution asks
"which of those observations are one thing?" and has failures - an
unknown rule, an unresolvable grouping - that would be meaningless
upstream.

Six named causes. Nothing is collapsed into a generic "resolution
failed", because they send an engineer to different places: there is no
evidence, the evidence was built under rules this code does not know, a
rule is malformed, a rule raised, the result violates an invariant, or
storage failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntityResolutionFailureCode(str, Enum):
    """Why an entity set could not be produced."""

    # There is no engineering evidence for this document. Not an error
    # about the document - resolution is the step after extraction.
    EVIDENCE_SET_MISSING = "evidence_set_missing"
    # The evidence was extracted under a policy this resolver does not
    # know. Refusing is the only safe answer: a newer policy may carry
    # evidence types this code would silently drop, and an entity set
    # missing half its evidence is worse than a visible refusal.
    UNSUPPORTED_EXTRACTION_POLICY_VERSION = (
        "unsupported_extraction_policy_version"
    )
    # An entity cites a rule or version the catalogue does not declare.
    INVALID_RESOLUTION_RULE = "invalid_resolution_rule"
    # A rule raised while grouping. The one genuinely unknown cause here.
    RESOLUTION_FAILURE = "resolution_failure"
    # The assembled set violates an invariant - an entity with no
    # contributing evidence, or one carrying two typed values.
    ENTITY_VALIDATION_FAILURE = "entity_validation_failure"
    # Built, and could not be stored.
    ENTITY_PERSISTENCE_FAILURE = "entity_persistence_failure"
    # The evidence set describes a different document than the one asked
    # about. Continuing would attach a hypothesis to the wrong document.
    INCONSISTENT_SOURCE_IDENTITY = "inconsistent_source_identity"


@dataclass(frozen=True, slots=True)
class EntityResolutionFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: EntityResolutionFailureCode
    message: str
    detail: str | None = None
