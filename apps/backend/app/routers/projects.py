from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead


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


@router.post(
    "/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
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

    try:
        db.commit()
        db.refresh(project)
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esiste già un progetto con questo codice.",
        ) from exc

    return project


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
            detail="Progetto non trovato.",
        )

    return project