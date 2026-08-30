"""
What the governed graph is allowed to contain.

Three node kinds and two edge kinds. That is not an oversight, and it is
not a placeholder: **it is exactly what governed engineering semantics
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
| ``EntityType`` | ``equipment_designation``, ``engineering_quantity``, ``structural_location`` |
| ``SemanticStatementType`` | ``has_rated_power``, ``is_located_in`` |

So the graph can express an asset identified by a designation, a
quantity, the rated-power relationship between them, a designated
location, and the containment relationship between an asset and a
location. **Nothing else.**

## What EPIC 32.P1 added, and why it was allowed to

``STRUCTURAL_LOCATION`` and ``IS_LOCATED_IN`` arrived together because a
node kind nothing can relate to would be a concept no query could use,
and an edge kind with no second endpoint could not exist. They are the
first governed relationship in this graph whose **both endpoints are
structural objects**, which is what EPIC 32.2 found missing when it
stopped.

They obey the rule the rest of this table records: each exists because a
semantic rule produces the statement it comes from -
``location_from_compound_reference_designation``, reading the ``+``
aspect of a compound IEC 81346 reference designation. Neither was added
because a later milestone wanted one.

### What is deliberately absent, and what each would need

| Concept | Why it is not here |
|---|---|
| Voltage | Voltage *evidence* exists, and `engineering_semantics` deliberately refuses to interpret it: an associated voltage may be rated, test, insulation or busbar voltage, and the association does not say which. A `Voltage` node would assert a meaning no rule has assigned. |
| Protection | No evidence type, no entity type, no statement type. |
| Connection | Would require a topology statement type. `HAS_ASSOCIATED_QUANTITY` is a same-line association, not a connection - and `IS_LOCATED_IN` is containment, not a circuit: two assets in one location are in the same place, which says nothing about what is wired to what. |
| Function | Would require a classification vocabulary and a rule that assigns it. |
| Location *kind* | ``STRUCTURAL_LOCATION`` says a location was designated; it does not say whether ``+E01`` is a bay, a panel, a room or a building. That classification needs a governed vocabulary, exactly as the equipment classes do. (Source *locations* - page, line, span - are a different thing again: they are provenance, not engineering knowledge.) |

Each becomes promotable the day a semantic rule produces it, and the
change is one member here plus one entry in the mapping below - which is
exactly the change EPIC 32.P1 made for the location aspect, once an
extraction rule, a fact predicate and a semantic rule existed to produce
it. Adding the rest now would be node kinds no promotion can create, no
query can return and no test can cover - the shape of the model implying
knowledge the system does not have.
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

    #: A place the documents put equipment **in** - ``+E01``. Promoted
    #: from a `structural_location` entity, which comes from the ``+``
    #: aspect of a compound IEC 81346 reference designation.
    #:
    #: Deliberately not ``Bay``, ``Panel`` or ``Room``. IEC 81346 assigns
    #: ``+`` to the location aspect and says nothing about what kind of
    #: location it is; this node says a location was designated, and
    #: leaves what sort of place it is to a vocabulary somebody governs.
    STRUCTURAL_LOCATION = "structural_location"


class GraphEdgeKind(str, Enum):
    """
    The governed engineering relationships.

    One member per semantic statement type that exists. An edge kind is
    added here only when a semantic rule produces the statement it would
    come from - never in anticipation.
    """

    #: "This asset's rated power is this quantity." Promoted from a
    #: `has_rated_power` statement that an engineer approved.
    HAS_RATED_POWER = "has_rated_power"

    #: "This asset is located in this structural location." Promoted from
    #: an `is_located_in` statement that an engineer approved.
    #:
    #: The **first governed relationship between two structural
    #: objects**, and the reason relationship reasoning has anything to
    #: read. It is a containment statement and nothing more: it does not
    #: say two assets in one location are connected, does not encode
    #: electrical direction, and does not make the location a circuit
    #: node.
    IS_LOCATED_IN = "is_located_in"


#: Which entity type becomes which node kind.
#:
#: The **only** way a node comes into existence. An entity type absent
#: from this table cannot be promoted, which is what keeps the graph from
#: acquiring concepts the pipeline never produced.
NODE_KIND_FOR_ENTITY_TYPE: dict[str, GraphNodeKind] = {
    "equipment_designation": GraphNodeKind.ENGINEERING_ASSET,
    "engineering_quantity": GraphNodeKind.ENGINEERING_QUANTITY,
    "structural_location": GraphNodeKind.STRUCTURAL_LOCATION,
}


#: Which semantic statement type becomes which edge kind.
#:
#: The **only** way an edge comes into existence.
EDGE_KIND_FOR_STATEMENT_TYPE: dict[str, GraphEdgeKind] = {
    "has_rated_power": GraphEdgeKind.HAS_RATED_POWER,
    "is_located_in": GraphEdgeKind.IS_LOCATED_IN,
}


#: What each edge kind requires of its endpoints.
#:
#: Every edge kind relates its two endpoints in one direction only: a
#: rated power runs from an asset to a quantity, and a location from an
#: asset to a location. The constraint is checked at promotion, so an
#: edge whose endpoints are the wrong kinds is refused rather than
#: stored - a graph that answered "what is the rated power of 630 kVA?"
#: would be worse than one that answered nothing.
#:
#: **Direction here is grammatical, not electrical.** It records which
#: endpoint is the subject of the reviewed statement. No edge kind in
#: this vocabulary encodes power flow, and none may be read as though it
#: did.
EDGE_ENDPOINT_KINDS: dict[
    GraphEdgeKind, tuple[GraphNodeKind, GraphNodeKind]
] = {
    GraphEdgeKind.HAS_RATED_POWER: (
        GraphNodeKind.ENGINEERING_ASSET,
        GraphNodeKind.ENGINEERING_QUANTITY,
    ),
    # An asset is located in a location, in that direction. The reverse
    # is refused for the same reason the rated-power reverse is: a graph
    # that answered "what is +E01 located in?" with a circuit breaker
    # would be worse than one that answered nothing.
    GraphEdgeKind.IS_LOCATED_IN: (
        GraphNodeKind.ENGINEERING_ASSET,
        GraphNodeKind.STRUCTURAL_LOCATION,
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
