from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.project.project_lifecycle import ProjectLifecycleState


class ProjectKnowledgeGraphError(Exception):
    """
    Base class for every exception raised by the Project Knowledge
    Graph Persistence bounded context.
    """


# --- Request/batch-level: raised before any operation is executed,
# mapped to an HTTP 4xx by the router. -----------------------------------


class GraphOperationBatchNotFoundError(ProjectKnowledgeGraphError):
    def __init__(self, batch_id: int) -> None:
        self.batch_id = batch_id

        super().__init__(f"Graph operation batch '{batch_id}' not found.")


class TransientBatchNotExecutableError(ProjectKnowledgeGraphError):
    """A batch with no ``id`` cannot be executed - it was never
    persisted, so it can never be referenced by a caller either. A
    defensive check: unreachable through the real repository, kept
    because the domain contract for ``GraphOperationBatch`` allows a
    transient (unpersisted) instance to exist in memory."""

    def __init__(self) -> None:
        super().__init__(
            "A transient (unpersisted) graph operation batch cannot be "
            "executed."
        )


class BatchMissingProjectError(ProjectKnowledgeGraphError):
    """A document-scoped batch built from a document with no Canonical
    Facts yet has no resolvable project (see
    ``GraphOperationBatch``'s docstring) and therefore cannot be
    executed."""

    def __init__(self, batch_id: int) -> None:
        self.batch_id = batch_id

        super().__init__(
            f"Graph operation batch '{batch_id}' has no project and "
            "cannot be executed."
        )


class GraphExecutionProjectNotFoundError(ProjectKnowledgeGraphError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Project '{project_id}' not found.")


class ProjectNotGraphExecutableError(ProjectKnowledgeGraphError):
    """
    Executing a batch persists new state scoped to a Project; Archived
    and Deleted projects are read-only, per the Project Lifecycle - the
    same rule every other write path in this system enforces.
    """

    def __init__(
        self,
        project_id: int,
        lifecycle_state: ProjectLifecycleState,
    ) -> None:
        self.project_id = project_id
        self.lifecycle_state = lifecycle_state

        super().__init__(
            f"Project '{project_id}' is '{lifecycle_state.value}' and "
            "is read-only; no graph operation batch can be executed "
            "against it."
        )


class GraphExecutionNotFoundError(ProjectKnowledgeGraphError):
    def __init__(self, execution_id: int) -> None:
        self.execution_id = execution_id

        super().__init__(f"Graph execution '{execution_id}' not found.")


class InvalidGraphEntityIdError(ProjectKnowledgeGraphError):
    """The ``{graph_entity_id}`` path segment is not a well-formed
    ``"{entity_type}:{canonical_id}"`` pair."""

    def __init__(self, raw_value: str) -> None:
        self.raw_value = raw_value

        super().__init__(
            f"'{raw_value}' is not a valid graph entity id "
            "('entity_type:canonical_id')."
        )


# --- Operation-level: raised while executing one operation, caught by
# the service, never surfaced as an HTTP error - they cause the batch's
# graph mutations to roll back and a FAILED GraphExecution to be
# recorded instead. ------------------------------------------------------


class GraphExecutionOperationError(ProjectKnowledgeGraphError):
    """Base class for every exception that represents one operation
    failing during execution, as opposed to the whole request being
    invalid."""


class UnsupportedGraphOperationError(GraphExecutionOperationError):
    """
    Graph Persistence executes only ``CREATE_NODE``, ``UPDATE_NODE``,
    and ``CREATE_RELATIONSHIP`` - the kinds Graph Builder currently
    emits. ``UPDATE_RELATIONSHIP``/``DELETE_RELATIONSHIP``/
    ``SUPERSEDE_RELATIONSHIP`` are defined but never executed this
    milestone; there is no speculative behavior for them.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind

        super().__init__(
            f"'{kind}' is not a supported graph operation kind."
        )


class GraphNodeNotFoundError(GraphExecutionOperationError):
    """
    ``UPDATE_NODE`` and ``CREATE_RELATIONSHIP`` require their target
    entity/entities to already exist - Graph Persistence never invents
    a missing node.
    """

    def __init__(
        self,
        project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> None:
        self.project_id = project_id
        self.graph_entity_id = graph_entity_id

        super().__init__(
            f"No node '{graph_entity_id.value}' exists in project "
            f"'{project_id}'."
        )


class CrossProjectGraphExecutionError(GraphExecutionOperationError):
    """
    An operation's own entity id(s) do not belong to the batch's
    project - a data-integrity anomaly Graph Builder's own validation
    should already prevent, checked defensively here rather than
    assumed.
    """

    def __init__(self, expected_project_id: int, found_project_id: int) -> None:
        self.expected_project_id = expected_project_id
        self.found_project_id = found_project_id

        super().__init__(
            f"Operation targets project '{found_project_id}', not the "
            f"batch's project '{expected_project_id}'."
        )


class MalformedGraphOperationError(GraphExecutionOperationError):
    """A node/relationship operation is missing a field its kind
    requires (e.g. ``UPDATE_NODE`` with no attribute/value) - defensive:
    Graph Builder's own factory should never produce this."""

    def __init__(self, kind: str, detail: str) -> None:
        self.kind = kind
        self.detail = detail

        super().__init__(f"Malformed '{kind}' operation: {detail}.")


class ConcurrentGraphMutationError(GraphExecutionOperationError):
    """
    An upsert's insert-after-select-found-nothing was rejected by the
    database's own natural-key uniqueness constraint - a genuine
    concurrent writer won the race between this operation's read and
    write. Not recovered in place (the whole transaction must roll
    back regardless, per this milestone's atomicity requirement); on
    retry, the same upsert will find the concurrently-created row via
    its normal select-first path and return it, no error.
    """

    def __init__(self, natural_key: str) -> None:
        self.natural_key = natural_key

        super().__init__(
            f"Concurrent write detected for '{natural_key}'; retry the "
            "batch execution."
        )
