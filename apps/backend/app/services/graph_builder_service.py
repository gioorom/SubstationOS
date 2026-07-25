"""
Application services for the Graph Builder (Milestone 11.1). Each
function is a single use case, orchestrating the domain
(``app.domain.graph_builder``) through the ``GraphOperationBatchRepository``
port, together with Canonicalization's own ``CanonicalFactRepository``
(read-only) and the Project bounded context's ``ProjectRepository``
(read-only) - never a raw database session.

This module translates Canonical Facts into Graph Operations. It does
not persist anything into a graph database, does not know Neo4j or
Cypher exist, and does not execute any operation it produces - Graph
Persistence (Milestone 11.2) is what consumes a ``GraphOperationBatch``
and turns it into an actual graph mutation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.canonicalization.canonicalization_repository import (
    CanonicalFactRepository,
)
from app.domain.graph_builder.graph_builder_exceptions import (
    GraphBuilderProjectNotFoundError,
    GraphOperationBatchNotFoundError,
    ProjectNotGraphBuildableError,
)
from app.domain.graph_builder.graph_builder_factory import (
    GraphOperationBatchFactory,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphOperationBatch,
    GraphOperationBatchScope,
    GraphOperationBatchSource,
)
from app.domain.graph_builder.graph_operation_batch_repository import (
    GraphOperationBatchRepository,
)
from app.domain.project.project_repository import ProjectRepository


def _require_graph_buildable_project(
    project_repository: ProjectRepository,
    project_id: int,
) -> None:
    project = project_repository.get_by_id(project_id)

    if project is None:
        raise GraphBuilderProjectNotFoundError(project_id)

    if not project.is_mutable():
        raise ProjectNotGraphBuildableError(
            project.id,  # type: ignore[arg-type]
            project.lifecycle_state,
        )


def build_batch_for_project(
    batch_repository: GraphOperationBatchRepository,
    fact_repository: CanonicalFactRepository,
    project_repository: ProjectRepository,
    *,
    project_id: int,
    now: datetime,
) -> GraphOperationBatch:
    """
    Builds and persists a ``GraphOperationBatch`` from every Canonical
    Fact currently recorded for a project. Raises
    ``GraphBuilderProjectNotFoundError`` if the project does not exist
    and ``ProjectNotGraphBuildableError`` if it is Archived or Deleted.
    A project with no Canonical Facts yet still produces a valid,
    empty, persisted batch bound to ``project_id`` - unlike the
    document-scoped build, this project is already known and already
    validated above, so the batch is never left without one (see
    ``GraphOperationBatchFactory.build``, which cannot infer a project
    from an empty fact list on its own).
    """

    _require_graph_buildable_project(project_repository, project_id)

    facts = fact_repository.list_by_project(project_id)
    source = GraphOperationBatchSource(
        scope=GraphOperationBatchScope.PROJECT,
        scope_id=project_id,
    )
    batch, _results = GraphOperationBatchFactory.build(
        source=source,
        facts=facts,
        now=now,
    )

    if batch.project_id is None:
        batch = replace(batch, project_id=project_id)

    return batch_repository.save(batch)


def build_batch_for_document(
    batch_repository: GraphOperationBatchRepository,
    fact_repository: CanonicalFactRepository,
    project_repository: ProjectRepository,
    *,
    document_id: int,
    now: datetime,
) -> GraphOperationBatch:
    """
    Builds and persists a ``GraphOperationBatch`` from every Canonical
    Fact citing at least one evidence entry from a document. Unlike the
    project-scoped build, this never resolves which project it belongs
    to via a Document lookup - Graph Builder has no dependency on the
    Document/Engineering Index bounded contexts. When Canonical Facts
    exist, their own ``project_id`` is used (and its mutability is
    still validated); when none exist, an empty, unpersisted batch with
    no known project is returned (see ``GraphOperationBatch``'s
    docstring).
    """

    facts = fact_repository.list_by_document(document_id)

    if facts:
        _require_graph_buildable_project(
            project_repository,
            facts[0].project_id,
        )

    source = GraphOperationBatchSource(
        scope=GraphOperationBatchScope.DOCUMENT,
        scope_id=document_id,
    )
    batch, _results = GraphOperationBatchFactory.build(
        source=source,
        facts=facts,
        now=now,
    )

    if batch.project_id is None:
        return batch

    return batch_repository.save(batch)


def get_graph_operation_batch(
    batch_repository: GraphOperationBatchRepository,
    batch_id: int,
) -> GraphOperationBatch:
    batch = batch_repository.get_by_id(batch_id)

    if batch is None:
        raise GraphOperationBatchNotFoundError(batch_id)

    return batch
