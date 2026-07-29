"""
The fact construction rule catalogue (Milestone 29.2) - the **one**
authoritative statement of when two entities may be associated.

## SAME_LINE_ASSOCIATION, and only that

One rule ships. A designation entity and a quantity entity may be
associated **only** when contributing observations of both occur on the
same document line - the same page, the same block, the same line index.

### Why paragraph association is not implemented

The brief for this milestone permits a paragraph-level rule *only if the
repository's evidence proves it can be conservative*. It does not.

The canonical parser makes each separately-placed run of text its own
block, so a "paragraph" in this pipeline is sometimes exactly one line
and sometimes a wrapped run of several unrelated ones - a title bar, a
column of a table, a stack of data-sheet rows. A paragraph rule would
therefore behave as a line rule on some documents and as a
several-lines-wide cartesian join on others, with nothing in the data to
tell the two apart. A rule whose strictness depends on how the parser
happened to block a page is not a deterministic rule; it is a coin flip
with a version number.

Line association has no such problem: a line is a line.

### What is deliberately not used

No token-distance scoring, no nearest-neighbour, no geometry, no
same-page association, no punctuation-based inference, no document-wide
proximity, no thresholds. Each of those would introduce a number nobody
calibrated, and the first place it would surface is an engineer disputing
a rating that was assigned by arithmetic on coordinates.

Note what this means in practice: on ``TR1 630 kVA 20/0.4 kV``, the
association is with ``630 kVA`` because that is what the extractor
observed - not because it is nearer. ``20/0.4`` is not a number this
system reads, so there is nothing to associate.

## The cardinality policy is declared, not implied

| On one line | Result |
|---|---|
| 1 designation, N quantities | N facts - declared by `ONE_SUBJECT_MANY_OBJECTS` |
| M ≥ 2 designations, ≥ 1 quantity | **no facts**, one diagnostic |
| 0 designations, or 0 quantities | nothing |

The one-to-many case is permitted **explicitly**: a data-sheet line
listing a designation and several of its ratings is a real and common
shape, and associating them says only that they appeared together.

The many-subject case is refused. ``TR1 TR2 630 kVA`` must not silently
become two facts: the line does not say which transformer the rating
belongs to, and a guess would put a rating on the wrong equipment - the
kind of error that is invisible in a graph and expensive in a substation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_entities.entity_models import EntityType
from app.domain.engineering_facts.fact_predicates import FactPredicate


class StructuralScope(str, Enum):
    """
    The structural unit within which contributing observations must
    co-occur.

    One member. Adding a second - a paragraph, a page - must be a
    deliberate act with its own justification, because each widening
    multiplies how many pairs a rule can produce.
    """

    LINE = "line"


class CardinalityPolicy(str, Enum):
    """How many entities a rule may associate on one structural unit."""

    # One subject may associate with any number of objects; two or more
    # subjects produce nothing.
    ONE_SUBJECT_MANY_OBJECTS = "one_subject_many_objects"


@dataclass(frozen=True, slots=True)
class FactConstructionRule:
    """
    One rule, identified and versioned.

    ``rule_id`` is a stable contract: once published it appears in stored
    facts, so renaming it is a migration rather than an edit.
    ``rule_version`` changes whenever the rule's behaviour changes, and a
    bump creates a new fact set rather than rewriting the old one.
    """

    rule_id: str
    rule_version: str
    predicate: FactPredicate
    subject_type: EntityType
    object_type: EntityType
    scope: StructuralScope
    cardinality: CardinalityPolicy
    description: str


SAME_LINE_ASSOCIATION_RULE = FactConstructionRule(
    rule_id="same_line_association",
    rule_version="1.0",
    predicate=FactPredicate.HAS_ASSOCIATED_QUANTITY,
    subject_type=EntityType.EQUIPMENT_DESIGNATION,
    object_type=EntityType.ENGINEERING_QUANTITY,
    scope=StructuralScope.LINE,
    cardinality=CardinalityPolicy.ONE_SUBJECT_MANY_OBJECTS,
    description=(
        "A designation entity and a quantity entity are associated when "
        "contributing observations of both occur on the same document "
        "line, and that line carries exactly one designation. Says only "
        "that they appeared together - not what the quantity is to the "
        "designation."
    ),
)

CONSTRUCTION_RULES: tuple[FactConstructionRule, ...] = (
    SAME_LINE_ASSOCIATION_RULE,
)

RULES_BY_ID: dict[str, FactConstructionRule] = {
    rule.rule_id: rule for rule in CONSTRUCTION_RULES
}
