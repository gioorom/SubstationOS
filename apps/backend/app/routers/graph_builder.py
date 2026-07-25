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
from app.domain.graph_builder.graph_builder_exceptions import (
    ConflictingAttributeOperationError,
    CrossProjectGraphOperationError,
    GraphBuilderProjectNotFoundError,
    GraphOperationBatchNotFoundError,
    InvalidCanonicalFactShapeError,
    MissingEntityReferenceError,
    ProjectNotGraphBuildableError,
    UnsupportedClaimTypeError,
)
from app.infrastructure.canonicalization.sqlalchemy_canonical_fact_repository import (
    SqlAlchemyCanonicalFactRepository,
)
from app.infrastructure.graph_builder.sqlalchemy_graph_operation_batch_repository import (
    SqlAlchemyGraphOperationBatchRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.schemas.graph_builder import GraphOperationBatchRead
from app.services import graph_builder_service


router = APIRouter(
    tags=["Graph Builder"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


_NOT_FOUND_ERRORS = (
    GraphBuilderProjectNotFoundError,
    GraphOperationBatchNotFoundError,
)

_INVALID_INPUT_ERRORS = (
    UnsupportedClaimTypeError,
    InvalidCanonicalFactShapeError,
    MissingEntityReferenceError,
    CrossProjectGraphOperationError,
    ConflictingAttributeOperationError,
)

_CONFLICT_ERRORS = (ProjectNotGraphBuildableError,)


@router.post(
    "/graph-builder/build/project/{project_id}",
    response_model=GraphOperationBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def build_batch_for_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    batch_repository = SqlAlchemyGraphOperationBatchRepository(db)
    fact_repository = SqlAlchemyCanonicalFactRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return graph_builder_service.build_batch_for_project(
            batch_repository,
            fact_repository,
            project_repository,
            project_id=project_id,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except _CONFLICT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/graph-builder/build/document/{document_id}",
    response_model=GraphOperationBatchRead,
)
def build_batch_for_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    batch_repository = SqlAlchemyGraphOperationBatchRepository(db)
    fact_repository = SqlAlchemyCanonicalFactRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return graph_builder_service.build_batch_for_document(
            batch_repository,
            fact_repository,
            project_repository,
            document_id=document_id,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except _CONFLICT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/graph-builder/batch/{batch_id}",
    response_model=GraphOperationBatchRead,
)
def get_graph_operation_batch(
    batch_id: int,
    db: Session = Depends(get_db),
):
    batch_repository = SqlAlchemyGraphOperationBatchRepository(db)

    try:
        return graph_builder_service.get_graph_operation_batch(
            batch_repository,
            batch_id,
        )
    except GraphOperationBatchNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
