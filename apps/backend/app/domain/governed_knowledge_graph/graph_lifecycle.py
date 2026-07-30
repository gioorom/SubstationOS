"""
What happens to governed knowledge when its authorisation stops holding.

The EPIC that introduced this context offered four strategies - remove,
disable, historical, superseded - and required one to be chosen
explicitly. **Historical is chosen**, with a recorded reason.

---

## Why historical, and not the other three

- **Remove** destroys the record of what the platform once asserted. An
  engineering system that silently forgets having claimed something
  cannot answer "what did the graph say when we ordered that
  transformer?", which is precisely the question an audit asks.
- **Disable** is a flag with no stated cause. Six months later nobody can
  tell a judgement that was reversed from one the pipeline outran.
- **Superseded** implies something replaced it. Usually nothing has: a
  rule version bump retires knowledge and produces no replacement until
  an engineer reviews the newly-derived statement.
- **Historical** says the true thing: this *was* governed knowledge, it
  is no longer current, and here is why.

The reason is carried separately (`GraphRetirementReason`) rather than
folded into the state, so "how much knowledge did the last rule change
retire?" is answerable without reading prose.

## The lifecycle

```
                    promote
                       │
                       ▼
                    ACTIVE ──────────────── answers queries
                       │
     authorisation stops holding
                       │
                       ▼
                  HISTORICAL ─────────────  excluded from queries,
                       ▲                    still readable with provenance
                       │
                  re-approved
                       │
                    ACTIVE
```

`REMOVED` is reachable only through a **rebuild**, and means something
different: the recomputation found no promotable source for this identity
at all. `HISTORICAL` says *we know why this stopped being current*;
`REMOVED` says *nothing produces this any more*.

**Nothing is physically deleted by a retirement.** A rebuild is the only
operation that discards rows, and it discards them by recomputing the
whole projection - which is safe precisely because the graph is derived.

## Never silently stale

There is no path by which knowledge whose review stopped being
`APPROVED + APPLIES` remains `ACTIVE`. Promotion computes the desired
state of every candidate it visits and retires what no longer qualifies;
a rebuild does the same for the whole graph. Two tests assert it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class GraphObjectState(str, Enum):
    """
    Where a node or an edge stands.

    ``created`` is deliberately **not** a member: it is an event, not a
    state. An object that has been created is `ACTIVE`, and modelling
    creation as a state would leave a value that nothing transitions out
    of and no query excludes.
    """

    #: Current governed knowledge. The only state queries return by
    #: default.
    ACTIVE = "active"

    #: Was governed knowledge; its authorisation no longer holds. Still
    #: readable, with its provenance and the reason it was retired.
    HISTORICAL = "historical"

    #: A rebuild found no promotable source for this identity. Retained
    #: as a tombstone rather than dropped, so the graph can still say it
    #: once asserted this.
    REMOVED = "removed"


class GraphRetirementReason(str, Enum):
    """
    Why knowledge stopped being current.

    A closed catalogue, so the question is aggregatable: "what did the
    rule change cost us?" has an answer that can be counted rather than
    read.
    """

    #: An engineer recorded a later judgement that is not an approval.
    REVIEW_REVERSED = "review_reversed"

    #: The pipeline was re-run under different bytes or rules, and the
    #: reviewed statement is not in the new interpretation. The judgement
    #: may still hold - only a human may say so.
    REQUIRES_REVALIDATION = "requires_revalidation"

    #: There is no current interpretation to compare the review against.
    ORPHANED = "orphaned"

    #: The statement is no longer promotable for a reason above, found
    #: while recomputing the whole graph rather than while visiting one
    #: candidate.
    REBUILD_RECONCILIATION = "rebuild_reconciliation"

    #: A node whose every edge has been retired. A node exists to be an
    #: endpoint of governed relationships; one with none represents
    #: nothing current.
    NO_REMAINING_RELATIONSHIPS = "no_remaining_relationships"


@dataclass(frozen=True, slots=True)
class GraphRetirement:
    """
    The record of one retirement.

    Carried on the object rather than in a side table: "why is this not
    current?" must be answerable from the thing itself, without a join
    somebody might forget.
    """

    reason: GraphRetirementReason
    retired_at: datetime

    def describe(self) -> str:
        return f"{self.reason.value} at {self.retired_at.isoformat()}"


def state_for_promotion() -> GraphObjectState:
    """Newly promoted knowledge is current. There is no other option."""

    return GraphObjectState.ACTIVE


def is_queryable(state: GraphObjectState) -> bool:
    """
    Whether an object answers queries.

    The single definition, used by the repository and by the query
    service. Two definitions of "current" would eventually disagree, and
    the disagreement would be invisible.
    """

    return state is GraphObjectState.ACTIVE
