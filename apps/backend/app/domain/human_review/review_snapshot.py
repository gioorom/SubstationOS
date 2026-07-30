"""
What was in front of the engineer when they decided.

A review recorded today has to be readable in five years, after the
document has been re-ingested twice and the rule catalogue has moved on
three versions. The snapshot is what makes that possible: it records
**enough identity to explain what was reviewed**, and deliberately not
the artefact graph itself.

---

## Why identity is enough

``EngineeringSemanticStatement.statement_key`` is a SHA-256 over the
document, the exact fact source, the triple, and the rule and contract
versions. That single fact does most of this milestone's work:

- the same document, the same facts and the same rules always reproduce
  the **same key** - so a re-run that changes nothing leaves every review
  attached, with nothing to detect and nothing to do;
- any change to the rules, the contract, the facts or the bytes produces
  a **different key** - so a statement whose meaning was derived
  differently can never silently inherit a judgement made about the old
  one.

The snapshot therefore does not have to diff artefacts. It records the
identity the statement had, and the service compares that identity
against the document's current interpretation. Everything in
``review_applicability`` follows from this.

## What is deliberately not here

No statement type, no subject, no object, no quantity, no support
payload. A snapshot holding those would be a copy of engineering
knowledge living outside the pipeline that produced it, and the first
time the two disagreed nobody would know which was authoritative. What
the statement *said* is read from the pipeline; what was *reviewed* is
identified here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.domain.human_review.review_exceptions import (
    InvalidReviewSnapshotError,
)

SUPPORT_FINGERPRINT_LENGTH = 64


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    """
    The upstream identity of the reviewed artefact, at review time.

    Every field is copied from an artefact the pipeline produced. None is
    computed by this context except ``support_fingerprint``, which is a
    hash of keys the pipeline produced.
    """

    #: Which bytes. A re-ingested document has a different checksum, and
    #: therefore a different everything.
    content_checksum: str

    #: The rule that assigned the meaning, and its version.
    semantic_rule_id: str
    semantic_rule_version: str

    #: The contract the statement was expressed under.
    semantic_contract_version: str

    #: The three policy versions that identify the whole upstream chain:
    #: how evidence was resolved into entities, how facts were built from
    #: entities, and how meaning was interpreted from facts.
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str

    #: The support chain, as identity rather than as content: a
    #: fingerprint over the supporting fact keys, and how many there were.
    support_fingerprint: str
    support_count: int

    def __post_init__(self) -> None:
        required = {
            "content_checksum": self.content_checksum,
            "semantic_rule_id": self.semantic_rule_id,
            "semantic_rule_version": self.semantic_rule_version,
            "semantic_contract_version": self.semantic_contract_version,
            "resolution_policy_version": self.resolution_policy_version,
            "fact_policy_version": self.fact_policy_version,
            "semantic_policy_version": self.semantic_policy_version,
            "support_fingerprint": self.support_fingerprint,
        }

        missing = sorted(name for name, value in required.items() if not value)

        if missing:
            raise InvalidReviewSnapshotError(
                "A review snapshot must identify what was reviewed; "
                f"missing: {', '.join(missing)}."
            )

        if self.support_count < 0:
            raise InvalidReviewSnapshotError(
                "A support count cannot be negative."
            )

    @property
    def rule_identity(self) -> str:
        """``rated_power_from_…@1.0`` - what interpreted the statement."""

        return f"{self.semantic_rule_id}@{self.semantic_rule_version}"

    @property
    def pipeline_identity(self) -> tuple[str, str, str, str]:
        """
        The whole upstream chain, as one comparable value.

        Two statements sharing this share the rules and the bytes they
        were derived under. It is what ``review_applicability`` compares
        to tell "the pipeline moved on" from "the pipeline is gone".
        """

        return (
            self.content_checksum,
            self.resolution_policy_version,
            self.fact_policy_version,
            self.semantic_policy_version,
        )


def fingerprint_support(supporting_fact_keys: tuple[str, ...]) -> str:
    """
    A deterministic fingerprint over a statement's supporting fact keys.

    Sorted before hashing, so two orderings of the same support compare
    equal - the *set* of facts is the identity, and the order the backend
    happened to return them in is not.

    Strictly speaking this is redundant for detection: ``statement_key``
    already hashes the fact source, so a matching key implies matching
    support. It is recorded anyway, as an integrity check - a matching key
    with differing support would mean the identity of a statement had
    stopped meaning what it claims, and that is worth surfacing loudly
    rather than trusting silently.
    """

    # A separator that cannot occur inside a fact key, so ("ab", "c") and
    # ("a", "bc") cannot fingerprint alike.
    joined = "\x1f".join(sorted(supporting_fact_keys))

    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
