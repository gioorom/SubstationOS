"""
The semantic statement vocabulary (Milestone 30.1) - the **one closed
list** of engineering meanings this system can assign.

Exactly one member. That is the design, not a placeholder.

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
`BELONGS_TO`, `IS_PRIMARY_EQUIPMENT`.

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
