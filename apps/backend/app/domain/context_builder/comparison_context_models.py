"""
The two-sided context a comparison needs (EPIC 5, Milestone 24.2).

Context Builder's own ``ContextPackage`` is deliberately **not** extended
to carry two sides. It is the artifact for *one* body of evidence, and
every one of its fields - coverage, budget consumption, retrieval summary,
statistics - is a statement about that one body. Adding a second set to it
would make every existing field ambiguous.

Instead a ``ComparisonContextPackage`` holds two whole
``ContextPackage``s, each assembled by the same governed Context
Assembly, entirely unchanged. That is the smallest honest
representation of "two labelled
evidence groups": the sides are separate objects, so nothing downstream
can flatten them by accident, and each side keeps its own coverage and
budget story rather than an averaged one that would describe neither.

``left`` and ``right`` are **named fields, never a list with role
labels.** "Compare A with B" and "compare B with A" are different
questions - additions, removals and directional changes all invert - so
the ordering is made structural rather than conventional: there is no
index to transpose and no role tag to mislabel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage


@dataclass(frozen=True, slots=True)
class ComparisonOperandContext:
    """One side of a comparison: the designation the engineer named, and
    the evidence assembled for it.

    ``designation`` is carried so a reader (and the prompt) can say *what*
    each side is, rather than only "left" and "right". It is the text the
    request contained, never a canonical identifier this system chose for
    it."""

    designation: str
    package: ContextPackage

    @property
    def evidence_count(self) -> int:
        return len(self.package.selected_items)

    @property
    def has_evidence(self) -> bool:
        return self.evidence_count > 0


@dataclass(frozen=True, slots=True)
class ComparisonContextStatistics:
    left_evidence_count: int
    right_evidence_count: int
    both_sides_have_evidence: bool


@dataclass(frozen=True, slots=True)
class ComparisonContextPackage:
    """
    The bounded, two-sided artifact a comparison prompt is built from.

    Deliberately holds no merged view of the two sides - no combined
    item list, no union, no diff. Computing a difference is the
    comparison's *answer*, and precomputing one here would either
    duplicate the reasoning or, worse, invent a structural difference
    (two entities are not "the same attribute changed" merely because
    their attribute names match) that the evidence does not support.
    """

    project_id: int
    left: ComparisonOperandContext
    right: ComparisonOperandContext
    statistics: ComparisonContextStatistics
    assembled_at: datetime

    @property
    def both_sides_have_evidence(self) -> bool:
        return self.left.has_evidence and self.right.has_evidence
