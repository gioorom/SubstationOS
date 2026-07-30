"""
How a governed graph object is identified.

**Identity derives from governed pipeline artefacts, never from a display
label.** A node is not "the node called TR1"; it is the node for one
governed entity key. Two entities that happen to render the same string
are two nodes, and one entity promoted twice is one node - which is the
whole of the duplicate-prevention guarantee.

---

## Why keys and not labels

`equipment_designation` entities carry a `label`, and it is tempting to
use it: `TR1` reads better than a hex digest. It would also be wrong in
both directions. Two different transformers labelled `TR1` in two
drawings would collapse into one node, silently merging engineering
knowledge nobody merged; and a label normalisation change would
re-identify every node in the graph.

Entity keys and statement keys are deterministic hashes the pipeline
already computes over the document, the rules and the source. Deriving
graph identity from them means:

- promoting the same artefact twice produces the **same** id, so
  promotion is idempotent and a rebuild reproduces the graph exactly;
- an artefact re-derived under different rules gets a **different** id,
  so knowledge from different rule versions never silently merges.

## What this does *not* do

**No cross-document entity resolution.** `TR1` in document A and `TR1` in
document B have different entity keys, so they are two nodes. That is
correct and it is a stated limit: deciding they are the same transformer
is entity resolution across documents, which no governed rule performs.
Merging them here would be exactly the label-matching this module exists
to refuse. See `knowledge_graph.md` on what an upstream milestone would
have to provide first.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.domain.governed_knowledge_graph.graph_exceptions import (
    InvalidGraphIdentityError,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)

NODE_IDENTITY_NAMESPACE = "substationos/governed-graph/node/v1"

EDGE_IDENTITY_NAMESPACE = "substationos/governed-graph/edge/v1"

#: Separator that cannot occur in a key or a kind, so two different
#: compositions cannot hash alike.
_SEPARATOR = "\x1f"


@dataclass(frozen=True, slots=True)
class GraphNodeId:
    """One node's stable identity, and the artefact it came from."""

    value: str
    kind: GraphNodeKind
    entity_key: str

    def __post_init__(self) -> None:
        if not self.entity_key.strip():
            raise InvalidGraphIdentityError(
                "A graph node must be identified by an entity key."
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GraphEdgeId:
    """One edge's stable identity, and the statement it came from."""

    value: str
    kind: GraphEdgeKind
    statement_key: str

    def __post_init__(self) -> None:
        if not self.statement_key.strip():
            raise InvalidGraphIdentityError(
                "A graph edge must be identified by a statement key."
            )

    def __str__(self) -> str:
        return self.value


def node_id_for(kind: GraphNodeKind, entity_key: str) -> GraphNodeId:
    """
    The identity of the node for one governed entity.

    Deterministic and total: the same kind and key always produce the
    same id, on any machine, in any process, forever. That is what makes
    a rebuild reproduce the graph rather than merely re-populate it.

    The namespace is versioned so a future change to how identity is
    composed is a visible, deliberate re-identification rather than a
    silent one.
    """

    key = entity_key.strip()

    if not key:
        raise InvalidGraphIdentityError(
            "A graph node must be identified by an entity key."
        )

    digest = hashlib.sha256(
        _SEPARATOR.join(
            (NODE_IDENTITY_NAMESPACE, kind.value, key)
        ).encode("utf-8")
    ).hexdigest()

    return GraphNodeId(value=digest, kind=kind, entity_key=key)


def edge_id_for(kind: GraphEdgeKind, statement_key: str) -> GraphEdgeId:
    """
    The identity of the edge for one governed semantic statement.

    `statement_key` is already a hash over the document, the fact source,
    the triple and the rule versions - so this identity inherits every
    property that gives it. Re-promoting an unchanged statement is a
    no-op; a statement re-derived under a new rule version is a different
    edge, and the old one is retired rather than mutated.
    """

    key = statement_key.strip()

    if not key:
        raise InvalidGraphIdentityError(
            "A graph edge must be identified by a statement key."
        )

    digest = hashlib.sha256(
        _SEPARATOR.join(
            (EDGE_IDENTITY_NAMESPACE, kind.value, key)
        ).encode("utf-8")
    ).hexdigest()

    return GraphEdgeId(value=digest, kind=kind, statement_key=key)
