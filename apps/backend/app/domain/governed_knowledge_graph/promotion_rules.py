"""
What may become governed knowledge, and what may not.

**One rule admits knowledge into the graph:**

```
    current review decision == APPROVED
        AND
    review applicability == APPLIES
        AND
    the statement type has a governed edge kind
        AND
    both endpoint entities have governed node kinds
        ↓
    PROMOTE
```

Everything else is refused, with a stated reason. There is no implicit
behaviour, no "promote anyway with a lower confidence", and no threshold:
a statement is either governed engineering knowledge or it is not.

---

## Why each refusal

| Condition | Refusal | Why |
|---|---|---|
| Nobody has reviewed it | `NOT_REVIEWED` | An unreviewed statement is pipeline output, not governed knowledge. Admitting it would make the graph exactly what ADR-0004 forbids. |
| Reviewed `REJECTED` | `REVIEW_REJECTED` | An engineer looked and did not sustain it. |
| Reviewed `NEEDS_INVESTIGATION` | `REVIEW_INCONCLUSIVE` | An engineer looked and could not yet decide. Not a weak approval. |
| `REQUIRES_REVALIDATION` | `REVIEW_STALE` | The judgement was passed on a statement derived under different rules or bytes. Carrying it forward would promote knowledge on the strength of an opinion about something else. |
| `ORPHANED` | `REVIEW_ORPHANED` | There is no current interpretation to compare the judgement against. |
| Unknown statement type | `UNGOVERNED_STATEMENT_TYPE` | No edge kind exists for it. Inventing one would be inventing ontology. |
| Unknown entity type | `UNGOVERNED_ENTITY_TYPE` | No node kind exists for it. |
| Endpoint kinds wrong | `INVALID_ENDPOINTS` | A rated power relates an asset to a quantity. The reverse would let the graph answer "what is the rated power of 630 kVA?". |

## Everything here is pure

The rule takes a description of a candidate - values already read from
elsewhere - and returns a decision. No repository, no request, no clock,
no import of the semantics or review contexts. That is what lets every
promotion rule be tested without a pipeline and without a reviewer, and
what keeps this context from depending on the ones it projects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
    edge_kind_for_statement_type,
    endpoints_valid,
    node_kind_for_entity_type,
)

PROMOTION_CONTRACT_VERSION = "1.0"
"""
The version of the promotion rules themselves.

Recorded on every generation, so "which rules admitted this knowledge?"
is answerable. Bumped when a rule changes what would be promoted from
identical inputs - never for a refactor.
"""

#: The decision values a review must carry. Plain strings rather than the
#: Human Review enums, because this context does not import that one -
#: see the module docstring on purity. The values are asserted against
#: the real enums by a test, so a rename upstream fails loudly here.
APPROVED_DECISION = "approved"

APPLIES_APPLICABILITY = "applies"


class PromotionRefusal(str, Enum):
    """Why a candidate did not become graph knowledge."""

    NOT_REVIEWED = "not_reviewed"
    REVIEW_REJECTED = "review_rejected"
    REVIEW_INCONCLUSIVE = "review_inconclusive"
    REVIEW_STALE = "review_stale"
    REVIEW_ORPHANED = "review_orphaned"
    UNGOVERNED_STATEMENT_TYPE = "ungoverned_statement_type"
    UNGOVERNED_ENTITY_TYPE = "ungoverned_entity_type"
    INVALID_ENDPOINTS = "invalid_endpoints"


@dataclass(frozen=True, slots=True)
class PromotionCandidate:
    """
    One semantic statement, with everything the rule needs to judge it.

    A **description**, assembled by the application service from the
    semantics and review contexts. Deliberately not the statement and not
    the review: this context reads their identity, never their objects.

    ``decision`` and ``applicability`` are ``None`` when nobody has
    reviewed the statement - a state, not a decision, and never conflated
    with one.
    """

    statement_key: str
    statement_type: str
    subject_entity_key: str
    subject_entity_type: str
    object_entity_key: str
    object_entity_type: str
    decision: str | None
    applicability: str | None


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """
    What the rule decided, and the kinds it resolved on the way.

    ``promote`` and ``refusal`` are mutually exclusive: a decision is
    never partially made, and there is no state a careless caller could
    read as "good enough".
    """

    promote: bool
    refusal: PromotionRefusal | None
    edge_kind: GraphEdgeKind | None = None
    subject_kind: GraphNodeKind | None = None
    object_kind: GraphNodeKind | None = None

    @classmethod
    def promoted(
        cls,
        edge_kind: GraphEdgeKind,
        subject_kind: GraphNodeKind,
        object_kind: GraphNodeKind,
    ) -> "PromotionDecision":
        return cls(
            promote=True,
            refusal=None,
            edge_kind=edge_kind,
            subject_kind=subject_kind,
            object_kind=object_kind,
        )

    @classmethod
    def refused(cls, refusal: PromotionRefusal) -> "PromotionDecision":
        return cls(promote=False, refusal=refusal)


#: Which refusals mean "an engineer's judgement stopped sustaining this",
#: as opposed to "it was never promotable in the first place".
#:
#: Only the first group retires knowledge that is already in the graph.
#: The second group describes candidates that never entered it, so there
#: is nothing to retire.
RETIRING_REFUSALS = frozenset(
    {
        PromotionRefusal.NOT_REVIEWED,
        PromotionRefusal.REVIEW_REJECTED,
        PromotionRefusal.REVIEW_INCONCLUSIVE,
        PromotionRefusal.REVIEW_STALE,
        PromotionRefusal.REVIEW_ORPHANED,
    }
)


def evaluate(candidate: PromotionCandidate) -> PromotionDecision:
    """
    Applies the promotion rule. Total over its input.

    Checked in this order deliberately: **governance first, then
    vocabulary**. A rejected statement of an ungovernable type is refused
    as rejected, because that is the more useful thing to tell somebody -
    the reviewer's judgement is the fact that matters, and the vocabulary
    gap is this platform's problem rather than theirs.
    """

    if candidate.decision is None or candidate.applicability is None:
        return PromotionDecision.refused(PromotionRefusal.NOT_REVIEWED)

    if candidate.decision != APPROVED_DECISION:
        return PromotionDecision.refused(_refusal_for(candidate.decision))

    if candidate.applicability != APPLIES_APPLICABILITY:
        return PromotionDecision.refused(
            _refusal_for_applicability(candidate.applicability)
        )

    edge_kind = edge_kind_for_statement_type(candidate.statement_type)

    if edge_kind is None:
        return PromotionDecision.refused(
            PromotionRefusal.UNGOVERNED_STATEMENT_TYPE
        )

    subject_kind = node_kind_for_entity_type(candidate.subject_entity_type)
    object_kind = node_kind_for_entity_type(candidate.object_entity_type)

    if subject_kind is None or object_kind is None:
        return PromotionDecision.refused(
            PromotionRefusal.UNGOVERNED_ENTITY_TYPE
        )

    if not endpoints_valid(edge_kind, subject_kind, object_kind):
        return PromotionDecision.refused(PromotionRefusal.INVALID_ENDPOINTS)

    return PromotionDecision.promoted(edge_kind, subject_kind, object_kind)


def _refusal_for(decision: str) -> PromotionRefusal:
    if decision == "rejected":
        return PromotionRefusal.REVIEW_REJECTED

    if decision == "needs_investigation":
        return PromotionRefusal.REVIEW_INCONCLUSIVE

    # A decision this context does not recognise is refused rather than
    # guessed at. A new decision value upstream must be a deliberate
    # change here, not a silent promotion.
    return PromotionRefusal.REVIEW_INCONCLUSIVE


def _refusal_for_applicability(applicability: str) -> PromotionRefusal:
    if applicability == "orphaned":
        return PromotionRefusal.REVIEW_ORPHANED

    return PromotionRefusal.REVIEW_STALE
