"""
Typed failures of deterministic engineering reasoning.

There is exactly one, and it is raised at **query construction** rather
than during evaluation. That placement is the point: an evaluator that
had to defend itself against malformed questions would be an evaluator
whose outcomes mean two different things - "the governed knowledge says
this" and "your question made no sense". Those are not the same answer
and must not share a vocabulary.

A reasoning *outcome* reports what governed knowledge establishes. A
reasoning *error* reports that there was no question to answer.
"""

from __future__ import annotations


class EngineeringReasoningError(Exception):
    """Base class for every reasoning failure."""


class SameAssetComparisonError(EngineeringReasoningError):
    """
    A structural relationship was asked about one asset and itself.

    ``shared_structural_location(A, A)`` is not a question governed
    knowledge can answer usefully. Every asset trivially shares every one
    of its own locations with itself, so a positive answer would be
    true, worthless, and indistinguishable at a glance from the real
    conclusion that two *different* assets stand in one place.

    Refused at construction rather than answered, because the alternative
    - an `ESTABLISHED` result whose two participants are the same object
    - is exactly the kind of technically-true statement that becomes a
    misleading line in an engineering report.
    """

    def __init__(self, asset_node_id: str) -> None:
        self.asset_node_id = asset_node_id
        super().__init__(
            "A structural relationship question needs two distinct "
            f"governed assets; both sides named '{asset_node_id}'."
        )
