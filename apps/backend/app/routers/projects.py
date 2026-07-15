from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.project import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
)
from app.schemas.project_intelligence import (
    ProjectIntelligenceResponse,
)
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


@router.get(
    "/",
    response_model=list[ProjectRead],
)
def get_projects(
    db: Session = Depends(get_db),
):
    return (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
    existing_project = (
        db.query(Project)
        .filter(Project.code == payload.code)
        .first()
    )

    if existing_project is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project code already exists",
        )

    project = Project(
        name=payload.name,
        code=payload.code,
        customer=payload.customer,
        epc=payload.epc,
        location=payload.location,
        voltage_level=payload.voltage_level,
        status=payload.status,
        description=payload.description,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id)
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.get(
    "/{project_id}/intelligence",
    response_model=ProjectIntelligenceResponse,
)
def get_project_intelligence(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .filter(Project.id == project_id)
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return build_project_intelligence(
        db=db,
        project=project,
    )