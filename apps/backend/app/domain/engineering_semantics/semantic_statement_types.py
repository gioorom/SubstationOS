"""
The semantic statement vocabulary (Milestone 30.1, extended by EPIC
32.P1) - the **one closed list** of engineering meanings this system can
assign.

Two members. Each arrived with the evidence that justifies it, and
neither was added in anticipation of a milestone that wanted it.

## Why this layer exists at all

Every layer beneath it was built to say *less* than it might have:

| Layer | Says |
|---|---|
| Evidence | "I observed `630 kVA` here." |
| Entity | "These observations refer to one quantity." |
| Fact | "This designation and this quantity are structurally associated." |
| **Semantic statement** | "This designation **has rated power** this quantity." |

The first three deliberately assign no engineering meaning. This is where
meaning is assigned - and it is assigned **only** where a declared,
versioned rule says so. `HAS_ASSOCIATED_QUANTITY` becomes
`HAS_RATED_POWER` because ``semantic_rules`` declares that mapping, and
for no other reason.

## Deliberately absent

`HAS_NOMINAL_VOLTAGE`, `HAS_NOMINAL_CURRENT`, `HAS_CABLE_SECTION`,
`CONNECTED_TO`, `PROTECTS`, `SUPPLIES`, `IS_TRANSFORMER`, `IS_BREAKER`,
`IS_PRIMARY_EQUIPMENT`.

`CONNECTED_TO` is the one worth naming twice. `IS_LOCATED_IN` may look
like a step towards it and is not: two objects sharing a location are in
the same place, which is not a circuit. Connectivity needs evidence that
says two objects are joined, and no rule in this repository observes
that.

The voltage and current ones look like the natural next step and are not:
a voltage beside a designation may be a rated voltage, a test voltage, an
insulation level or the voltage of the busbar the equipment connects to,
and the association alone does not say which. Power is being interpreted
first precisely because it is the least ambiguous of them - a `kVA`
figure beside a designation is a rating far more reliably than a `kV`
figure is. Even that is a rule somebody should review, which is why it is
declared in a catalogue with a version rather than assumed here.

The classification predicates (`IS_TRANSFORMER`, …) are a different kind
of claim altogether and need a governed equipment vocabulary that does
not exist.

An architecture test asserts this enum stays closed and that nothing else
in the context declares a statement vocabulary.
"""

from __future__ import annotations

from enum import Enum


class SemanticStatementType(str, Enum):
    """Every engineering meaning this system can assign."""

    # "The quantity associated with this designation is its rated
    # power." Assigned only where the supporting fact's object is a
    # power observation and exactly one such quantity is associated.
    HAS_RATED_POWER = "has_rated_power"

    # "This equipment is located in this structural location." Assigned
    # only where the supporting fact is a `HAS_LOCATION_ASPECT` reading
    # of one compound IEC 81346 reference designation.
    #
    # The meaning comes from the standard, not from this platform:
    # IEC 81346-1 assigns ``+`` to the location aspect, so ``+E01-QA1``
    # designates the object ``-QA1`` **in the context of location
    # ``+E01``**. That is a documented, published reading of a syntax the
    # document chose to use - not a guess about what two nearby strings
    # might have to do with each other.
    #
    # It says nothing about what kind of location ``+E01`` is, nothing
    # about what is connected to what, and nothing about whether two
    # objects in one location are electrically related. Those are
    # different claims needing different evidence.
    IS_LOCATED_IN = "is_located_in"
