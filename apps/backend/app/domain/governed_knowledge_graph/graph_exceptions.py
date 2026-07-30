"""
Typed failures of the Governed Knowledge Graph context.

Every one derives from ``GovernedGraphError``. None of them carries a
pipeline artefact or a review: this context reads both and owns neither,
so an exception holding one would mean it had taken a copy.
"""

from __future__ import annotations


class GovernedGraphError(Exception):
    """Base class for every failure of the governed graph context."""


class InvalidGraphIdentityError(GovernedGraphError):
    """An identity that names no governed artefact."""


class InvalidGraphProvenanceError(GovernedGraphError):
    """
    Provenance that does not explain where the knowledge came from.

    Raised at construction, so a node or edge whose origin cannot be
    stated is refused rather than stored. A graph object nobody can trace
    is worse than a missing one: the missing one is visibly missing.
    """


class UnpromotableArtefactError(GovernedGraphError):
    """
    The artefact cannot become graph knowledge under any rule.

    Carries the reason so a caller can report it. Not an error condition
    in normal operation - most statements are unpromotable most of the
    time, because nobody has approved them.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class GraphIntegrityError(GovernedGraphError):
    """
    The graph would become internally inconsistent.

    An edge whose endpoints are the wrong kinds, or which references a
    node that was never promoted. Raised rather than stored: a graph that
    answered "what is the rated power of 630 kVA?" would be worse than
    one that answered nothing.
    """


class GraphPersistenceError(GovernedGraphError):
    """The projection could not be written."""
