"""
Whether a review still applies after the pipeline has moved on.

This is the milestone's hardest question, and the answer is **derived
from identity the pipeline already produces**, not invented here.

---

## The property everything rests on

``EngineeringSemanticStatement.statement_key`` is a SHA-256 over the
document, the exact fact source, the triple, and the rule and contract
versions. Therefore:

- **Nothing changed** → the re-run reproduces the *same* key. The review
  is still about the statement in front of the engineer today.
- **Anything changed** - the bytes, the entity resolution, the fact
  construction, the semantic rule, the contract - → the key is
  *different*. A statement derived differently can never silently inherit
  a judgement passed on the old one.

So the question "does this review still apply?" reduces to a lookup, and
a review is never matched to a statement by resemblance.

## The lifecycle

```
                    record a review
                          │
                          ▼
                       APPLIES ────────────── the key is in the current set
                          │
        pipeline re-runs  │
                          ▼
           ┌──────────────┴───────────────┐
           │                              │
   key still present               key absent
           │                              │
        APPLIES              ┌────────────┴────────────┐
                             │                         │
                  a current set exists         no current set
                  under a different            exists at all
                  upstream identity                    │
                             │                         │
                 REQUIRES_REVALIDATION            ORPHANED
```

Three states, and each says something an engineer would act on
differently:

| State | Means | What an engineer does |
|---|---|---|
| ``APPLIES`` | The reviewed statement is in the document's current interpretation, under the identity it was reviewed under. | Nothing. |
| ``REQUIRES_REVALIDATION`` | The document has been re-interpreted under different bytes or different rules. The judgement may well still hold - and only a human may say so. | Review the current statement. |
| ``ORPHANED`` | There is no current interpretation to compare against: the semantic stage has not been run since, or its set was removed. | Re-run the pipeline, then look again. |

**A review is never discarded, in any of them.** `REQUIRES_REVALIDATION`
does not delete, hide or weaken the record; it marks it, which is
precisely what the EPIC that introduced this context required. The old
judgement stays readable, with the identity it was passed under, forever.

## What is deliberately *not* modelled

There is no "the review was migrated to the new statement" state. Moving
a judgement onto an artefact derived under different rules is exactly the
inference no machine may make here: it would silently attribute to an
engineer an opinion about something they never saw.

Everything in this module is a pure function of a snapshot and a
description of the current pipeline state. No repository, no request, no
clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.human_review.review_snapshot import ReviewSnapshot


class ReviewApplicability(str, Enum):
    """Whether a recorded judgement still describes today's pipeline."""

    APPLIES = "applies"
    REQUIRES_REVALIDATION = "requires_revalidation"
    ORPHANED = "orphaned"


@dataclass(frozen=True, slots=True)
class CurrentPipelineState:
    """
    What the document's semantic interpretation looks like *now*.

    A deliberately thin description rather than the semantic set itself:
    this context may not import the engineering domain, and everything the
    decision needs is identity. The application service reads the set and
    fills this in - an architecture test asserts the direction.

    ``exists`` is ``False`` when the semantic stage has never run for this
    document, or its set is gone. The version fields are then meaningless
    and are ignored.
    """

    exists: bool
    target_key_present: bool
    content_checksum: str | None = None
    resolution_policy_version: str | None = None
    fact_policy_version: str | None = None
    semantic_policy_version: str | None = None

    #: The support fingerprint of the *current* statement, when the key is
    #: present. Used only for the integrity check below.
    support_fingerprint: str | None = None

    @property
    def pipeline_identity(self) -> tuple[str, str, str, str] | None:
        if not self.exists:
            return None

        return (
            self.content_checksum or "",
            self.resolution_policy_version or "",
            self.fact_policy_version or "",
            self.semantic_policy_version or "",
        )

    @classmethod
    def absent(cls) -> "CurrentPipelineState":
        return cls(exists=False, target_key_present=False)


def evaluate(
    snapshot: ReviewSnapshot, current: CurrentPipelineState
) -> ReviewApplicability:
    """
    Whether the review whose snapshot this is still applies.

    Total over the inputs: every combination resolves to one of three
    states, and none of them is "unknown".
    """

    if not current.exists:
        return ReviewApplicability.ORPHANED

    if current.target_key_present:
        return ReviewApplicability.APPLIES

    # The set exists and this statement is not in it. The key is a hash of
    # the rules and the source, so its absence means the document was
    # re-interpreted under something different - which is a judgement to
    # re-confirm, never one to discard.
    return ReviewApplicability.REQUIRES_REVALIDATION


def has_integrity(
    snapshot: ReviewSnapshot, current: CurrentPipelineState
) -> bool:
    """
    Whether a statement that kept its key also kept its support.

    ``statement_key`` already hashes the fact source, so this should be
    impossible - which is why it is checked. A statement whose key matched
    while its support differed would mean the identity of an engineering
    artefact had stopped meaning what it claims, and that must surface
    loudly rather than be trusted quietly.

    Vacuously true when the key is absent (there is nothing to compare) or
    when the current support fingerprint was not supplied.
    """

    if not current.target_key_present:
        return True

    if current.support_fingerprint is None:
        return True

    return current.support_fingerprint == snapshot.support_fingerprint
