"""
The fact construction rule catalogue (Milestone 29.2) - the **one**
authoritative statement of when two entities may be associated.

## Two rules ship

`SAME_LINE_ASSOCIATION` (Milestone 29.2) associates a designation entity
and a quantity entity **only** when contributing observations of both
occur on the same document line - the same page, the same block, the
same line index.

`COMPOUND_REFERENCE_DESIGNATION` (EPIC 32.P1) associates a designation
entity and a structural-location entity when both observations came from
**one token**: the ``+E01`` inside ``+E01-QA1``. It is the first rule in
this catalogue whose object is not a quantity, and the reason EPIC 32.2
has a structural relationship to reason about at all.

Neither rule reads a document. Both read the locations the entities
already carry on their evidence, which is why the scope vocabulary is
what it is: a rule may only be as strict as the provenance recorded at
extraction time allows.

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

    Each member is a deliberate act with its own justification, because
    each **widening** multiplies how many pairs a rule can produce. Note
    that the second member added here narrows rather than widens: a
    token is the smallest unit there is.
    """

    LINE = "line"

    #: One token. The strongest co-occurrence this pipeline can record:
    #: the two observations did not merely appear near each other, they
    #: were produced from **the same characters** - ``+E01-QA1`` yields
    #: both the designation and the location aspect inside it.
    #:
    #: This is what keeps the location rule outside the objection that
    #: sinks page- and paragraph-level association. There is no window
    #: to calibrate and no distance to threshold; the unit is one token,
    #: and a token is a token.
    TOKEN = "token"


class CardinalityPolicy(str, Enum):
    """How many entities a rule may associate on one structural unit."""

    # One subject may associate with any number of objects; two or more
    # subjects produce nothing.
    ONE_SUBJECT_MANY_OBJECTS = "one_subject_many_objects"
    # Exactly one subject and exactly one object; anything else produces
    # nothing. The policy a token-scoped rule needs, and the only one
    # that is honest there: a token that somehow yielded two subjects
    # would mean the extractor had contradicted itself, and a fact is
    # not the place to resolve that.
    ONE_SUBJECT_ONE_OBJECT = "one_subject_one_object"


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

COMPOUND_REFERENCE_DESIGNATION_RULE = FactConstructionRule(
    rule_id="compound_reference_designation",
    rule_version="1.0",
    predicate=FactPredicate.HAS_LOCATION_ASPECT,
    subject_type=EntityType.EQUIPMENT_DESIGNATION,
    object_type=EntityType.STRUCTURAL_LOCATION,
    scope=StructuralScope.TOKEN,
    cardinality=CardinalityPolicy.ONE_SUBJECT_ONE_OBJECT,
    description=(
        "A designation entity and a structural-location entity are "
        "associated when contributing observations of both were "
        "produced from the same token - which happens only for a "
        "compound IEC 81346 reference designation such as '+E01-QA1'. "
        "Says that the document wrote the one inside the other, not "
        "what that means."
    ),
)

CONSTRUCTION_RULES: tuple[FactConstructionRule, ...] = (
    SAME_LINE_ASSOCIATION_RULE,
    COMPOUND_REFERENCE_DESIGNATION_RULE,
)

RULES_BY_ID: dict[str, FactConstructionRule] = {
    rule.rule_id: rule for rule in CONSTRUCTION_RULES
}
