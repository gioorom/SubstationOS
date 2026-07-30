"""
What a review is *about*.

A review never contains the thing it reviews. It names it, by the
artefact's own deterministic key, and stops there. That is the whole
reason the pipeline stays the single producer of engineering knowledge:
there is no field on a review into which a semantic statement, a fact or
an entity could be copied, so no review can quietly become a second
account of what the document says.

``ReviewTargetType`` is generic **and currently has one member**. The
EPIC that introduced this context asked for exactly that: the
architecture must admit evidence, entities and facts later, and this
milestone must not review them. A second member is added the day a
milestone reviews a second artefact - not in anticipation of one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.human_review.review_exceptions import InvalidReviewTargetError

MAX_TARGET_KEY_LENGTH = 128


class ReviewTargetType(str, Enum):
    """
    The kinds of artefact that may be reviewed.

    One member, deliberately. Evidence, entities, facts and documents are
    **not** reviewable in this milestone, and adding their members here
    "ready for later" would be four values that no endpoint accepts, no
    projection understands and no test covers.
    """

    SEMANTIC_STATEMENT = "semantic_statement"


@dataclass(frozen=True, slots=True)
class ReviewTarget:
    """
    One reviewable artefact, named by identity alone.

    ``document_id`` is carried alongside the key because every artefact
    this context will ever review belongs to a document, and because a
    key without its document cannot be resolved back to anything - the
    keys are deterministic hashes, unique in practice, but the document
    is what makes a lookup possible rather than a scan.
    """

    target_type: ReviewTargetType
    target_key: str
    document_id: int

    def __post_init__(self) -> None:
        key = self.target_key.strip()

        if not key:
            raise InvalidReviewTargetError(
                "A review target must name an artefact key."
            )

        if len(key) > MAX_TARGET_KEY_LENGTH:
            raise InvalidReviewTargetError(
                f"A target key may not exceed {MAX_TARGET_KEY_LENGTH} "
                "characters."
            )

        if self.document_id <= 0:
            raise InvalidReviewTargetError(
                "A review target must name the document it belongs to."
            )

        object.__setattr__(self, "target_key", key)

    def describe(self) -> str:
        """``semantic_statement:abc…`` - for an audit event's resource."""

        return f"{self.target_type.value}:{self.target_key}"

    @classmethod
    def semantic_statement(
        cls, statement_key: str, document_id: int
    ) -> "ReviewTarget":
        return cls(
            target_type=ReviewTargetType.SEMANTIC_STATEMENT,
            target_key=statement_key,
            document_id=document_id,
        )
