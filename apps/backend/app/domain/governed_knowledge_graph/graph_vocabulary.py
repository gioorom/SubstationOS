"""
What the governed graph is allowed to contain.

Two node kinds and one edge kind. That is not an oversight, and it is not
a placeholder: **it is exactly what governed engineering semantics
currently produces**, and the graph may contain nothing else.

---

## Why the catalogue is this small

The EPIC that introduced this context listed nine candidate concepts -
Asset, Designation, Quantity, Voltage, Protection, Connection, Function,
Location, Relationship - and then constrained them:

> Only introduce concepts that already exist in governed semantics.
> Do not invent engineering ontology.

The second instruction decides the first. Today the deterministic
pipeline produces:

| Upstream | Values |
|---|---|
| ``EntityType`` | ``equipment_designation``, ``engineering_quantity`` |
| ``SemanticStatementType`` | ``has_rated_power`` |

So the graph can express an asset identified by a designation, a
quantity, and the rated-power relationship between them. **Nothing
else.**

### What is deliberately absent, and what each would need

| Concept | Why it is not here |
|---|---|
| Voltage | Voltage *evidence* exists, and `engineering_semantics` deliberately refuses to interpret it: an associated voltage may be rated, test, insulation or busbar voltage, and the association does not say which. A `Voltage` node would assert a meaning no rule has assigned. |
| Protection | No evidence type, no entity type, no statement type. |
| Connection | Would require a topology statement type. `HAS_ASSOCIATED_QUANTITY` is a same-line association, not a connection. |
| Function | Would require a classification vocabulary and a rule that assigns it. |
| Location | Source *locations* exist (page, line, span) and are provenance, not engineering knowledge. A substation-location concept has no upstream. |

Each becomes promotable the day a semantic rule produces it, and the
change is one member here plus one entry in the mapping below. Adding
them now would be four node kinds no promotion can create, no query can
return and no test can cover - the shape of the model implying knowledge
the system does not have.
"""

from __future__ import annotations

from enum import Enum


class GraphNodeKind(str, Enum):
    """
    The kinds of thing the governed graph holds.

    Deliberately **not** `Transformer`, `Breaker` or `Cable`. Deciding
    that ``TR1`` names a transformer is a classification, and the entity
    context refuses to make it for exactly the reason this context
    inherits: a classification needs a rule somebody reviewed and a
    vocabulary somebody governs.
    """

    #: Something the documents designate - ``TR1``, ``Q1``. Promoted from
    #: an `equipment_designation` entity. Says what it is *called*, never
    #: what it *is*.
    ENGINEERING_ASSET = "engineering_asset"

    #: A magnitude with a unit - ``630 kVA``. Promoted from an
    #: `engineering_quantity` entity.
    ENGINEERING_QUANTITY = "engineering_quantity"


class GraphEdgeKind(str, Enum):
    """
    The governed engineering relationships.

    One member, from the one semantic statement type that exists. An edge
    kind is added here only when a semantic rule produces the statement
    it would come from - never in anticipation.
    """

    #: "This asset's rated power is this quantity." Promoted from a
    #: `has_rated_power` statement that an engineer approved.
    HAS_RATED_POWER = "has_rated_power"


#: Which entity type becomes which node kind.
#:
#: The **only** way a node comes into existence. An entity type absent
#: from this table cannot be promoted, which is what keeps the graph from
#: acquiring concepts the pipeline never produced.
NODE_KIND_FOR_ENTITY_TYPE: dict[str, GraphNodeKind] = {
    "equipment_designation": GraphNodeKind.ENGINEERING_ASSET,
    "engineering_quantity": GraphNodeKind.ENGINEERING_QUANTITY,
}


#: Which semantic statement type becomes which edge kind.
#:
#: The **only** way an edge comes into existence.
EDGE_KIND_FOR_STATEMENT_TYPE: dict[str, GraphEdgeKind] = {
    "has_rated_power": GraphEdgeKind.HAS_RATED_POWER,
}


#: What each edge kind requires of its endpoints.
#:
#: A rated power relates an asset to a quantity, in that direction. The
#: constraint is checked at promotion, so an edge whose endpoints are the
#: wrong kinds is refused rather than stored - a graph that answered
#: "what is the rated power of 630 kVA?" would be worse than one that
#: answered nothing.
EDGE_ENDPOINT_KINDS: dict[
    GraphEdgeKind, tuple[GraphNodeKind, GraphNodeKind]
] = {
    GraphEdgeKind.HAS_RATED_POWER: (
        GraphNodeKind.ENGINEERING_ASSET,
        GraphNodeKind.ENGINEERING_QUANTITY,
    ),
}


def node_kind_for_entity_type(entity_type: str) -> GraphNodeKind | None:
    """The node kind an entity promotes to, or ``None`` if it cannot."""

    return NODE_KIND_FOR_ENTITY_TYPE.get(entity_type)


def edge_kind_for_statement_type(
    statement_type: str,
) -> GraphEdgeKind | None:
    """The edge kind a statement promotes to, or ``None`` if it cannot."""

    return EDGE_KIND_FOR_STATEMENT_TYPE.get(statement_type)


def endpoints_valid(
    edge_kind: GraphEdgeKind,
    subject_kind: GraphNodeKind,
    object_kind: GraphNodeKind,
) -> bool:
    """
    Whether these two node kinds may be joined by this edge kind.

    A pure function of three enums - no repository, no request, no clock.
    """

    expected = EDGE_ENDPOINT_KINDS.get(edge_kind)

    return expected == (subject_kind, object_kind)
