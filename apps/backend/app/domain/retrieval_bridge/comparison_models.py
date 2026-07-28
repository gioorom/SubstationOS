"""
Value objects for comparison request preparation (Milestone 24.2) - the
two-operand counterpart to ``retrieval_bridge_models.py``.

A comparison names **exactly two** subjects. That count is a hard rule,
not a convenience: one operand is not a comparison, three leave the system
choosing which two the engineer meant, and choosing silently is how a
comparison of the wrong pair gets acted on. Both are typed preparation
failures.

``left`` and ``right`` are **named fields, never a list.** "Confronta T1
con T2" and "confronta T2 con T1" are different questions - additions,
removals and every directional finding invert - so the ordering is
structural rather than conventional. There is no index to transpose and no
role tag to mislabel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    RequestDesignation,
    RetrievalBridgeFailure,
    RetrievalConfiguration,
)


@dataclass(frozen=True, slots=True)
class ComparisonOperand:
    """One side of a prepared comparison: the designation the engineer
    named, how far it resolved, and the retrieval criteria derived for it.

    ``designation`` carries the full ``RequestDesignation`` rather than
    just its text, so an operand's provenance - where in the request it
    appeared, and whether it resolved to a canonical entity - travels with
    it rather than being recomputed downstream."""

    designation: RequestDesignation
    configuration: RetrievalConfiguration

    @property
    def text(self) -> str:
        return self.designation.text


@dataclass(frozen=True, slots=True)
class ComparisonScope:
    """
    What the comparison is scoped to.

    Deliberately minimal: this system can determine, deterministically,
    only that both operands are entity-shaped designations in the same
    project. It records that and nothing more. A richer scope ("compare
    only the protections", "compare only revision metadata") would have to
    be inferred from the request's prose, which is exactly the inference
    this pipeline refuses - so it is not modelled until something can
    supply it honestly.
    """

    project_id: int
    both_operands_resolved_canonically: bool


@dataclass(frozen=True, slots=True)
class ComparisonBridgeMetadata:
    retrieval_bridge_version: str
    bridge_policy_version: str
    project_id: int
    engineering_intent_id: str
    intent_type: EngineeringIntentType
    derived_at: datetime


@dataclass(frozen=True, slots=True)
class ComparisonBridgeStatistics:
    designation_count: int
    required_operand_count: int
    canonical_reference_count: int


@dataclass(frozen=True, slots=True)
class ComparisonConfiguration:
    """The two prepared operands, in the order the request named them."""

    left: ComparisonOperand
    right: ComparisonOperand
    scope: ComparisonScope


@dataclass(frozen=True, slots=True)
class ComparisonBridgeResult:
    """
    Either a ``configuration`` (``resolved=True``) or a ``failure``
    (``resolved=False``) - never both, never neither.

    ``designations`` is populated in both cases: when preparation refuses
    because a request named one subject or four, an engineer needs to see
    which ones were found in order to understand why.
    """

    resolved: bool
    metadata: ComparisonBridgeMetadata
    statistics: ComparisonBridgeStatistics
    designations: tuple[RequestDesignation, ...] = ()
    configuration: ComparisonConfiguration | None = None
    failure: RetrievalBridgeFailure | None = None
