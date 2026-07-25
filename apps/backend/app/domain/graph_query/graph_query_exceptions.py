from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import GraphEntityId


class GraphQueryError(Exception):
    """
    Base class for every exception raised by the Graph Query bounded
    context. Deliberately has no "project not found" member: every
    query here is scoped by ``project_id`` in its own read, so a
    nonexistent project and an existing-but-empty project are
    indistinguishable from a pure read - both simply return no rows
    (or, for a single-entity query, ``EntityNotFoundError``). Graph
    Query is read-only and never needed to confirm a project's
    existence or mutability the way every write-oriented milestone in
    this pipeline did.
    """


class EntityNotFoundError(GraphQueryError):
    def __init__(self, project_id: int, graph_entity_id: GraphEntityId) -> None:
        self.project_id = project_id
        self.graph_entity_id = graph_entity_id

        super().__init__(
            f"No entity '{graph_entity_id.value}' exists in project "
            f"'{project_id}'."
        )


class CrossProjectGraphQueryError(GraphQueryError):
    """
    An entity id parsed from a request does not belong to the project
    the request was scoped to. Structurally unreachable through this
    bounded context's own path parsing (which always builds a
    ``GraphEntityId`` from the URL's own ``project_id``), kept as a
    defensive, typed check rather than assumed.
    """

    def __init__(self, expected_project_id: int, found_project_id: int) -> None:
        self.expected_project_id = expected_project_id
        self.found_project_id = found_project_id

        super().__init__(
            f"Entity belongs to project '{found_project_id}', not the "
            f"requested project '{expected_project_id}'."
        )


class InvalidEntityTypeError(GraphQueryError):
    def __init__(self, entity_type: str) -> None:
        self.entity_type = entity_type

        super().__init__(
            f"Invalid entity type: '{entity_type}'. An entity type is "
            "required."
        )


class InvalidAttributeNameError(GraphQueryError):
    def __init__(self, attribute: str) -> None:
        self.attribute = attribute

        super().__init__(
            f"Invalid attribute name: '{attribute}'. An attribute name "
            "is required."
        )


class UnsupportedTraversalDepthError(GraphQueryError):
    """Graph Query supports only depth-1 (direct neighbor) traversal -
    no recursive traversal, no graph algorithms."""

    def __init__(self, depth: int) -> None:
        self.depth = depth

        super().__init__(
            f"Unsupported traversal depth: {depth}. Only depth=1 is "
            "supported."
        )
