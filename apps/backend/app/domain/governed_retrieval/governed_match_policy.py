"""
How governed results are ordered, and why it is not a score.

The legacy Structured Retrieval ranked candidates by a **weighted sum**:
100 for an exact canonical id, 80 for a normalized identifier, 10 per
lexical token, and so on. That number was documented, but it was still a
number - and once results carry one, somebody eventually reads it as a
measure of how true the knowledge is.

Governed retrieval ranks by **which strategy matched**, which is a fact
about the comparison rather than a quantity about the knowledge. The
table below is a total order over
:class:`~app.domain.governed_retrieval.governed_retrieval_vocabulary.GovernedMatchStrategy`,
and every result exposes its strategy, so the ordering is readable
without consulting this module.

---

## The order, and the reasoning behind it

| Rank | Strategy | Why it outranks the next |
|---:|---|---|
| 0 | `GOVERNED_IDENTITY` | The caller named the object. Nothing is more specific than that. |
| 1 | `EXACT_DESIGNATION` | The governed label *is* the designation, character for character. |
| 2 | `NORMALIZED_DESIGNATION` | Equal once case and whitespace are folded - a difference in how it was typed, not in what it names. |
| 3 | `NORMALIZED_VALUE` | Equal to the value **the pipeline itself normalized**, which is governed output rather than a fold retrieval invented. |
| 4 | `CANONICAL_DESIGNATION` | Equal only after separators are dropped: the weakest equality, and the one most likely to join two things an engineer would distinguish. |
| 5 | `RELATIONSHIP_TRAVERSAL` | Reached *through* the asset the query resolved, so it is one governed step away from what was asked. |
| 6 | `EDGE_KIND` | Selected by kind: correct, but the query named no individual object. |
| 7 | `DOCUMENT_SCOPE` | Selected by origin: the broadest selection this context performs. |

Ranks 2 and 3 are a deliberate pair. Both are "equal after folding", and
the normalized *value* ranks below the normalized *label* because the
label is what a drawing shows an engineer, while the normalized value is
a derived field - when they disagree, the one on the drawing is the one
the engineer meant.

## Ties

Rank alone never decides an order. The full sort key is

```
(strategy rank, primary label, secondary label, governed identity)
```

with the labels folded by ``normalize_designation`` so ordering does not
depend on how a designation happened to be capitalised, and the governed
identity - a SHA-256 of governed keys - as the final, always-present
tie-breaker. Nothing in the key depends on insertion order, on a
database's default sort, or on a clock.
"""

from __future__ import annotations

from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchStrategy,
)

#: Bumped whenever a rank changes or a strategy is added. Echoed on
#: every result's diagnostics, so a caller can tell which policy ordered
#: a given page.
GOVERNED_MATCHING_POLICY_VERSION = "1.0"


#: Lower sorts first. Total over ``GovernedMatchStrategy`` - a strategy
#: missing from this table would be a result nobody could order, so the
#: completeness is asserted by a test rather than assumed.
STRATEGY_PRECEDENCE: dict[GovernedMatchStrategy, int] = {
    GovernedMatchStrategy.GOVERNED_IDENTITY: 0,
    GovernedMatchStrategy.EXACT_DESIGNATION: 1,
    GovernedMatchStrategy.NORMALIZED_DESIGNATION: 2,
    GovernedMatchStrategy.NORMALIZED_VALUE: 3,
    GovernedMatchStrategy.CANONICAL_DESIGNATION: 4,
    GovernedMatchStrategy.RELATIONSHIP_TRAVERSAL: 5,
    GovernedMatchStrategy.EDGE_KIND: 6,
    GovernedMatchStrategy.DOCUMENT_SCOPE: 7,
}


#: The order designation strategies are attempted in, strongest first.
#: A node matches under the first strategy that holds and is reported
#: under that one only - "why did this match?" has one answer.
DESIGNATION_STRATEGY_ORDER: tuple[GovernedMatchStrategy, ...] = (
    GovernedMatchStrategy.EXACT_DESIGNATION,
    GovernedMatchStrategy.NORMALIZED_DESIGNATION,
    GovernedMatchStrategy.NORMALIZED_VALUE,
    GovernedMatchStrategy.CANONICAL_DESIGNATION,
)


def precedence_of(strategy: GovernedMatchStrategy) -> int:
    """The rank of one strategy. Total: every member has one."""

    return STRATEGY_PRECEDENCE[strategy]
