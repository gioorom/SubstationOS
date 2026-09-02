"""
The semantic rule catalogue (Milestone 30.1) - the **one** authoritative
statement of what an engineering association is allowed to mean.

Each rule declares:

| Property | Answers |
|---|---|
| supported fact predicate | which associations it may read |
| required evidence types | what the associated quantity must be |
| validation policy | when the mapping may be asserted |
| resulting statement type | what meaning it produces |
| versioning | which rule, at which version, produced a statement |

**No executable engineering rule exists outside this module.** An
architecture test asserts nothing else in the context constructs a
``SemanticRule``, because a rule somewhere else would be an engineering
judgement nobody could find, version or review - while every stored
statement cites a rule version.

## Why the required evidence type is a string

``EvidenceType`` lives in the Engineering Evidence context, and this
layer is not permitted to depend on it: **only Engineering Facts cross
the boundary**. The evidence type is available *on the fact's support*,
where Milestone 29.2 recorded it, and this catalogue names the one it
requires as a declared string.

That is the same discipline the pipeline already uses where two contexts
must agree on a vocabulary without coupling - ``ClassifiedFormat``
against ``DocumentFormat``, the evidence failure codes against
ingestion's. The value is asserted equal to ``EvidenceType.POWER_VALUE``
by test, so the two cannot drift apart while the production dependency
stays absent.

## Why the location rule is not a proximity rule

`IS_LOCATED_IN` is the first rule here whose object is not a quantity,
and the first that could be mistaken for topology. It is not.

Its supporting fact is `HAS_LOCATION_ASPECT`, and **this rule does not
ask how that fact was constructed**. It cannot: only facts cross this
boundary, and a rule that read extraction mechanics would be assigning
meaning to how a drawing was typeset rather than to what it said. The
governed reading is the same either way - IEC 81346 assigns ``+`` to the
location aspect, so a designation written with one is designated in the
context of that location.

What keeps the rule out of proximity territory is therefore the fact
catalogue, where it belongs. Both rules that can produce this predicate
are exact: one requires the two observations to come from a single
token, the other requires exactly one designation and exactly one
location on a line. Neither has a window to widen or a threshold to
tune, and neither will choose between candidates. EPIC 32.P2 added the
second because the first, alone, could not reach a single real drawing
in this repository.

The caution that follows is unchanged and still controlling:
`IS_LOCATED_IN` asserts the reference-designation association and
nothing else. Not containment, not connectivity, not bay membership, not
hierarchy, not geometry.

## Why power, and why only power

A `kVA` figure written beside a designation is a rating far more reliably
than a `kV` figure is: a voltage beside a transformer may be its rated
voltage, a test voltage, an insulation level, or the voltage of the
busbar it connects to. The association alone does not distinguish them,
so no voltage rule ships.

Power is not free of that problem either - a data sheet can list a
throughput or a loss in kVA - which is exactly why the mapping is
declared here with a version rather than assumed, and why the milestone
that measures interpretation quality matters before more rules are added.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)

# The evidence type a quantity must carry for the rated-power rule to
# apply, as it appears on a fact's support. Declared here rather than
# imported - see the module docstring - and asserted equal to
# ``EvidenceType.POWER_VALUE.value`` by test.
POWER_VALUE_EVIDENCE_TYPE = "power_value"

# The evidence type a location aspect carries on a fact's support.
# Declared as a string for the same reason, and asserted equal to
# ``EvidenceType.LOCATION_ASPECT.value`` by test.
LOCATION_ASPECT_EVIDENCE_TYPE = "location_aspect"


@dataclass(frozen=True, slots=True)
class SemanticRule:
    """
    One rule, identified and versioned.

    ``rule_id`` is a stable contract: once published it appears in stored
    statements, so renaming it is a migration rather than an edit.
    ``rule_version`` changes whenever the engineering judgement changes,
    and a bump creates a new semantic set rather than reinterpreting the
    old one.

    ``max_supporting_objects`` is the validation policy in data form.
    One, for both rules that ship: a subject associated with two power
    quantities receives no statement, because a fact carries entity keys
    rather than values - this layer cannot see whether the two figures
    agree, and reading them would mean reaching into entities, which is
    not its business. A subject written with two different location
    aspects is refused for a stricter reason: the document contradicted
    itself about where the equipment is, and choosing a side is not
    interpretation.
    """

    rule_id: str
    rule_version: str
    supported_predicate: FactPredicate
    required_evidence_types: tuple[str, ...]
    statement_type: SemanticStatementType
    max_supporting_objects: int
    description: str


RATED_POWER_RULE = SemanticRule(
    rule_id="rated_power_from_associated_power_quantity",
    rule_version="1.0",
    supported_predicate=FactPredicate.HAS_ASSOCIATED_QUANTITY,
    required_evidence_types=(POWER_VALUE_EVIDENCE_TYPE,),
    statement_type=SemanticStatementType.HAS_RATED_POWER,
    max_supporting_objects=1,
    description=(
        "A designation associated with exactly one power quantity has "
        "that quantity as its rated power. Two or more associated power "
        "quantities produce no statement: which is the rating cannot be "
        "decided from the association alone."
    ),
)

IS_LOCATED_IN_RULE = SemanticRule(
    rule_id="location_from_compound_reference_designation",
    rule_version="1.0",
    supported_predicate=FactPredicate.HAS_LOCATION_ASPECT,
    required_evidence_types=(LOCATION_ASPECT_EVIDENCE_TYPE,),
    statement_type=SemanticStatementType.IS_LOCATED_IN,
    max_supporting_objects=1,
    description=(
        "A designation the document associated with a location aspect "
        "is located in the location that aspect names. The meaning is "
        "IEC 81346's: '+E01-QA1' designates an object in the context of "
        "location '+E01', and a line reading 'MORSETTIERA -E.AM "
        "+GSH002' says the same of '-E.AM'. Which structural rule "
        "established the association is the fact catalogue's business, "
        "not this rule's. Two different location aspects for one "
        "subject produce no statement - the document disagreed with "
        "itself, and this rule does not choose."
    ),
)

SEMANTIC_RULES: tuple[SemanticRule, ...] = (
    RATED_POWER_RULE,
    IS_LOCATED_IN_RULE,
)

RULES_BY_ID: dict[str, SemanticRule] = {
    rule.rule_id: rule for rule in SEMANTIC_RULES
}


def rule_applies_to(rule: SemanticRule, predicate: FactPredicate) -> bool:
    """Whether a rule may read a fact carrying this predicate.

    A predicate the catalogue does not name is **ignored**, not refused:
    a future fact predicate this rule knows nothing about is not an
    error, it is simply not this rule's business."""

    return rule.supported_predicate is predicate


def satisfies_evidence_requirement(
    rule: SemanticRule, evidence_types: tuple[str, ...]
) -> bool:
    """
    Whether the quantity supporting a fact is of the kind the rule
    requires.

    Every supporting observation on the object side must be of a required
    type. A fact whose object support mixed a power reading with
    something else would not be a quantity this rule can interpret.
    """

    if not evidence_types:
        return False

    return all(
        evidence_type in rule.required_evidence_types
        for evidence_type in evidence_types
    )
