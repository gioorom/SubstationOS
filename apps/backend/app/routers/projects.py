"""
The Project API.

Every response is built from the **domain aggregate**, through
``project_service``. This router constructs no query, reads no ORM row
and knows no column name - a discipline it did not have before Milestone
30.1.3, when it re-read the persistence record to fill in fields the
domain model lacked.

Status mapping, consistent across every endpoint here:

- ``404`` the project does not exist
- ``409`` the request conflicts with the project's lifecycle state - a
  duplicate code, an invalid transition, an edit to a read-only project
- ``422`` the request itself is invalid - a name or code the domain
  refuses, a page size beyond the maximum
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
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
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_query import (
    DEFAULT_PROJECT_DIRECTION,
    DEFAULT_PROJECT_SORT,
    ProjectQuery,
    ProjectSearchTerm,
    ProjectSortField,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.project.project_status import ProjectStatus
from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageRequest,
    SortDirection,
)
from app.domain.shared_kernel.pagination_exceptions import PaginationError
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.schemas.pagination import PageMetadata
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
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


def _repository(db: Session) -> ProjectRepository:
    return SqlAlchemyProjectRepository(db)


def _require_project(db: Session, project_id: int) -> Project:
    try:
        return project_service.get_project(_repository(db), project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="List projects, filtered, sorted and paginated by the server",
)
def get_projects(
    page: int = Query(default=1, ge=1, description="1-based page index."),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page. Maximum {MAX_PAGE_SIZE}.",
    ),
    status_filter: ProjectStatus | None = Query(
        default=None,
        alias="status",
        description="Delivery phase of the installation.",
    ),
    lifecycle_state: ProjectLifecycleState | None = Query(
        default=None,
        description=(
            "Record lifecycle. Distinct from status: a project can be "
            "'energized' and 'archived' at once."
        ),
    ),
    search: str | None = Query(
        default=None,
        description=(
            "Case-insensitive partial match over name, code, customer "
            "and location. Trimmed at both ends; internal whitespace is "
            "significant."
        ),
    ),
    include_deleted: bool = Query(
        default=False,
        description="Soft-deleted projects are hidden unless this is set.",
    ),
    sort_by: ProjectSortField = Query(default=DEFAULT_PROJECT_SORT),
    direction: SortDirection = Query(default=DEFAULT_PROJECT_DIRECTION),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    try:
        page_request = PageRequest(page=page, page_size=page_size)
    except PaginationError as error:
        # FastAPI's own ge/le bounds refuse most of these first; this
        # keeps the domain rule authoritative even if they ever diverge.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    result = project_service.list_projects_page(
        _repository(db),
        ProjectQuery(
            page=page_request,
            status=status_filter,
            lifecycle_state=lifecycle_state,
            search=ProjectSearchTerm.of(search),
            include_deleted=include_deleted,
            sort_by=sort_by,
            direction=direction,
        ),
    )

    return ProjectListResponse(
        items=tuple(ProjectRead.of(project) for project in result.items),
        pagination=PageMetadata.of(result),
    )


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "A project with this code already exists."},
        422: {"description": "The name or code is not valid."},
    },
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        project = project_service.create_project(
            _repository(db),
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
            status=payload.status,
            voltage_level=payload.voltage_level,
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

    return ProjectRead.of(project)


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    responses={404: {"description": "No such project."}},
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return ProjectRead.of(_require_project(db, project_id))


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    responses={
        404: {"description": "No such project."},
        409: {"description": "The project is archived or deleted."},
        422: {"description": "The name is not valid."},
    },
)
def update_project_metadata(
    project_id: int,
    payload: ProjectUpdateMetadata,
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        project = project_service.update_project_metadata(
            _repository(db),
            project_id,
            now=datetime.utcnow(),
            name=payload.name,
            customer=payload.customer,
            epc=payload.epc,
            country=payload.country,
            location=payload.location,
            description=payload.description,
            status=payload.status,
            voltage_level=payload.voltage_level,
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

    return ProjectRead.of(project)


def _transition_endpoint(
    project_id: int,
    db: Session,
    transition: Callable[..., Project],
) -> ProjectRead:
    try:
        project = transition(
            _repository(db), project_id, now=datetime.utcnow()
        )
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

    return ProjectRead.of(project)


_TRANSITION_RESPONSES = {
    404: {"description": "No such project."},
    409: {
        "description": (
            "The transition is not allowed from the project's current "
            "lifecycle state."
        )
    },
}


@router.post(
    "/{project_id}/activate",
    response_model=ProjectRead,
    responses=_TRANSITION_RESPONSES,
)
def activate_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return _transition_endpoint(
        project_id,
        db,
        project_service.activate_project,
    )


@router.post(
    "/{project_id}/archive",
    response_model=ProjectRead,
    responses=_TRANSITION_RESPONSES,
)
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return _transition_endpoint(
        project_id,
        db,
        project_service.archive_project,
    )


@router.post(
    "/{project_id}/restore",
    response_model=ProjectRead,
    responses=_TRANSITION_RESPONSES,
)
def restore_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectRead:
    return _transition_endpoint(
        project_id,
        db,
        project_service.restore_project,
    )


@router.delete(
    "/{project_id}",
    response_model=ProjectRead,
    responses=_TRANSITION_RESPONSES,
    summary="Soft delete a project",
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectRead:
    """
    Soft deletes the project. No row is ever removed from the database,
    and the updated project is returned so a caller can see its new
    lifecycle state.
    """

    return _transition_endpoint(
        project_id,
        db,
        project_service.delete_project,
    )


@router.get(
    "/{project_id}/intelligence",
    response_model=ProjectIntelligenceResponse,
    responses={404: {"description": "No such project."}},
)
def get_project_intelligence(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectIntelligenceResponse:
    # Existence is confirmed through the repository; the intelligence
    # service is then given the id, never an ORM record.
    project = _require_project(db, project_id)

    return build_project_intelligence(db=db, project_id=project.id)
