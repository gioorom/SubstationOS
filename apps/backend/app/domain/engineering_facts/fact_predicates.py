"""
The predicate vocabulary (Milestone 29.2) - the **one closed list** of
things a fact is allowed to say.

Exactly one member. That is not a placeholder; it is the whole design.

## Why `HAS_ASSOCIATED_QUANTITY` and nothing else

A construction rule can prove that a designation and a quantity appeared
together in a declared structural position. It cannot prove *what the
quantity is to the designation*. So the predicate says only what was
proven:

| Allowed | Not allowed |
|---|---|
| `TR1 HAS_ASSOCIATED_QUANTITY 630 kVA` | `TR1 HAS_RATED_POWER 630 kVA` |

The second sentence claims the quantity is the equipment's rated power.
Nothing in this pipeline establishes that. It would need a semantic rule
somebody reviewed, and it would need to survive being wrong - a
transformer data sheet listing a *test* voltage beside a designation
would become a rated voltage in the graph, and no engineer reading the
answer would be able to see why.

The quantity's evidence type - voltage, current, power, cable section -
remains reachable through the fact's support, so a later milestone has
everything it needs to promote a role. It must do so with its own rule,
its own version and its own evaluation. Reading the evidence type as a
predicate here would be that promotion happening by accident.

## Deliberately absent

`HAS_VOLTAGE`, `HAS_CURRENT`, `HAS_POWER`, `HAS_CABLE_SECTION`,
`CONNECTED_TO`, `PROTECTS`, `FEEDS`, `BELONGS_TO`, `IS_A`. The first four
are property roles this layer cannot prove; the last five are topology
and classification, which are not even this layer's subject matter.

An architecture test asserts this enum stays closed and that no other
module declares a predicate.
"""

from __future__ import annotations

from enum import Enum


class FactPredicate(str, Enum):
    """Everything a fact may assert."""

    # "These two resolved entities satisfied a declared structural
    # association rule." Nothing about roles, properties or topology.
    HAS_ASSOCIATED_QUANTITY = "has_associated_quantity"

    # "This designation was written with this location aspect inside
    # it." The structural reading of one compound IEC 81346 reference
    # designation - ``+E01-QA1`` carries ``+E01``.
    #
    # Deliberately not ``IS_LOCATED_IN``. This layer records what the
    # document *wrote*; that the equipment is therefore located there is
    # a meaning, and meanings are assigned one layer up by a versioned
    # rule an engineer reviews. The same discipline that keeps
    # ``HAS_ASSOCIATED_QUANTITY`` from being ``HAS_RATED_POWER``.
    HAS_LOCATION_ASPECT = "has_location_aspect"
