"""
What can go wrong in this context, named.

One failure mode, because there is only one: a stored segment whose
kind is not a kind this system knows. Everything else search does is
total - a query that matches nothing is an answer, not an error.
"""

from __future__ import annotations


class DocumentSearchError(Exception):
    """Base class for every failure this context raises."""


class UnknownSegmentKindError(DocumentSearchError):
    """
    A stored segment names a source family this version does not know.

    Raised rather than skipped because the index is a projection of a
    canonical representation, and a row it cannot read means the two
    have diverged. Dropping the row quietly would turn a version
    mismatch into a search that is silently incomplete, which in this
    domain reads as "the document does not say that".
    """

    def __init__(self, kind: str) -> None:
        super().__init__(
            f"Unknown search segment kind {kind!r}. The index was "
            f"written by a different version and must be rebuilt."
        )
        self.kind = kind
