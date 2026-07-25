from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.project_knowledge_graph.graph_entity_id_codec import (
    parse_graph_entity_id,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    BatchMissingProjectError,
    GraphExecutionNotFoundError,
    GraphExecutionProjectNotFoundError,
    GraphNodeNotFoundError,
    GraphOperationBatchNotFoundError,
    InvalidGraphEntityIdError,
    ProjectNotGraphExecutableError,
    TransientBatchNotExecutableError,
)
from app.infrastructure.graph_builder.sqlalchemy_graph_operation_batch_repository import (
    SqlAlchemyGraphOperationBatchRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_execution_repository import (
    SqlAlchemyGraphExecutionRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store import (
    SqlAlchemyGraphStore,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_unit_of_work import (
    SqlAlchemyGraphUnitOfWork,
)
from app.schemas.project_knowledge_graph import (
    GraphExecutionRead,
    GraphExecutionResultRead,
    ProjectGraphNodeRead,
    ProjectGraphRelationshipRead,
)
from app.services import graph_execution_service


router = APIRouter(
    tags=["Project Knowledge Graph"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


_NOT_FOUND_ERRORS = (
    GraphOperationBatchNotFoundError,
    GraphExecutionProjectNotFoundError,
    GraphExecutionNotFoundError,
    GraphNodeNotFoundError,
)

_INVALID_INPUT_ERRORS = (
    TransientBatchNotExecutableError,
    BatchMissingProjectError,
    InvalidGraphEntityIdError,
)

_CONFLICT_ERRORS = (ProjectNotGraphExecutableError,)


def _handle(error: Exception):
    if isinstance(error, _NOT_FOUND_ERRORS):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    if isinstance(error, _INVALID_INPUT_ERRORS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    if isinstance(error, _CONFLICT_ERRORS):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    raise error


@router.post(
    "/graph-executions/batches/{batch_id}",
    response_model=GraphExecutionResultRead,
)
def execute_batch(
    batch_id: int,
    db: Session = Depends(get_db),
):
    batch_repository = SqlAlchemyGraphOperationBatchRepository(db)
    execution_repository = SqlAlchemyGraphExecutionRepository(db)
    graph_store = SqlAlchemyGraphStore(db)
    project_repository = SqlAlchemyProjectRepository(db)
    unit_of_work = SqlAlchemyGraphUnitOfWork(db)

    try:
        return graph_execution_service.execute_batch(
            batch_repository,
            execution_repository,
            graph_store,
            project_repository,
            unit_of_work,
            batch_id=batch_id,
            now=datetime.utcnow(),
        )
    except (
        GraphOperationBatchNotFoundError,
        TransientBatchNotExecutableError,
        BatchMissingProjectError,
        GraphExecutionProjectNotFoundError,
        ProjectNotGraphExecutableError,
    ) as error:
        _handle(error)


@router.get(
    "/graph-executions/{execution_id}",
    response_model=GraphExecutionRead,
)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
):
    execution_repository = SqlAlchemyGraphExecutionRepository(db)

    try:
        return graph_execution_service.get_execution(
            execution_repository,
            execution_id,
        )
    except GraphExecutionNotFoundError as error:
        _handle(error)


@router.get(
    "/graph-operation-batches/{batch_id}/executions",
    response_model=list[GraphExecutionRead],
)
def list_executions_for_batch(
    batch_id: int,
    db: Session = Depends(get_db),
):
    execution_repository = SqlAlchemyGraphExecutionRepository(db)

    return graph_execution_service.list_executions_for_batch(
        execution_repository,
        batch_id,
    )


@router.get(
    "/projects/{project_id}/knowledge-graph/nodes",
    response_model=list[ProjectGraphNodeRead],
)
def list_graph_nodes(
    project_id: int,
    db: Session = Depends(get_db),
):
    graph_store = SqlAlchemyGraphStore(db)

    return graph_execution_service.list_graph_nodes(
        graph_store,
        project_id,
    )


@router.get(
    "/projects/{project_id}/knowledge-graph/nodes/{graph_entity_id}",
    response_model=ProjectGraphNodeRead,
)
def get_graph_node(
    project_id: int,
    graph_entity_id: str,
    db: Session = Depends(get_db),
):
    graph_store = SqlAlchemyGraphStore(db)

    try:
        entity_id = parse_graph_entity_id(project_id, graph_entity_id)

        return graph_execution_service.get_graph_node(
            graph_store,
            project_id,
            entity_id,
        )
    except (InvalidGraphEntityIdError, GraphNodeNotFoundError) as error:
        _handle(error)


@router.get(
    "/projects/{project_id}/knowledge-graph/relationships",
    response_model=list[ProjectGraphRelationshipRead],
)
def list_graph_relationships(
    project_id: int,
    db: Session = Depends(get_db),
):
    graph_store = SqlAlchemyGraphStore(db)

    return graph_execution_service.list_graph_relationships(
        graph_store,
        project_id,
    )


@router.get(
    "/projects/{project_id}/knowledge-graph/nodes/{graph_entity_id}/outgoing",
    response_model=list[ProjectGraphRelationshipRead],
)
def list_outgoing_relationships(
    project_id: int,
    graph_entity_id: str,
    db: Session = Depends(get_db),
):
    graph_store = SqlAlchemyGraphStore(db)

    try:
        entity_id = parse_graph_entity_id(project_id, graph_entity_id)
    except InvalidGraphEntityIdError as error:
        _handle(error)

    return graph_execution_service.list_outgoing_relationships(
        graph_store,
        project_id,
        entity_id,
    )


@router.get(
    "/projects/{project_id}/knowledge-graph/nodes/{graph_entity_id}/incoming",
    response_model=list[ProjectGraphRelationshipRead],
)
def list_incoming_relationships(
    project_id: int,
    graph_entity_id: str,
    db: Session = Depends(get_db),
):
    graph_store = SqlAlchemyGraphStore(db)

    try:
        entity_id = parse_graph_entity_id(project_id, graph_entity_id)
    except InvalidGraphEntityIdError as error:
        _handle(error)

    return graph_execution_service.list_incoming_relationships(
        graph_store,
        project_id,
        entity_id,
    )
