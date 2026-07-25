from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    StructuredRetrievalError,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
)
from app.infrastructure.graph_query.sqlalchemy_graph_query_repository import (
    SqlAlchemyGraphQueryRepository,
)
from app.schemas.structured_retrieval import (
    RetrievalQueryPlanRead,
    StructuredRetrievalResultRead,
    StructuredRetrievalSearchRequest,
)
from app.services import structured_retrieval_service

router = APIRouter(
    tags=["Structured Retrieval"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _build_request(project_id: int, body: StructuredRetrievalSearchRequest):
    try:
        return StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=body.mode,
            limit=body.limit,
            include_neighborhood=body.include_neighborhood,
            neighborhood_depth=body.neighborhood_depth,
            lexical_match_mode=body.lexical_match_mode,
            canonical_entity_id=body.canonical_entity_id,
            entity_type=body.entity_type,
            attribute_name=body.attribute_name,
            attribute_value=body.attribute_value,
            relationship_type=body.relationship_type,
            lexical_terms=tuple(body.lexical_terms),
        )
    except StructuredRetrievalError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post(
    "/projects/{project_id}/structured-retrieval/plan",
    response_model=RetrievalQueryPlanRead,
    summary="Plan a structured retrieval request without executing it",
)
def plan_structured_retrieval(
    project_id: int,
    body: StructuredRetrievalSearchRequest,
):
    request = _build_request(project_id, body)

    return structured_retrieval_service.plan_retrieval(request)


@router.post(
    "/projects/{project_id}/structured-retrieval/search",
    response_model=StructuredRetrievalResultRead,
    summary="Execute a structured retrieval request",
)
def search_structured_retrieval(
    project_id: int,
    body: StructuredRetrievalSearchRequest,
    db: Session = Depends(get_db),
):
    request = _build_request(project_id, body)
    repository = SqlAlchemyGraphQueryRepository(db)

    return structured_retrieval_service.retrieve(
        repository,
        request,
        now=datetime.utcnow(),
    )
