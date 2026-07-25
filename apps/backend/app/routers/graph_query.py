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
from app.domain.graph_query.graph_query_exceptions import (
    CrossProjectGraphQueryError,
    EntityNotFoundError,
    InvalidAttributeNameError,
    InvalidEntityTypeError,
    UnsupportedTraversalDepthError,
)
from app.domain.project_knowledge_graph.graph_entity_id_codec import (
    parse_graph_entity_id,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    InvalidGraphEntityIdError,
)
from app.infrastructure.graph_query.sqlalchemy_graph_query_repository import (
    SqlAlchemyGraphQueryRepository,
)
from app.schemas.graph_query import (
    GraphNeighborhoodRead,
    GraphNodeViewRead,
    GraphRelationshipViewRead,
    GraphStatisticsRead,
)
from app.services import graph_query_service


router = APIRouter(
    tags=["Graph Query"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


_NOT_FOUND_ERRORS = (EntityNotFoundError,)

_INVALID_INPUT_ERRORS = (
    CrossProjectGraphQueryError,
    InvalidEntityTypeError,
    InvalidAttributeNameError,
    UnsupportedTraversalDepthError,
    InvalidGraphEntityIdError,
)


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

    raise error


@router.get(
    "/projects/{project_id}/graph/entities",
    response_model=list[GraphNodeViewRead],
)
def list_entities(
    project_id: int,
    has_attribute: str | None = None,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    try:
        result = graph_query_service.list_entities(
            repository,
            project_id=project_id,
            has_attribute=has_attribute,
            now=datetime.utcnow(),
        )
    except _INVALID_INPUT_ERRORS as error:
        _handle(error)

    return result.payload


@router.get(
    "/projects/{project_id}/graph/entities/{entity_id}",
    response_model=GraphNodeViewRead,
)
def get_entity(
    project_id: int,
    entity_id: str,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    try:
        graph_entity_id = parse_graph_entity_id(project_id, entity_id)
        result = graph_query_service.get_entity(
            repository,
            project_id=project_id,
            graph_entity_id=graph_entity_id,
            now=datetime.utcnow(),
        )
    except (*_NOT_FOUND_ERRORS, *_INVALID_INPUT_ERRORS) as error:
        _handle(error)

    return result.payload


@router.get(
    "/projects/{project_id}/graph/entity-types/{type}",
    response_model=list[GraphNodeViewRead],
)
def list_entities_by_type(
    project_id: int,
    type: str,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    try:
        result = graph_query_service.list_entities_by_type(
            repository,
            project_id=project_id,
            entity_type=type,
            now=datetime.utcnow(),
        )
    except _INVALID_INPUT_ERRORS as error:
        _handle(error)

    return result.payload


@router.get(
    "/projects/{project_id}/graph/neighborhood/{entity_id}",
    response_model=GraphNeighborhoodRead,
)
def get_neighborhood(
    project_id: int,
    entity_id: str,
    depth: int = 1,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    try:
        graph_entity_id = parse_graph_entity_id(project_id, entity_id)
        result = graph_query_service.get_neighborhood(
            repository,
            project_id=project_id,
            graph_entity_id=graph_entity_id,
            depth=depth,
            now=datetime.utcnow(),
        )
    except (*_NOT_FOUND_ERRORS, *_INVALID_INPUT_ERRORS) as error:
        _handle(error)

    return result.payload


@router.get(
    "/projects/{project_id}/graph/statistics",
    response_model=GraphStatisticsRead,
)
def get_statistics(
    project_id: int,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    result = graph_query_service.get_statistics(
        repository,
        project_id=project_id,
        now=datetime.utcnow(),
    )

    return result.payload


@router.get(
    "/projects/{project_id}/graph/orphans",
    response_model=list[GraphNodeViewRead],
)
def list_orphans(
    project_id: int,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    result = graph_query_service.list_orphans(
        repository,
        project_id=project_id,
        now=datetime.utcnow(),
    )

    return result.payload


@router.get(
    "/projects/{project_id}/graph/relationships",
    response_model=list[GraphRelationshipViewRead],
)
def list_relationships(
    project_id: int,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyGraphQueryRepository(db)

    result = graph_query_service.list_all_relationships(
        repository,
        project_id=project_id,
        now=datetime.utcnow(),
    )

    return result.payload
