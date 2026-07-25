from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True, slots=True)
class GraphEntityId:
    """
    The graph-scoped identity of one engineering entity, built
    exclusively from a
    ``app.domain.canonicalization.canonicalization_models.CanonicalEntityReference``
    (``GraphEntityIdFactory.from_canonical_reference``) - never from a
    raw string. Project-scoped (``project_id``) so that two different
    projects' "CABLE:C-295" can never collide into the same graph node
    (ADR-0001).
    """

    project_id: int
    entity_type: str
    canonical_id: str

    @property
    def value(self) -> str:
        return f"{self.project_id}:{self.entity_type}:{self.canonical_id}"


@dataclass(frozen=True, slots=True)
class GraphRelationshipType:
    """
    A graph-scoped relationship type, generated exclusively from a
    ``CanonicalPredicate`` (``GraphRelationshipTypeFactory.from_canonical_predicate``)
    - never from a raw string and never from a ``CanonicalAttribute``
    (attribute claims produce node operations, not relationships).
    """

    value: str


class GraphNodeOperationKind(str, Enum):
    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"


class GraphRelationshipOperationKind(str, Enum):
    CREATE_RELATIONSHIP = "create_relationship"
    UPDATE_RELATIONSHIP = "update_relationship"
    DELETE_RELATIONSHIP = "delete_relationship"
    SUPERSEDE_RELATIONSHIP = "supersede_relationship"


@dataclass(frozen=True, slots=True)
class GraphNodeOperation:
    """
    A deterministic instruction to create or update one graph node.
    Carries no execution or persistence behavior - Graph Persistence
    (Milestone 11.2) is what turns this into a database write, this
    bounded context only describes the mutation.

    ``attribute``/``value`` are set only for ``UPDATE_NODE`` (the
    canonical attribute name/value an ``ATTRIBUTE`` fact asserts);
    both are ``None`` for ``CREATE_NODE``, which only asserts the
    entity's existence and identity.
    """

    kind: GraphNodeOperationKind
    entity_id: GraphEntityId
    attribute: str | None
    value: str | None
    source_fact_id: int


@dataclass(frozen=True, slots=True)
class GraphRelationshipOperation:
    """
    A deterministic instruction to create, update, delete, or supersede
    one graph relationship. ``subject_id``/``object_id`` are always
    built from a ``CanonicalEntityReference`` and ``relationship_type``
    always from a ``CanonicalPredicate`` - a Graph Builder never
    invents an entity or relationship type that Canonicalization did
    not already produce.
    """

    kind: GraphRelationshipOperationKind
    subject_id: GraphEntityId
    relationship_type: GraphRelationshipType
    object_id: GraphEntityId
    source_fact_id: int


# The two operation shapes this bounded context produces. A plain union,
# not a base class with subclasses: there is no shared behavior beyond
# the fields each already declares, and Python's modern union types
# (CLAUDE.md SS6) make an inheritance hierarchy unnecessary ceremony.
GraphOperation = GraphNodeOperation | GraphRelationshipOperation


@dataclass(frozen=True, slots=True)
class GraphOperationResult:
    """
    The outcome of considering one candidate ``GraphOperation`` during
    batch assembly: whether it was included in the final
    ``GraphOperationBatch`` or suppressed as a duplicate of an operation
    already produced earlier in the same batch (``included=False``,
    ``reason`` explains why). Internal bookkeeping for
    ``GraphOperationBatchFactory``/``GraphBuilderService`` - not part of
    the batch a caller receives, but directly testable to prove
    duplicate suppression actually happened, not merely that the final
    count looks right.
    """

    operation: GraphOperation
    included: bool
    reason: str | None


class GraphOperationBatchScope(str, Enum):
    """What a ``GraphOperationBatch`` was built from - the two shapes
    the API supports (``POST /graph-builder/build/project/{id}`` and
    ``.../build/document/{id}``)."""

    PROJECT = "project"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class GraphOperationBatchSource:
    scope: GraphOperationBatchScope
    scope_id: int


@dataclass(frozen=True, slots=True)
class GraphOperationBatch:
    """
    A deterministically ordered collection of ``GraphOperation``s
    translated from a set of Canonical Facts, with duplicates already
    suppressed. This is Graph Builder's entire output - it is never
    executed or written to a graph database by this bounded context
    (Graph Persistence, Milestone 11.2, is what consumes it).

    Ordering is fixed and content-independent: every ``CREATE_NODE``
    operation first, then every ``UPDATE_NODE`` operation, then every
    relationship operation - so a graph-persistence consumer can always
    create referenced nodes before the edges between them, regardless
    of which Canonical Fact happened to be canonicalized first.

    ``project_id`` is ``None`` only for a document-scoped batch built
    from a document with no Canonical Facts yet - there is nothing to
    derive a project from without this bounded context depending on a
    Document lookup, which it deliberately does not (see this
    milestone's Architecture Compliance notes). Such a batch is empty
    and is not persisted.

    ``id`` is ``None`` for a batch that has not yet been persisted.
    """

    id: int | None
    project_id: int | None
    source: GraphOperationBatchSource
    operations: tuple[GraphOperation, ...]
    created_at: datetime
