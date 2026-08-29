"""
How one retrieval result is identified.

**Derived from governed identity, and from nothing else.** A
``result_id`` is composed from the result kind and the node/edge ids the
governed graph already assigned - which are themselves SHA-256 digests
over governed keys (``graph_identity``). So a result identity inherits
every property those have: the same graph and the same query produce the
same identifiers on any machine, in any process, forever.

Deliberately **not** composed from: a counter, a page position, a
timestamp, a database row id, or a label. Each of those would make two
runs over unchanged knowledge disagree, and a caller that stored a
result identity would find it meaningless a day later.

A quantity reached by traversal carries **both** the edge and the node:
the same quantity node can be the object of two different governed
relationships, and collapsing them would report one answer where the
graph holds two.
"""

from __future__ import annotations

from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedResultKind,
)

_SEPARATOR = ":"


def node_result_id(kind: GovernedResultKind, node_id: str) -> str:
    """The identity of a result that *is* one governed node."""

    return _SEPARATOR.join((kind.value, node_id))


def relationship_result_id(edge_id: str) -> str:
    """The identity of a result that *is* one governed relationship."""

    return _SEPARATOR.join((GovernedResultKind.RELATIONSHIP.value, edge_id))


def traversed_node_result_id(
    kind: GovernedResultKind, edge_id: str, node_id: str
) -> str:
    """
    The identity of a node reached by following one governed edge.

    Both ends are in the identity because "the rated power of TR1" and
    "the rated power of TR2" may be the same quantity node, and they are
    two different engineering answers.
    """

    return _SEPARATOR.join((kind.value, edge_id, node_id))
