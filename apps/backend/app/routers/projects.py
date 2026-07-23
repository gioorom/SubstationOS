from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.project.project_exceptions import (
    DuplicateProjectCodeError,
    InvalidProjectCodeError,
    InvalidProjectNameError,
    InvalidProjectTransitionError,
    ProjectNotFoundError,
    ProjectNotMutableError,
)
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.models.project import Project as ProjectRecord
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdateMetadata,
)
from app.schemas.project_intelligence import (
    ProjectIntelligenceResponse,
)
from app.services import project_service
from app.services.project_intelligence import (
    build_project_intelligence,
)


router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _get_record_or_404(
    db: Session,
    project_id: int,
) -> ProjectRecord:
    """
    Re-reads the ORM row for the response payload. The domain
    ``Project`` returned by the service layer does not carry the
    pre-existing ``status``/``voltage_level`` delivery-phase fields
    (an orthogonal concern to the Lifecycle, see
    ``app.domain.project.project_lifecycle``) - the ORM row does, so
    responses are built from it.
    """

    record = db.get(ProjectRecord, project_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return record


@router.get(
    "/",
    response_model=list[ProjectRead],
)
def get_projects(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyProjectRepository(db)

    projects = project_service.list_projects(
        repository,
        include_deleted=include_deleted,
    )

    records_by_id = {
        record.id: record
        for record in (
            db.query(ProjectRecord)
            .filter(
                ProjectRecord.id.in_(
                    [project.id for project in projects]
                )
            )
            .all()
        )
    }

    return [records_by_id[project.id] for project in projects]


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyProjectRepository(db)

    try:
        project = project_service.create_project(
            repository,
            name=payload.name,
            code=payload.code,
            customer=payload.customer,
            now=datetime.utcnow(),
            epc=payload.epc,
            country=payload.country,
            location=payload.location,
            description=payload.description,
            canonical_domain_version=payload.canonical_domain_version,
            created_by=payload.created_by,
        )
    except DuplicateProjectCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (InvalidProjectNameError, InvalidProjectCodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    record = _get_record_or_404(db, project.id)

    # Legacy delivery-phase fields (see _get_record_or_404) are not part
    # of the Project Lifecycle domain and so are applied directly here.
    record.voltage_level = payload.voltage_level
    record.status = payload.status
    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    return _get_record_or_404(db, project_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
)
def update_project_metadata(
    project_id: int,
    payload: ProjectUpdateMetadata,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyProjectRepository(db)

    try:
        project = project_service.update_project_metadata(
            repository,
            project_id,
            now=datetime.utcnow(),
            name=payload.name,
            customer=payload.customer,
            epc=payload.epc,
            country=payload.country,
            location=payload.location,
            description=payload.description,
        )
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ProjectNotMutableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except InvalidProjectNameError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return _get_record_or_404(db, project.id)


def _transition_endpoint(
    project_id: int,
    db: Session,
    transition: Callable[..., Project],
) -> ProjectRecord:
    repository: ProjectRepository = SqlAlchemyProjectRepository(db)

    try:
        project = transition(repository, project_id, now=datetime.utcnow())
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except InvalidProjectTransitionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return _get_record_or_404(db, project.id)


@router.post(
    "/{project_id}/activate",
    response_model=ProjectRead,
)
def activate_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    return _transition_endpoint(
        project_id,
        db,
        project_service.activate_project,
    )


@router.post(
    "/{project_id}/archive",
    response_model=ProjectRead,
)
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    return _transition_endpoint(
        project_id,
        db,
        project_service.archive_project,
    )


@router.post(
    "/{project_id}/restore",
    response_model=ProjectRead,
)
def restore_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    return _transition_endpoint(
        project_id,
        db,
        project_service.restore_project,
    )


@router.delete(
    "/{project_id}",
    response_model=ProjectRead,
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Soft deletes the project. No row is ever removed from the database.
    """

    return _transition_endpoint(
        project_id,
        db,
        project_service.delete_project,
    )


@router.get(
    "/{project_id}/intelligence",
    response_model=ProjectIntelligenceResponse,
)
def get_project_intelligence(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _get_record_or_404(db, project_id)

    return build_project_intelligence(
        db=db,
        project=project,
    )
